# -*- coding: utf-8 -*-
"""每天增量抓取 localbanana.io 最新美女提示词，合并进 CosplayPromptNode 缓存。
- 只抓最新若干页（默认10页≈600条），过滤美女 + 露骨词
- 按 target_id 去重，不覆盖已有条目
- 新条目标记 source='banana'，前缀 IMP:，与现有香蕉库一致
用法：python update_banana_daily.py   （需要代理时设置 HTTPS_PROXY 环境变量）
"""
import json
import os
import re
import sys
import time
import base64
import hashlib
import urllib.request
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE_PATH = HERE.parent / "CosplayPromptNode" / "prompt_cache.json"
BASE = "https://www.localbanana.io/api/feed"
MAX_PAGES = 20  # 每天抓最新20页(≈1200条)，扩大覆盖，控制时间和流量

# 与 fetcher.py 一致的过滤规则（放宽版：追加常用人像/日常/自拍/氛围词）
INCLUDE = [
    "woman", "women", "female", "girl", "girls", "lady", "ladies",
    "beauty", "beautiful", "glamour", "fashion", "portrait", "portraits",
    "model", "cosplay", "pinup", "pin-up", "boudoir", "lingerie",
    "bikini", "swimsuit", "babe", "bride", "cheerleader",
    "anime-girl", "anime-woman", "asian-girl", "japanese-girl", "korean-girl",
    "east-asian-woman", "chinese-girl", "teen-girl", "young-woman",
    "soft-girl", "coquette", "egirl", "e-girl", "waifu", "muse",
    # 放宽追加：日常人像 / 自拍 / 穿搭 / 国别 / 情绪氛围
    "attractive", "pretty", "cute", "gorgeous", "stunning", "elegant",
    "graceful", "stylish", "charming", "lovely",
    "selfie", "photoshoot", "photo", "photograph", "photography",
    "candid", "snapshot", "ootd", "outfit", "lookbook", "casual", "lifestyle",
    "japanese", "korean", "asian", "chinese", "east-asian",
    "actress", "idol", "influencer", "wedding", "party", "date",
    "dress", "skirt", "jeans", "heels", "cardigan", "sweater", "coat",
]
EXCLUDE_WORDS = [
    "man", "male", "boy", "boys", "men", "guy", "groom", "father",
    "beard", "mustache", "muscular", "soldier", "military", "middle-aged",
    "old man", "elderly", "grandpa", "uncle", "bro", "dude",
    "cat", "dog", "bird", "horse", "lion", "tiger", "animal", "pet",
    "still-life", "food", "product",
    "abstract",
    "concept", "artwork", "brand", "logo", "poster design", "packaging",
    "enamel", "world cup",
    "advertisement", "advertising", "nike", "adidas", "sneaker", "shoe",
]
BANNED = ('乳头', '阴部', '全裸', '性器', '插入', 'nipple', 'genital',
          'penis', 'vagina', 'oral sex', 'cum ', '裸体', '狗爬', '猛操',
          '勃起', 'sex', 'porn', 'nude', 'naked')


def _has_word(blob: str, word: str) -> bool:    # 严格整词匹配(字母/数字/连字符两侧都算边界), 避免 "car" 误匹配 "cardigan"
    return re.search(r"(?<![A-Za-z0-9-])" + re.escape(word) + r"(?![A-Za-z0-9-])", blob) is not None


def _en(w: str) -> str:
    # 去掉中文注释部分, 保留英文(含多词如 "world cup"); 纯中文词原样保留
    en = re.sub(r'[\u4e00-\u9fff]+', '', w).strip()
    return en if en else w.strip()


def _load_words_from_config():
    """优先从 GUI config 加载词表(单一可编辑来源), config 不可用则用内置词表。"""
    try:
        p = r"L:\工作流\小工具\香蕉提示词抓取\config.json"
        cfg = json.load(open(p, encoding="utf-8"))
        inc = [_en(w) for w in cfg.get("include", []) if w.strip()]
        exc = [_en(w) for w in cfg.get("exclude", []) if w.strip()]
        if inc or exc:
            return inc, exc
    except Exception:
        pass
    return INCLUDE, EXCLUDE_WORDS


INCLUDE, EXCLUDE_WORDS = _load_words_from_config()


def _dedup_prompt(s: str) -> str:
    """localbanana 作者原文常整段或整块重复两遍，入库前去重保留一份。
    覆盖三种模式：
      1) 尾部段重复:  ...\n\nA\n\nA
      2) 首尾段重复:  A\n\n头部\n\nA
      3) 头部后整块重复: 头部\n\nB1\n\nB2\n\nB1\n\nB2  (B 为多段块)
    """
    parts = s.split("\n\n")
    if len(parts) >= 2 and parts[-1].strip() == parts[-2].strip():
        return "\n\n".join(parts[:-1])
    if len(parts) >= 3 and parts[-1].strip() == parts[0].strip():
        return "\n\n".join(parts[:-1])
    # 定位头部段("Image 2 / 原始提示词 / Original Image 2 prompt")
    hi = None
    for i, seg in enumerate(parts):
        if "Image 2" in seg or "原始提示词" in seg or "Original Image 2" in seg:
            hi = i
            break
    body = parts[hi + 1:] if hi is not None else parts
    if len(body) >= 4 and len(body) % 2 == 0:
        half = len(body) // 2
        left = [p.strip() for p in body[:half]]
        right = [p.strip() for p in body[half:]]
        if left == right:
            keep = (parts[:hi + 1] if hi is not None else []) + body[:half]
            return "\n\n".join(keep)
    return s


def is_beauty(it: dict) -> bool:
    tags = [t.lower() for t in (it.get("tags") or [])]
    cat = ",".join(it.get("category") or []).lower()
    title = (it.get("title_en") or "").lower()
    prompt = (it.get("prompt_en") or "").lower()
    title_zh = (it.get("title_zh") or "").lower()
    prompt_zh = (it.get("prompt_zh") or "").lower()
    # 中英文都纳入匹配: 中文杂质(海藻/雕塑等)也能被黑名单拦住, 中文美女描述也能被白名单召回
    blob = (" ".join(tags) + " " + cat + " " + title + " " + prompt[:500]
            + " " + title_zh + " " + prompt_zh[:500])
    for ex in EXCLUDE_WORDS:
        if _has_word(blob, ex):
            return False
    return any(_has_word(blob, inc) for inc in INCLUDE)


def _is_banned(it: dict) -> bool:
    blob = " ".join([
        (it.get("title_en") or ""), (it.get("title_zh") or ""),
        (it.get("prompt_en") or ""), (it.get("prompt_zh") or ""),
        (it.get("title") or ""),
    ]).lower()
    return any(w in blob for w in BANNED)


def _http_get(url: str, retries=3) -> dict:
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "Accept": "application/json",
            })
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            last = e
            time.sleep(1.5 * (i + 1))
    raise last


def fetch_latest():
    """抓最新 MAX_PAGES 页 feed"""
    items = []
    cursor = None
    for page in range(MAX_PAGES):
        url = BASE
        if cursor:
            url += "?cursor=" + urllib.parse.quote(cursor)
        data = _http_get(url)
        batch = data.get("items", [])
        items.extend(batch)
        if not data.get("hasMore") or not batch:
            break
        cursor = data.get("cursor")
        time.sleep(0.25)
    return items


def main():
    if not CACHE_PATH.exists():
        print(f"缓存不存在: {CACHE_PATH}")
        sys.exit(1)

    cache = json.load(open(CACHE_PATH, encoding="utf-8"))
    # 已存在的 target_id 集合（去重）
    existing_ids = {v.get("target_id") for v in cache.values() if v.get("target_id")}

    print(f"抓取 localbanana 最新 {MAX_PAGES} 页...")
    items = fetch_latest()
    print(f"拿到 {len(items)} 条原始条目")

    added = 0
    skipped = {"非美女": 0, "露骨": 0, "已存在": 0, "无提示词": 0}
    for it in items:
        pid = str(it.get("id") or "")
        if not pid:
            continue
        if not is_beauty(it):
            skipped["非美女"] += 1
            continue
        if _is_banned(it):
            skipped["露骨"] += 1
            continue
        prompt_en = (it.get("prompt_en") or "").strip()
        prompt_zh = (it.get("prompt_zh") or "").strip()
        if not prompt_en and not prompt_zh:
            skipped["无提示词"] += 1
            continue
        # 完整版: 中文引导 + 英文细节(与平台原样一致), 单语言时用已有的兜底
        if prompt_zh and prompt_en:
            prompt = prompt_zh + "\n\n" + prompt_en
        elif prompt_en:
            prompt = prompt_en
        else:
            prompt = prompt_zh
        title = (it.get("title_en") or it.get("title_zh") or it.get("title") or "").strip()
        prompt = _dedup_prompt(prompt)
        target_id = f"BN-{pid[:8]}"
        if target_id in existing_ids:
            skipped["已存在"] += 1
            continue
        try:
            a, b = [float(x) for x in (it.get("aspect_ratio") or "2:3").split(":")]
        except Exception:
            a, b = 2, 3
        scale = 1024 / max(a, b)
        w, h = max(64, round(a * scale)), max(64, round(b * scale))
        try:
            ts = int(time.time())
        except Exception:
            ts = int(time.time())
        key = "IMP:" + hashlib.md5(pid.encode()).hexdigest()[:8]
        cache[key] = {
            "prompt": prompt, "prompt_zh": prompt_zh, "title": title,
            "width": w, "height": h,
            "target_id": target_id, "ts": ts,
            "is_video": False, "source": "banana",
        }
        existing_ids.add(target_id)
        added += 1

    tmp = str(CACHE_PATH) + ".tmp"
    json.dump(cache, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, CACHE_PATH)

    n_banana = sum(1 for v in cache.values() if v.get("source") == "banana")
    print(f"完成: 新增 {added} 条 | 跳过 {skipped} | 香蕉库共 {n_banana} 条 | 库总 {len(cache)} 条")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""香蕉提示词库 · 后期筛查脚本
用法:
  python scan_cleanup.py --report          # 只扫描报告疑似杂质(不删)
  python scan_cleanup.py --clean           # 扫描并删除疑似杂质(自动备份)
  python scan_cleanup.py --report --all    # 不限定 source=banana, 扫全库
说明:
  用与抓取完全一致的 is_beauty(白名单整词+黑名单整词) 重筛库内条目,
  未通过的一律列为"疑似杂质"。
"""
import sys, os, json, time, datetime, argparse, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(HERE, "config.json")
sys.path.insert(0, os.path.join(HERE, "..", "ComfyUI", "ComfyUI", "custom_nodes", "localbanana-prompts"))
try:
    import update_banana_daily as u
except Exception:
    sys.path.insert(0, r"L:\ComfyUI\ComfyUI\custom_nodes\localbanana-prompts")
    import update_banana_daily as u


def _en(w):
    # 去掉中文注释部分, 保留英文(含多词如 "world cup"); 无英文则原样
    import re as _re
    en = _re.sub(r'[\u4e00-\u9fff]+', '', w).strip()
    return en if en else w.strip()


def load_words():
    # 直接使用 update_banana_daily 内置权威词表(与抓取同口径), 不覆盖
    cfg = json.load(open(CONFIG_FILE, encoding="utf-8"))
    return cfg


def scan(cache_path, only_banana=True):
    data = json.load(open(cache_path, encoding="utf-8"))
    suspects, keep = [], []
    for k, v in data.items():
        if only_banana and v.get("source") != "banana":
            continue
        it = {
            "title_en": v.get("title") or "", "prompt_en": v.get("prompt") or "",
            "title_zh": "", "prompt_zh": v.get("prompt_zh") or "",
            "tags": [], "category": [],
        }
        if u.is_beauty(it):
            keep.append(k)
        else:
            suspects.append((k, v))
    return data, suspects, keep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true", help="只报告不删除")
    ap.add_argument("--clean", action="store_true", help="删除疑似杂质并备份")
    ap.add_argument("--all", action="store_true", help="扫全库(默认只扫 banana 来源)")
    args = ap.parse_args()
    cfg = load_words()
    cache = cfg.get("cache") or r"L:\ComfyUI\ComfyUI\custom_nodes\CosplayPromptNode\prompt_cache.json"
    data, suspects, keep = scan(cache, only_banana=not args.all)
    print(f"扫描范围: {'全库' if args.all else 'banana来源'} | 词表 白{len(u.INCLUDE)}/黑{len(u.EXCLUDE_WORDS)}")
    print(f"条目 {len(data)} 条, 疑似杂质 {len(suspects)} 条")
    for i, (k, v) in enumerate(suspects[:40], 1):
        print(f"  {i}. {v.get('target_id') or k} | {(v.get('title') or '')[:60]}")
    if len(suspects) > 40:
        print(f"  ... 其余 {len(suspects) - 40} 条省略")
    if args.clean and suspects:
        bak = cache.replace("prompt_cache.json",
                            f"deleted_banana_scan_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        drop = {k: data.pop(k) for k, _ in suspects}
        json.dump(drop, open(bak, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        tmp = cache + ".scan.tmp"
        json.dump(data, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
        os.replace(tmp, cache)
        print(f"已删除 {len(drop)} 条, 库剩 {len(data)} 条, 备份: {bak}")


if __name__ == "__main__":
    main()

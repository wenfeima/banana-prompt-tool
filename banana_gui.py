# -*- coding: utf-8 -*-
"""香蕉提示词抓取器 GUI — PySide6
目录: L:\\工作流\\小工具\\BananaPromptGrabber\\
启动: 双击 打开香蕉抓取GUI.bat (调用 L:\\OpenClaw\\ComfyUI\\python_embeded\\pythonw.exe)

所有参数/词表均可视化配置, 保存到 config.json, 下次打开自动沿用。
"""
import sys
import os
import io
import re
import ast
import json
import time
import hashlib
import contextlib
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
FETCH_DIR = Path(r"L:\ComfyUI\ComfyUI\custom_nodes\localbanana-prompts")
DEFAULT_CACHE = Path(r"L:\ComfyUI\ComfyUI\custom_nodes\CosplayPromptNode\prompt_cache.json")
CONFIG_FILE = HERE / "config.json"
VIEWER_BAT = Path(r"L:\工作流\小工具\香蕉提示词抓取\打开查看器.bat")

try:
    from PySide6.QtWidgets import (
        QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
        QGroupBox, QLabel, QLineEdit, QComboBox, QPushButton, QListWidget,
        QListWidgetItem, QPlainTextEdit, QCheckBox, QFileDialog, QMessageBox,
    )
    from PySide6.QtCore import Qt, QThread, Signal, QSize
    from PySide6.QtGui import QFont
except ImportError:
    print("未安装 PySide6, 请先运行: L:\\OpenClaw\\ComfyUI\\python_embeded\\python.exe -m pip install PySide6")
    sys.exit(1)

sys.path.insert(0, str(FETCH_DIR))

# 默认词表(英文+中文注释)。抓取时只取开头的英文部分参与过滤, 中文仅作界面提示。
DEFAULT_INCLUDE = [
    "woman 女人", "women 女人们", "female 女性", "girl 女孩", "girls 女孩们",
    "lady 女士", "ladies 女士们", "beauty 美女", "beautiful 漂亮", "glamour 魅力",
    "fashion 时尚", "portrait 人像", "portraits 人像作品", "model 模特",
    "cosplay 角色扮演", "pinup 海报女郎", "pin-up 海报女郎", "boudoir 闺房风",
    "lingerie 内衣", "bikini 比基尼", "swimsuit 泳装", "babe 美女", "bride 新娘",
    "cheerleader 拉拉队员", "anime-girl 动漫女孩", "anime-woman 动漫女性",
    "asian-girl 亚洲女孩", "japanese-girl 日本女孩", "korean-girl 韩国女孩",
    "east-asian-woman 东亚女性", "chinese-girl 中国女孩", "teen-girl 少女",
    "young-woman 年轻女性", "soft-girl 软妹风", "coquette 可爱少女风",
    "egirl 网络女孩", "e-girl 网络女孩", "waifu 二次元女神", "muse 缪斯",
    "attractive 迷人", "pretty 好看", "cute 可爱", "gorgeous 华丽", "stunning 惊艳",
    "elegant 优雅", "graceful 优雅气质", "stylish 时髦", "charming 迷人", "lovely 可爱",
    "selfie 自拍", "photoshoot 棚拍写真", "photo 照片", "photograph 照片",
    "photography 摄影", "candid 抓拍", "snapshot 快照", "ootd 今日穿搭",
    "outfit 穿搭", "lookbook 穿搭图鉴", "casual 休闲风", "lifestyle 生活方式",
    "japanese 日本", "korean 韩国", "asian 亚洲", "chinese 中国", "east-asian 东亚",
    "actress 女演员", "idol 偶像", "influencer 网红", "wedding 婚礼", "party 派对",
    "date 约会", "dress 连衣裙", "skirt 短裙", "jeans 牛仔裤", "heels 高跟鞋",
    "cardigan 开衫", "sweater 毛衣", "coat 外套",
    # 中文召回词(命中中文 prompt 的美女描述)
    "写真", "写真集", "少女", "旗袍", "汉服", "穿搭", "自拍", "美女", "可爱",
    "漂亮", "女神", "泳装", "比基尼", "婚纱", "新娘", "网红", "明星", "杂志",
    "封面", "模特", "人像", "肖像", "日常", "校园", "街拍", "女仆", "水手服",
    "和服", "时装", "特写", "画报", "妆容",
]
DEFAULT_EXCLUDE = [
    "man 男人", "male 男性", "boy 男孩", "boys 男孩们", "men 男人们", "guy 家伙",
    "groom 新郎", "father 父亲", "beard 胡子", "mustache 络腮胡", "muscular 肌肉男",
    "soldier 士兵", "military 军人", "middle-aged 中年", "old man 老年男人",
    "elderly 年长者", "grandpa 爷爷", "uncle 叔叔", "bro 兄弟", "dude 老兄",
    "cat 猫", "dog 狗", "bird 鸟", "horse 马", "lion 狮子", "tiger 老虎",
    "animal 动物", "pet 宠物", "still-life 静物", "food 食物",
    "product 商品", "abstract 抽象",
        # 中文排除词(拦中文描述的无人像/非写实杂质)
    "海藻", "雕塑", "帆船", "候船", "微距", "静物", "风景", "建筑", "植物",
    "插画", "油画", "水粉", "陶瓷", "仓鼠", "考拉", "昆虫", "像素", "精灵",
    "游戏", "恐怖", "贴纸", "海报", "字体", "网格", "展厅", "画廊",
    "码头", "灯塔", "渡轮", "闹钟", "咖啡店", "汽水", "招牌", "剪贴簿", "手写",
    "论文", "手绘", "动漫",  "概念", "水母", "红熊猫", "邮局",
    "蕨类", "兰花", "珊瑚", "梨园", "果园", "羊毛", "黄油", "早餐", "算盘",
    "雨滴", "铅笔", "森林", "云朵", "洗衣", "草莓", "墨水", "纱线", "石灰",
    "印章", "卷心菜", "宇航员", "毛衣", "山峦", "河流", "瀑布", "星空", "银河",
    "月球", "星球", "汽车", "摩托车", "火车", "飞机", "轮船", "客厅", "卧室",
    "厨房", "图书馆", "博物馆", "教室", "美食", "甜点", "蛋糕", "水果", "蔬菜",
    "包豪斯", "漫画", "苹果材质", "玻璃杯", "视觉艺术", "旅行日志", "品牌视觉",
    "concept 概念", "artwork 艺术作品", "brand 品牌", "logo 标志", "poster design 海报设计", "packaging 包装",
    "enamel 珐琅", "world cup 世界杯",
    "advertisement 广告", "advertising 广告", "nike 耐克", "adidas 阿迪达斯", "sneaker 运动鞋", "shoe 鞋子",
]


def _en_part(s: str) -> str:
    """取词条开头的英文部分(字母/数字/连字符/空格), 丢弃中文注释。
    若英文部分最后一个 token 后紧跟中文(无空格), 视为注释开头, 回退丢弃该 token。
    """
    s = s.strip()
    m = re.match(r"[A-Za-z0-9-]+(?:[ ][A-Za-z0-9-]+)*", s)
    if not m:
        return s
    en = m.group(0)
    end = m.end()
    if end < len(s) and re.match(r"[\u4e00-\u9fff]", s[end:]):
        parts = en.split(" ")
        if len(parts) > 1:
            return " ".join(parts[:-1])
    return en

DARK_QSS = """
QWidget{background:#1e1e1e;color:#e0e0e0;font-size:13px}
QGroupBox{border:1px solid #3a3a3a;border-radius:8px;margin-top:10px;padding-top:12px;font-weight:bold}
QGroupBox::title{subcontrol-origin:margin;left:12px;padding:0 4px;color:#7ec8ff}
QLineEdit,QComboBox,QPlainTextEdit,QListWidget{border:1px solid #3a3a3a;border-radius:5px;padding:4px;background:#252526;selection-background-color:#094771}
QLineEdit:focus,QComboBox:focus,QPlainTextEdit:focus,QListWidget:focus{border-color:#4a9eff}
QComboBox::drop-down{border:none;width:22px}
QPushButton{border:1px solid #3a3a3a;border-radius:5px;padding:6px 10px;background:#333;color:#e0e0e0}
QPushButton:hover{background:#3d3d3d;border-color:#4a9eff}
QPushButton:pressed{background:#2a2a2a}
QPushButton:disabled{color:#777;background:#2b2b2b}
QPushButton#primary{background:#0e639c;border-color:#1177bb;color:#fff}
QPushButton#primary:hover{background:#1177bb}
QPushButton#danger{background:#8a2f2f;border-color:#b33;color:#fff}
QPushButton#danger:hover{background:#a33}
QListWidget{background:#1b1b1b}
QPlainTextEdit{background:#141414;font-family:Consolas,monospace;font-size:12px}
QCheckBox::indicator{width:15px;height:15px}
"""

LIGHT_QSS = """
QWidget{background:#f5f5f5;color:#1a1a1a;font-size:13px}
QGroupBox{border:1px solid #c8c8c8;border-radius:8px;margin-top:10px;padding-top:12px;font-weight:bold}
QGroupBox::title{subcontrol-origin:margin;left:12px;padding:0 4px;color:#0e639c}
QLineEdit,QComboBox,QPlainTextEdit,QListWidget{border:1px solid #c8c8c8;border-radius:5px;padding:4px;background:#fff;selection-background-color:#cce5ff}
QLineEdit:focus,QComboBox:focus,QPlainTextEdit:focus,QListWidget:focus{border-color:#0e639c}
QComboBox::drop-down{border:none;width:22px}
QPushButton{border:1px solid #c8c8c8;border-radius:5px;padding:6px 10px;background:#fff;color:#1a1a1a}
QPushButton:hover{background:#eef4fb;border-color:#0e639c}
QPushButton:pressed{background:#e0e8f0}
QPushButton:disabled{color:#aaa;background:#eee}
QPushButton#primary{background:#0e639c;border-color:#0e639c;color:#fff}
QPushButton#primary:hover{background:#1177bb}
QPushButton#danger{background:#c0504d;border-color:#c0504d;color:#fff}
QPushButton#danger:hover{background:#d05552}
QListWidget{background:#fff}
QPlainTextEdit{background:#fff;font-family:Consolas,monospace;font-size:12px}
QCheckBox::indicator{width:15px;height:15px}
"""


def _make_is_beauty(mode):
    """按过滤模式生成 is_beauty 判定函数。
    strict: 白名单+黑名单(原逻辑);  loose: 仅黑名单(不命中排除词即收)。
    """
    import update_banana_daily as u
    if mode == "loose":
        def loose(it):
            blob = (" ".join(t.lower() for t in (it.get("tags") or [])) + " "
                    + ",".join(it.get("category") or []).lower() + " "
                    + (it.get("title_en") or "").lower() + " "
                    + (it.get("prompt_en") or "")[:500].lower() + " "
                    + (it.get("title_zh") or "").lower() + " "
                    + (it.get("prompt_zh") or "")[:500].lower())
            return not any(u._has_word(blob, ex) for ex in u.EXCLUDE_WORDS)
        return loose
    return u.is_beauty


class FetchThread(QThread):
    log = Signal(str)
    finished_ok = Signal(dict)

    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.cfg = cfg

    def run(self):
        try:
            proxy = (self.cfg.get("proxy") or "").strip()
            if proxy:
                os.environ["HTTPS_PROXY"] = proxy
                os.environ["HTTP_PROXY"] = proxy
            else:
                os.environ.pop("HTTPS_PROXY", None)
                os.environ.pop("HTTP_PROXY", None)
            import update_banana_daily as u
            u.MAX_PAGES = int(self.cfg.get("pages", 20))
            u.INCLUDE = [_en_part(w) for w in self.cfg.get("include", []) if w.strip()]
            u.EXCLUDE_WORDS = [_en_part(w) for w in self.cfg.get("exclude", []) if w.strip()]
            u.CACHE_PATH = Path(self.cfg.get("cache") or str(DEFAULT_CACHE))
            u.is_beauty = _make_is_beauty(self.cfg.get("mode", "strict"))
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                u.main()
            out = buf.getvalue()
            for line in out.splitlines():
                self.log.emit(line)
            stats = {"ok": True, "raw": out}
            m = re.search(r"新增\s+(\d+)\s+条.*?香蕉库共\s+(\d+)\s+条.*?库总\s+(\d+)\s+条", out)
            if m:
                stats.update(added=int(m.group(1)), banana=int(m.group(2)), total=int(m.group(3)))
            m2 = re.search(r"跳过\s+(\{.*?\})", out)
            if m2:
                try:
                    stats["skipped"] = ast.literal_eval(m2.group(1))
                except Exception:
                    pass
            self.finished_ok.emit(stats)
        except Exception as e:
            self.log.emit("抓取异常: " + str(e))
            self.finished_ok.emit({"ok": False, "err": str(e)})


class SingleThread(QThread):
    log = Signal(str)

    def __init__(self, url, cfg, parent=None):
        super().__init__(parent)
        self.url = url
        self.cfg = cfg

    def run(self):
        try:
            import update_banana_daily as u
            u.INCLUDE = [_en_part(w) for w in self.cfg.get("include", []) if w.strip()]
            u.EXCLUDE_WORDS = [_en_part(w) for w in self.cfg.get("exclude", []) if w.strip()]
            u.CACHE_PATH = Path(self.cfg.get("cache") or str(DEFAULT_CACHE))
            u.is_beauty = _make_is_beauty(self.cfg.get("mode", "strict"))
            pid = self._extract_id(self.url)
            if not pid:
                self.log.emit("无法从链接识别作品 ID(需包含 8-4-4-4-12 的 UUID)")
                return
            it = self._fetch_item(pid)
            if it is None:
                self.log.emit("单条接口不可用或作品不存在(实验功能, 可用批量抓取代替)")
                return
            self.log.emit(self._ingest(pid, it, self.cfg))
        except Exception as e:
            self.log.emit("单条补抓异常: " + str(e))

    def _extract_id(self, url):
        m = re.search(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", url, re.I)
        return m.group(1) if m else None

    def _fetch_item(self, pid):
        import urllib.request
        for api in (
            f"https://www.localbanana.io/api/posts/{pid}",
            f"https://www.localbanana.io/api/post/{pid}",
            f"https://www.localbanana.io/api/items/{pid}",
        ):
            try:
                req = urllib.request.Request(api, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                    "Accept": "application/json",
                })
                data = json.loads(urllib.request.urlopen(req, timeout=20).read().decode("utf-8"))
                if isinstance(data, dict):
                    for k in ("item", "post", "data"):
                        if isinstance(data.get(k), dict):
                            return data[k]
                    return data
            except Exception:
                continue
        return None

    def _ingest(self, pid, it, cfg):
        import update_banana_daily as u
        cache = Path(cfg.get("cache") or str(DEFAULT_CACHE))
        if not cache.exists():
            return "库文件不存在: " + str(cache)
        if not u.is_beauty(it):
            return "未命中美女关键词, 未入库"
        if u._is_banned(it):
            return "含露骨词, 未入库"
        pen = (it.get("prompt_en") or "").strip()
        pzh = (it.get("prompt_zh") or "").strip()
        if not pen and not pzh:
            return "无提示词, 未入库"
        prompt = (pzh + "\n\n" + pen) if (pzh and pen) else (pen or pzh)
        title = (it.get("title_en") or it.get("title_zh") or it.get("title") or "").strip()
        tid = f"BN-{pid[:8]}"
        d = json.load(open(cache, encoding="utf-8"))
        if any(v.get("target_id") == tid for v in d.values()):
            return "该作品已在库中: " + tid
        try:
            a, b = [float(x) for x in (it.get("aspect_ratio") or "2:3").split(":")]
        except Exception:
            a, b = 2, 3
        sc = 1024 / max(a, b)
        w, h = max(64, round(a * sc)), max(64, round(b * sc))
        key = "IMP:" + hashlib.md5(pid.encode()).hexdigest()[:8]
        d[key] = {
            "prompt": prompt, "prompt_zh": pzh, "title": title,
            "width": w, "height": h, "target_id": tid,
            "ts": int(time.time()), "is_video": False, "source": "banana",
        }
        tmp = str(cache) + ".tmp"
        json.dump(d, open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
        os.replace(tmp, cache)
        return f"已入库 {tid} (title: {title or '无'})"


class ScanThread(QThread):
    """后期筛查: 用当前词表重筛库内 banana 条目, 报告或一键清理疑似杂质。"""
    log = Signal(str)
    finished_ok = Signal(dict)

    def __init__(self, cfg, clean=False, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.clean = clean

    def run(self):
        try:
            import update_banana_daily as u
            u.INCLUDE = [_en_part(w) for w in self.cfg.get("include", []) if w.strip()]
            u.EXCLUDE_WORDS = [_en_part(w) for w in self.cfg.get("exclude", []) if w.strip()]
            cache = Path(self.cfg.get("cache") or str(DEFAULT_CACHE))
            data = json.loads(cache.read_text(encoding="utf-8"))
            suspects = []
            for k, v in data.items():
                if v.get("source") != "banana":
                    continue
                it = {"title_en": v.get("title") or "", "prompt_en": v.get("prompt") or "",
                      "title_zh": "", "prompt_zh": v.get("prompt_zh") or "", "tags": [], "category": []}
                if not u.is_beauty(it):
                    suspects.append((k, v))
            self.log.emit(f"筛查: 词表 白{len(u.INCLUDE)}/黑{len(u.EXCLUDE_WORDS)} | 条目 {len(data)} 条 | 疑似杂质 {len(suspects)} 条")
            for i, (k, v) in enumerate(suspects[:30], 1):
                title = (v.get("title") or "")[:40]
                self.log.emit(f"  {i}. {title or k} | {(v.get('prompt') or '')[:45]}")
            if len(suspects) > 30:
                self.log.emit(f"  ... 其余 {len(suspects) - 30} 条(共 {len(suspects)} 条)")
            if self.clean and suspects:
                bak = cache.with_name(f"deleted_banana_scan_{time.strftime('%Y%m%d_%H%M%S')}.json")
                drop = {k: data.pop(k) for k, _ in suspects}
                bak.write_text(json.dumps(drop, ensure_ascii=False, indent=1), encoding="utf-8")
                cache.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                self.log.emit(f"已删除 {len(drop)} 条, 库剩 {len(data)} 条, 备份: {bak}")
            self.finished_ok.emit({"ok": True, "suspects": len(suspects), "total": len(data), "clean": self.clean})
        except Exception as e:
            self.log.emit("筛查异常: " + str(e))
            self.finished_ok.emit({"ok": False, "err": str(e)})


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🍌 香蕉提示词抓取器")
        self.resize(760, 720)
        self.theme = "dark"
        self._build_ui()
        self._load_cfg()
        self._apply_theme()

    # ---------- UI ----------
    def _build_ui(self):
        root = QVBoxLayout(self)

        # 抓取配置
        g1 = QGroupBox("抓取配置")
        gl = QGridLayout(g1)
        gl.addWidget(QLabel("抓取页数:"), 0, 0)
        self.pagesCombo = QComboBox()
        self.pagesCombo.setEditable(True)
        self.pagesCombo.setInsertPolicy(QComboBox.NoInsert)
        for p in ("5", "10", "15", "20", "30", "50", "100"):
            self.pagesCombo.addItem(p)
        self.pagesCombo.setCurrentText("20")
        self.pagesCombo.setToolTip("可下拉选择，也可直接输入任意页数（如 45 / 80）")
        gl.addWidget(self.pagesCombo, 0, 1)
        gl.addWidget(QLabel("代理地址:"), 0, 2)
        self.proxyEdit = QLineEdit("http://127.0.0.1:10808")
        self.proxyEdit.setPlaceholderText("留空 = 不使用代理")
        gl.addWidget(self.proxyEdit, 0, 3, 1, 3)
        gl.addWidget(QLabel("过滤模式:"), 1, 0)
        self.modeCombo = QComboBox()
        self.modeCombo.addItem("严格(白名单+黑名单)", "strict")
        self.modeCombo.addItem("宽松(仅黑名单)", "loose")
        self.modeCombo.setToolTip("严格=命中白名单任一且不命中黑名单; 宽松=只要不命中黑名单就收")
        gl.addWidget(self.modeCombo, 1, 1)
        gl.addWidget(QLabel("库文件:"), 2, 0)
        self.cacheEdit = QLineEdit(str(DEFAULT_CACHE))
        gl.addWidget(self.cacheEdit, 2, 1, 1, 5)
        browseBtn = QPushButton("📂 浏览")
        browseBtn.setToolTip("选择 prompt_cache.json")
        browseBtn.clicked.connect(self._browse_cache)
        gl.addWidget(browseBtn, 2, 6)
        root.addWidget(g1)

        # 过滤词表
        g2 = QGroupBox("过滤规则(可编辑: 增删/导入导出txt/重置默认)")
        gl2 = QGridLayout(g2)
        self.incList = QListWidget()
        self.incList.setToolTip("美女白名单: 命中任一即通过")
        self.incList.setMinimumHeight(140)
        self.excList = QListWidget()
        self.excList.setToolTip("露骨黑名单: 命中任一即拦截")
        self.excList.setMinimumHeight(140)
        gl2.addWidget(QLabel("✅ 美女白名单:"), 0, 0)
        gl2.addWidget(QLabel("🚫 露骨黑名单:"), 0, 1)
        gl2.addWidget(self.incList, 1, 0)
        gl2.addWidget(self.excList, 1, 1)

        def _make_tag_btns(listwidget, target):
            btns = QHBoxLayout()
            for text, tooltip, cb in (
                ("➕", "添加一个词", lambda: self._add_tag(listwidget)),
                ("➖", "删除选中", lambda: self._del_tag(listwidget)),
                ("📥", "从txt批量导入", lambda: self._import_tag(listwidget)),
                ("📤", "导出为txt", lambda: self._export_tag(listwidget)),
                ("♻️", "重置为默认词表", lambda: self._reset_tag(listwidget, target)),
            ):
                b = QPushButton(text)
                b.setToolTip(tooltip)
                b.setMaximumWidth(40)
                b.clicked.connect(cb)
                btns.addWidget(b)
            btns.addStretch(1)
            return btns

        gl2.addLayout(_make_tag_btns(self.incList, "inc"), 2, 0)
        gl2.addLayout(_make_tag_btns(self.excList, "exc"), 2, 1)
        root.addWidget(g2)

        # 操作
        g3 = QGroupBox("操作")
        g3l = QHBoxLayout(g3)
        self.statusDot = QLabel("●")
        self.statusDot.setStyleSheet("color:#e44;font-size:18px")
        self.statusDot.setToolTip("红=空闲/失败, 绿=运行中")
        g3l.addWidget(self.statusDot)
        self.fetchBtn = QPushButton("🟢 开始抓取")
        self.fetchBtn.setObjectName("primary")
        self.fetchBtn.setToolTip("按当前配置抓取 localbanana 最新N页, 增量合并入库")
        self.fetchBtn.clicked.connect(self._start_fetch)
        g3l.addWidget(self.fetchBtn)
        self.scanBtn = QPushButton("🔍 后期筛查")
        self.scanBtn.setToolTip("用当前词表重筛库内 banana 条目: 报告疑似杂质, 可选一键清理(自动备份)")
        self.scanBtn.clicked.connect(self._start_scan)
        g3l.addWidget(self.scanBtn)
        self.singleEdit = QLineEdit()
        self.singleEdit.setPlaceholderText("粘贴 localbanana 作品链接(实验性单条补抓)...")
        g3l.addWidget(self.singleEdit, 1)
        singleBtn = QPushButton("🔗 补抓")
        singleBtn.setToolTip("单条补抓: 从链接识别作品ID, 直接入库(需平台支持详情接口)")
        singleBtn.clicked.connect(self._start_single)
        g3l.addWidget(singleBtn)
        root.addWidget(g3)

        # 附加按钮行
        g4 = QHBoxLayout()
        openDir = QPushButton("📂 打开库文件夹")
        openDir.clicked.connect(self._open_dir)
        openViewer = QPushButton("🌐 打开网页查看器")
        openViewer.clicked.connect(self._open_viewer)
        saveCfg = QPushButton("💾 保存配置")
        saveCfg.clicked.connect(self._save_cfg)
        loadCfg = QPushButton("🔄 加载配置")
        loadCfg.clicked.connect(self._load_cfg)
        self.themeBtn = QPushButton("🌙 夜间模式")
        self.themeBtn.clicked.connect(self._toggle_theme)
        self.topChk = QCheckBox("窗口置顶")
        self.topChk.toggled.connect(lambda v: self.setWindowFlag(Qt.WindowStaysOnTopHint, v) or self.show())
        self.autoChk = QCheckBox("启动自动加载配置")
        self.autoChk.setChecked(True)
        for b in (openDir, openViewer, saveCfg, loadCfg, self.themeBtn):
            g4.addWidget(b)
        g4.addWidget(self.topChk)
        g4.addWidget(self.autoChk)
        g4.addStretch(1)
        root.addLayout(g4)

        # 日志
        g5 = QGroupBox("日志")
        g5v = QVBoxLayout(g5)
        self.statLabel = QLabel("尚未抓取")
        g5v.addWidget(self.statLabel)
        self.logView = QPlainTextEdit()
        self.logView.setReadOnly(True)
        self.logView.setMaximumBlockCount(5000)
        g5v.addWidget(self.logView, 1)
        logBtns = QHBoxLayout()
        clearLog = QPushButton("🧹 清空日志")
        clearLog.clicked.connect(self.logView.clear)
        exportLog = QPushButton("📤 导出日志")
        exportLog.clicked.connect(self._export_log)
        logBtns.addWidget(clearLog)
        logBtns.addWidget(exportLog)
        logBtns.addStretch(1)
        g5v.addLayout(logBtns)
        root.addWidget(g5, 1)

    # ---------- 词表操作 ----------
    def _add_tag(self, lst):
        from PySide6.QtWidgets import QInputDialog
        w, ok = QInputDialog.getText(self, "添加关键词", "输入新词:")
        if ok and w.strip():
            lst.addItem(w.strip())

    def _del_tag(self, lst):
        for it in lst.selectedItems():
            lst.takeItem(lst.row(it))

    def _import_tag(self, lst):
        fp, _ = QFileDialog.getOpenFileName(self, "选择txt词表", str(HERE), "文本文件 (*.txt)")
        if not fp:
            return
        try:
            txt = Path(fp).read_text(encoding="utf-8-sig")
        except Exception:
            txt = Path(fp).read_text(encoding="gbk", errors="ignore")
        words = [w.strip() for w in re.split(r"[\n,，、;；\t]+", txt) if w.strip()]
        for w in words:
            lst.addItem(w)
        self.log(f"已从 {Path(fp).name} 导入 {len(words)} 个词")

    def _export_tag(self, lst):
        fp, _ = QFileDialog.getSaveFileName(self, "导出词表txt", str(HERE / "词表.txt"), "文本文件 (*.txt)")
        if not fp:
            return
        words = [lst.item(i).text() for i in range(lst.count())]
        Path(fp).write_text("\n".join(words), encoding="utf-8")
        self.log(f"已导出 {len(words)} 个词 -> {fp}")

    def _reset_tag(self, lst, target):
        default = DEFAULT_INCLUDE if target == "inc" else DEFAULT_EXCLUDE
        lst.clear()
        for w in default:
            lst.addItem(w)
        self.log(f"白名单/黑名单已重置为默认({len(default)}词)")

    # ---------- 配置 ----------
    def _collect_cfg(self):
        txt = self.pagesCombo.currentText().strip()
        try:
            pages = int(txt)
            if pages < 1:
                pages = 20
        except ValueError:
            pages = 20
        return {
            "pages": pages,
            "mode": self.modeCombo.currentData(),
            "proxy": self.proxyEdit.text().strip(),
            "cache": self.cacheEdit.text().strip(),
            "include": [self.incList.item(i).text() for i in range(self.incList.count())],
            "exclude": [self.excList.item(i).text() for i in range(self.excList.count())],
            "theme": self.theme,
            "topmost": self.topChk.isChecked(),
            "auto_load": self.autoChk.isChecked(),
        }

    def _save_cfg(self):
        cfg = self._collect_cfg()
        json.dump(cfg, open(CONFIG_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        self.log(f"配置已保存 -> {CONFIG_FILE}")

    def _load_cfg(self):
        if not CONFIG_FILE.exists():
            self.incList.clear()
            for w in DEFAULT_INCLUDE:
                self.incList.addItem(w)
            self.excList.clear()
            for w in DEFAULT_EXCLUDE:
                self.excList.addItem(w)
            return
        try:
            cfg = json.load(open(CONFIG_FILE, encoding="utf-8"))
        except Exception:
            return
        self.pagesCombo.setCurrentText(str(cfg.get("pages", 20)))
        mode = cfg.get("mode", "strict")
        idx = self.modeCombo.findData(mode)
        if idx >= 0:
            self.modeCombo.setCurrentIndex(idx)
        self.proxyEdit.setText(cfg.get("proxy", ""))
        if cfg.get("cache"):
            self.cacheEdit.setText(cfg["cache"])
        for lst, key, default in (
            (self.incList, "include", DEFAULT_INCLUDE),
            (self.excList, "exclude", DEFAULT_EXCLUDE),
        ):
            lst.clear()
            for w in cfg.get(key) or default:
                lst.addItem(w)
        self.theme = cfg.get("theme", "dark")
        self.topChk.setChecked(bool(cfg.get("topmost", False)))
        self.autoChk.setChecked(bool(cfg.get("auto_load", True)))
        self.log("已加载配置")

    # ---------- 动作 ----------
    def _browse_cache(self):
        fp, _ = QFileDialog.getOpenFileName(self, "选择 prompt_cache.json", str(DEFAULT_CACHE), "JSON (*.json)")
        if fp:
            self.cacheEdit.setText(fp)

    def _open_dir(self):
        d = Path(self.cacheEdit.text()).parent
        os.startfile(str(d))

    def _open_viewer(self):
        if VIEWER_BAT.exists():
            subprocess.Popen([str(VIEWER_BAT)], cwd=str(VIEWER_BAT.parent), shell=True)
        else:
            QMessageBox.warning(self, "提示", "未找到 打开查看器.bat:\n" + str(VIEWER_BAT))

    def _toggle_theme(self):
        self.theme = "light" if self.theme == "dark" else "dark"
        self._apply_theme()
        self._save_cfg()

    def _apply_theme(self):
        self.setStyleSheet(DARK_QSS if self.theme == "dark" else LIGHT_QSS)
        self.themeBtn.setText("🌙 夜间模式" if self.theme == "light" else "☀️ 日间模式")

    def _start_fetch(self):
        if hasattr(self, "_thread") and self._thread.isRunning():
            return
        cfg = self._collect_cfg()
        self._set_busy(True)
        self.log("=" * 30)
        self.log(f"开始抓取: 页数={cfg['pages']} 代理={cfg['proxy'] or '无'} 词表 白{len(cfg['include'])}/黑{len(cfg['exclude'])}")
        self._thread = FetchThread(cfg)
        self._thread.log.connect(self.log)
        self._thread.finished_ok.connect(self._on_fetch_done)
        self._thread.start()

    def _on_fetch_done(self, stats):
        self._set_busy(False)
        if stats.get("ok"):
            if "added" in stats:
                sk = stats.get("skipped") or {}
                self.statLabel.setText(
                    f"✅ 新增 {stats['added']} 条 | 跳过: 非美女{sk.get('非美女',0)} 露骨{sk.get('露骨',0)} "
                    f"已存在{sk.get('已存在',0)} 无词{sk.get('无提示词',0)} | 香蕉库共 {stats['banana']} | 库总 {stats['total']}"
                )
            else:
                self.statLabel.setText("✅ 抓取完成(未能解析统计)")
        else:
            self.statLabel.setText("❌ 抓取失败: " + stats.get("err", "未知错误"))
        self.log("抓取结束")

    def _start_scan(self):
        if hasattr(self, "_sthread") and self._sthread.isRunning():
            return
        if hasattr(self, "_thread") and self._thread.isRunning():
            return
        ret = QMessageBox.question(
            self, "后期筛查",
            "用当前词表重筛库内 banana 条目。\n\n「是」= 仅报告疑似杂质(不删)\n「否」= 报告并一键删除(自动备份)\n「取消」= 退出",
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel, QMessageBox.Cancel)
        if ret == QMessageBox.Cancel:
            return
        clean = (ret == QMessageBox.No)
        cfg = self._collect_cfg()
        self._set_busy(True)
        self.log("=" * 30)
        self.log("后期筛查" + ("(清理模式)" if clean else "(仅报告)") + ": 用当前词表重筛库内 banana 条目...")
        self._sthread = ScanThread(cfg, clean=clean)
        self._sthread.log.connect(self.log)
        self._sthread.finished_ok.connect(self._on_scan_done)
        self._sthread.start()

    def _on_scan_done(self, stats):
        self._set_busy(False)
        if stats.get("ok"):
            mode = "清理" if stats.get("clean") else "报告"
            self.statLabel.setText(f"🔍 筛查({mode})完成: 疑似杂质 {stats.get('suspects', 0)} 条 | 库总 {stats.get('total', 0)}")
        else:
            self.statLabel.setText("❌ 筛查失败: " + stats.get("err", "未知错误"))
        self.log("筛查结束")

    def _start_single(self):
        url = self.singleEdit.text().strip()
        if not url:
            self.log("请先粘贴作品链接")
            return
        if hasattr(self, "_sthread") and self._sthread.isRunning():
            return
        self._set_busy(True, single=True)
        self.log("=" * 30)
        self.log("单条补抓: " + url)
        self._sthread = SingleThread(url, self._collect_cfg())
        self._sthread.log.connect(self.log)
        self._sthread.finished.connect(lambda: (self._set_busy(False), self.log("单条补抓结束")))
        self._sthread.start()

    def _set_busy(self, busy, single=False):
        self.fetchBtn.setEnabled(not busy)
        self.scanBtn.setEnabled(not busy)
        self.statusDot.setStyleSheet("color:#4e4;" if busy else "color:#e44;font-size:18px")
        if busy:
            self.statusDot.setToolTip("运行中")
        else:
            self.statusDot.setToolTip("空闲")

    def _export_log(self):
        fp, _ = QFileDialog.getSaveFileName(self, "导出日志txt", str(HERE / "抓取日志.txt"), "文本文件 (*.txt)")
        if fp:
            Path(fp).write_text(self.logView.toPlainText(), encoding="utf-8")
            self.log(f"日志已导出 -> {fp}")

    def log(self, msg):
        self.logView.appendPlainText(str(msg))

    def closeEvent(self, e):
        self._save_cfg()
        super().closeEvent(e)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())

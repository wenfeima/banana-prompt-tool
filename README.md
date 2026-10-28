# 🍌 Banana Prompt Tool 香蕉提示词工具链

localbanana.io 美女提示词的**增量抓取 + 严格过滤 + 后期筛查**本地工具链，面向 ComfyUI 工作流（CosplayPromptNode 缓存）。

## 功能

- **增量抓取**：抓取 localbanana 最新 N 页（默认 20 页），按作品 ID 去重合并入库，支持代理
- **双名单过滤**：白名单整词匹配（只收真人美女题材）+ 黑名单整词匹配（拦动漫/男性/广告/概念图/露骨），中英文都纳入判定
- **重复清洗**：自动去除 localbanana 作者原文的整段/整块重复
- **后期筛查**：用当前词表重筛库内全部条目，报告疑似杂质，可一键清理（自动备份）—— GUI 按钮或命令行均可
- **网页查看器**：本地服务模式浏览/搜索/删除/排序提示词库

## 文件说明

| 文件 | 用途 |
|---|---|
| `banana_gui.py` | PySide6 图形界面：抓取配置、词表可视化增删、页数自定义、后期筛查按钮 |
| `update_banana_daily.py` | 抓取核心：API 分页拉取、过滤判定 `is_beauty()`、去重清洗、合并入库（词表从 config.json 加载，单一来源） |
| `scan_cleanup.py` | 后期筛查 CLI：`--report` 仅报告 / `--clean` 清理并备份 |
| `serve_viewer.py` | 网页查看器服务（端口 8765），提供 `/api/delete` `/api/fetch` |
| `香蕉提示词库查看器.html` | 单文件查看器：列表/搜索/排序/分页/深浅色 |
| `config.json` | 词表唯一可编辑来源（白名单 include / 黑名单 exclude，格式"英文 中文"）、代理、页数、模式 |
| `香蕉提示词抓取器.exe` | Windows 启动器外壳（调 pythonw 跑 banana_gui.py） |
| `打开查看器.bat` | 一键启动查看器服务 |

## 使用

### GUI（推荐）
双击 `香蕉提示词抓取器.exe`（或 `python banana_gui.py`）：
1. 配置代理（默认 `http://127.0.0.1:10808`，v2rayN）与抓取页数（可手输任意页数）
2. 在词表区增删白/黑名单词（英文必填，中文仅注释）
3. 「🟢 开始抓取」→ 增量入库
4. 「🔍 后期筛查」→ 弹窗选「是」仅报告 / 「否」报告并一键清理（自动备份）

### 命令行
```bash
# 抓取（需代理时设置环境变量）
python update_banana_daily.py

# 后期筛查
python scan_cleanup.py --report   # 只报告疑似杂质
python scan_cleanup.py --clean    # 清理并备份(生成 deleted_banana_scan_时间戳.json)
```

### 查看器
双击 `打开查看器.bat`，浏览器访问 `http://127.0.0.1:8765`；也可直接打开 HTML 用本地文件模式（无删除/抓取按钮）。

## 过滤机制

- 严格模式：命中白名单任一 **且** 不命中黑名单 → 入库
- 白/黑名单均为**整词匹配**（`_has_word`，字母/数字/连字符两侧算边界），避免 `photorealistic` 误命中 `photo`、`cardigan` 误命中 `car`
- 词表**单一来源 = config.json**：GUI 编辑、抓取脚本、后期筛查全部从它读取，改了立即生效
- 黑名单同时覆盖英文与中文（动漫/男性/广告/概念/静物等类别）

## 数据

- 库文件：`prompt_cache.json`（顶层 `target_id → 条目`），个人数据不入库
- 备份：清理/修复前自动生成 `deleted_*` JSON，可手动恢复误删

## 已知坑

- 改 config.json 前先关闭 GUI（GUI 关窗会用内存词表覆盖 config）
- 中文场景词（客厅/毛衣/汽车等）**不要**加入黑名单——会误杀真人美女

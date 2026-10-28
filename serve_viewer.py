# -*- coding: utf-8 -*-
"""香蕉提示词库查看器 - 本地服务模式
双击「打开查看器.bat」启动: 自动打开浏览器并直接加载 prompt_cache.json,
刷新/重开不再需要手动选文件; 网页上的「抓取最新」按钮会调用抓取脚本。
"""
import http.server
import socketserver
import threading
import webbrowser
import os
import json
import re
import subprocess

PORT_START = 8765
PORT_TRY = 10
HERE = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(HERE, "香蕉提示词库查看器.html")
CACHE = r"L:\ComfyUI\ComfyUI\custom_nodes\CosplayPromptNode\prompt_cache.json"
PYTHON = r"L:\OpenClaw\ComfyUI\python_embeded\python.exe"
FETCH_SCRIPT = r"L:\ComfyUI\ComfyUI\custom_nodes\localbanana-prompts\update_banana_daily.py"
PROXY = "http://127.0.0.1:10808"


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            self._serve_file(HTML, "text/html; charset=utf-8")
        elif path == "/prompt_cache.json":
            self._serve_file(CACHE, "application/json; charset=utf-8")
        else:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()

    def do_POST(self):
        path = self.path.split("?")[0]
        if path == "/api/fetch":
            self._run_fetch()
        elif path == "/api/delete":
            self._delete_item()
        else:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()

    def _delete_item(self):
        """删除库中一条提示词: POST {"key":"缓存键"} → 原子写回"""
        body = b""
        try:
            n = int(self.headers.get("Content-Length") or 0)
            if n > 0:
                body = self.rfile.read(n)
            req = json.loads(body.decode("utf-8")) if body else {}
            key = (req.get("key") or "").strip()
        except Exception as e:
            self._json({"ok": False, "error": "请求解析失败: " + str(e)})
            return
        if not key:
            self._json({"ok": False, "error": "缺少 key"})
            return
        try:
            with open(CACHE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict) or key not in data:
                self._json({"ok": False, "error": "未找到该条目: " + key})
                return
            del data[key]
            tmp = CACHE + "." + str(os.getpid()) + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            os.replace(tmp, CACHE)
            self._json({"ok": True, "key": key, "total": len(data)})
        except Exception as e:
            self._json({"ok": False, "error": "删除失败: " + str(e)})

    def _json(self, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _run_fetch(self):
        env = dict(os.environ)
        env["HTTPS_PROXY"] = PROXY
        env["HTTP_PROXY"] = PROXY
        try:
            r = subprocess.run(
                [PYTHON, FETCH_SCRIPT],
                capture_output=True, text=True, timeout=600,
                env=env, encoding="utf-8", errors="replace",
            )
            out = (r.stdout or "") + (r.stderr or "")
            ok = (r.returncode == 0)
        except Exception as e:
            ok = False
            out = "抓取执行异常: " + str(e)
        # 从脚本输出解析结构化数字(新增/香蕉库总数/库总数)
        added = skipped = banana_total = total = None
        m = re.search(r"新增\s+(\d+)\s+条.*?香蕉库共\s+(\d+)\s+条.*?库总\s+(\d+)\s+条", out)
        if m:
            added, banana_total, total = int(m.group(1)), int(m.group(2)), int(m.group(3))
        m2 = re.search(r"跳过\s+(\{.*?\})", out)
        if m2:
            skipped = m2.group(1)
        body = json.dumps({
            "ok": ok, "output": out,
            "added": added, "banana_total": banana_total,
            "total": total, "skipped": skipped,
        }, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_file(self, fp, ctype):
        try:
            with open(fp, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
        except FileNotFoundError:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()

    def log_message(self, *args):
        pass


def main():
    server = None
    for port in range(PORT_START, PORT_START + PORT_TRY):
        try:
            server = socketserver.TCPServer(("127.0.0.1", port), Handler)
            break
        except OSError:
            continue
    if server is None:
        print(f"端口 {PORT_START}-{PORT_START+PORT_TRY-1} 都被占用, 启动失败")
        input("按回车退出...")
        return
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print("香蕉提示词库查看器: " + url)
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

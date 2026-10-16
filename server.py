"""
本機模式：在自己電腦上同時提供網頁與 /api。

    pip install -r requirements.txt
    python server.py            # 開啟 http://localhost:8000
    python server.py 9000       # 改用其他 port

在家用網路執行時，YouTube 看到的是一般使用者的 IP，不會像 Vercel 等雲端主機那樣被封鎖，
所以自動搜尋字幕最穩定。
"""
from http.server import ThreadingHTTPServer
from urllib.parse import urlparse
import importlib.util
import os
import sys
import webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))

_spec = importlib.util.spec_from_file_location("api_index", os.path.join(ROOT, "api", "index.py"))
api = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(api)


class LocalHandler(api.handler):
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api" or path.startswith("/api/"):
            return super().do_GET()
        if path in ("/", "/index.html"):
            with open(os.path.join(ROOT, "index.html"), "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_error(404)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("PORT", 8000))
    server = ThreadingHTTPServer(("127.0.0.1", port), LocalHandler)
    url = f"http://localhost:{port}"
    print(f"HANGUL MASTER 本機模式已啟動：{url}（Ctrl+C 結束）")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

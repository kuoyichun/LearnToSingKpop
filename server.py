"""
本機模式：在自己電腦上同時提供網頁與 /api。

    pip install -r requirements.txt
    python server.py            # 開啟 http://localhost:8000
    python server.py 9000       # 改用其他 port
    python server.py --lan      # 讓同一個 Wi-Fi 的手機 / 平板也能連進來

在家用網路執行時，YouTube 看到的是一般使用者的 IP，不會像 Vercel 等雲端主機那樣被封鎖，
所以自動搜尋字幕最穩定。
"""
from http.server import ThreadingHTTPServer
from urllib.parse import urlparse
import importlib.util
import os
import socket
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


def lan_ip():
    """找出這台電腦在家用網路裡的 IP（UDP connect 不會真的送出封包）。"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return None


def main():
    args = sys.argv[1:]
    lan = "--lan" in args
    ports = [a for a in args if a.isdigit()]
    port = int(ports[0]) if ports else int(os.environ.get("PORT", 8000))
    server = ThreadingHTTPServer(("0.0.0.0" if lan else "127.0.0.1", port), LocalHandler)
    url = f"http://localhost:{port}"
    print(f"HANGUL MASTER 本機模式已啟動：{url}（Ctrl+C 結束）")
    if lan:
        ip = lan_ip()
        if ip:
            print(f"手機 / 平板（連同一個 Wi-Fi）請開：http://{ip}:{port}")
        else:
            print("找不到這台電腦的區網 IP，請到網路設定查看本機 IP 後，用 http://<IP>:%d 開啟" % port)
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

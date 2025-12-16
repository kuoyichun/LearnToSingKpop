from http.server import BaseHTTPRequestHandler
import json
import sys
import os

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        debug_info = {}
        
        # 1. 嘗試匯入並檢查來源
        try:
            import youtube_transcript_api
            debug_info['status'] = "Imported"
            debug_info['file_location'] = getattr(youtube_transcript_api, '__file__', 'Unknown')
            debug_info['dir_content'] = dir(youtube_transcript_api)
        except ImportError as e:
            debug_info['status'] = "ImportError"
            debug_info['error'] = str(e)
            
        # 2. 列出 api 資料夾底下的所有檔案
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            debug_info['files_in_api_folder'] = os.listdir(current_dir)
        except Exception:
            debug_info['files_in_api_folder'] = "Error reading dir"

        # 回傳診斷報告
        self.wfile.write(json.dumps(debug_info, indent=2).encode('utf-8'))

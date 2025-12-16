from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json

# 嘗試匯入庫
try:
    from youtube_transcript_api import YouTubeTranscriptApi
except ImportError:
    YouTubeTranscriptApi = None

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # 1. 解析 URL 參數
        query = urlparse(self.path).query
        params = parse_qs(query)
        video_id = params.get('videoId', [None])[0]

        # 設定 CORS 標頭 (允許網頁呼叫)
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        # 2. 檢查是否有 videoId
        if not video_id:
            self.wfile.write(json.dumps({"error": "Missing videoId parameter"}).encode('utf-8'))
            return

        # 3. 檢查庫是否安裝
        if YouTubeTranscriptApi is None:
            self.wfile.write(json.dumps({"error": "Server Error: Library not installed."}).encode('utf-8'))
            return

        try:
            # 4. 真正去抓字幕 (優先順序：韓 -> 英 -> 中)
            transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['ko', 'en', 'zh-Hant'])
            
            # 成功！回傳 List (陣列)
            self.wfile.write(json.dumps(transcript).encode('utf-8'))
            
        except Exception as e:
            # 失敗，回傳錯誤訊息
            error_msg = str(e)
            if "TranscriptsDisabled" in error_msg or "NoTranscriptFound" in error_msg:
                error_msg = "抱歉，這部影片沒有公開的字幕 (CC)。"
            
            self.wfile.write(json.dumps({"error": error_msg}).encode('utf-8'))

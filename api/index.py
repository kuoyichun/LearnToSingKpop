from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json

# 確保引用的是外部庫，而不是本地檔案
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

        # 設定回應標頭 (CORS)
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        # 2. 檢查 Video ID
        if not video_id:
            response_data = {"error": "Missing videoId parameter"}
            self.wfile.write(json.dumps(response_data).encode('utf-8'))
            return

        # 3. 檢查庫是否安裝成功
        if YouTubeTranscriptApi is None:
            response_data = {"error": "Library not installed. Check requirements.txt"}
            self.wfile.write(json.dumps(response_data).encode('utf-8'))
            return

        try:
            # 4. 呼叫 YouTube API
            # 使用 list 獲取字幕 (優先抓韓文、英文、中文)
            transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['ko', 'en', 'zh-Hant'])
            
            # 回傳成功資料
            self.wfile.write(json.dumps(transcript).encode('utf-8'))
            
        except Exception as e:
            # 5. 捕捉並回傳錯誤 (包含詳細錯誤類型，方便除錯)
            error_msg = f"{type(e).__name__}: {str(e)}"
            
            # 如果是找不到字幕，給予友善提示
            if "TranscriptsDisabled" in error_msg or "NoTranscriptFound" in error_msg:
                error_msg = "This video does not have captions/subtitles available."

            response_data = {"error": error_msg}
            self.wfile.write(json.dumps(response_data).encode('utf-8'))

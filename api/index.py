from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
from youtube_transcript_api import YouTubeTranscriptApi

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # 1. 解析 URL 參數 (取得 videoId)
        query = urlparse(self.path).query
        params = parse_qs(query)
        video_id = params.get('videoId', [None])[0]

        # 設定回應標頭 (CORS) - 讓您的 GitHub Pages 可以呼叫此 API
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*') # 允許所有網域呼叫
        self.end_headers()

        response_data = {}

        if not video_id:
            response_data = {"error": "Missing videoId parameter"}
            self.wfile.write(json.dumps(response_data).encode('utf-8'))
            return

        try:
            # 2. 呼叫 YouTube API 抓取字幕
            # 優先順序：韓文 -> 英文 -> 中文
            transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['ko', 'en', 'zh-Hant'])
            
            # 3. 成功抓取，回傳資料
            self.wfile.write(json.dumps(transcript).encode('utf-8'))
            
        except Exception as e:
            # 4. 發生錯誤 (例如無字幕)
            response_data = {"error": str(e)}
            self.wfile.write(json.dumps(response_data).encode('utf-8'))

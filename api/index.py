from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json

try:
    from youtube_transcript_api import YouTubeTranscriptApi
except ImportError:
    YouTubeTranscriptApi = None

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        query = urlparse(self.path).query
        params = parse_qs(query)
        video_id = params.get('videoId', [None])[0]

        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        if not video_id:
            self.wfile.write(json.dumps({"error": "No videoId"}).encode('utf-8'))
            return

        if YouTubeTranscriptApi is None:
            self.wfile.write(json.dumps({"error": "Library not installed."}).encode('utf-8'))
            return

        try:
            # === 強力模式：列出所有可用字幕，然後挑選 ===
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            
            # 1. 優先尋找韓文 (手寫或自動皆可)
            try:
                # 嘗試尋找韓文、英文、中文的各種變體
                transcript = transcript_list.find_transcript(['ko', 'ko-KR', 'en', 'en-US', 'zh-Hant', 'zh-TW'])
            except:
                # 2. 如果上面都找不到，就隨便抓第一個可用的 (例如自動產生的字幕)
                # 這能保證我們至少抓到一點東西，而不是報錯
                transcript = next(iter(transcript_list))

            # 抓取資料
            final_data = transcript.fetch()
            
            self.wfile.write(json.dumps(final_data).encode('utf-8'))
            
        except Exception as e:
            error_msg = str(e)
            if "TranscriptsDisabled" in error_msg:
                error_msg = "YouTube 拒絕提供此影片的字幕 (可能是因為版權或 Vercel IP 被限制)。"
            elif "NoTranscriptFound" in error_msg:
                error_msg = "此影片完全沒有任何字幕軌。"
            
            self.wfile.write(json.dumps({"error": error_msg}).encode('utf-8'))

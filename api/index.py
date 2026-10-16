"""
HANGUL MASTER 後端（Vercel Serverless 與本機 server.py 共用）

GET /api?q=歌名 歌手          搜尋 YouTube，檢查前幾名影片的韓文字幕，回傳最適合的一支與字幕
GET /api?q=<YouTube 網址>     直接取得該影片的韓文字幕
GET /api?videoId=XXXXXXXXXXX  直接取得該影片的韓文字幕
GET /api?videoId=XXXXXXXXXXX&lrc=123  用 LRCLIB 第 123 號歌詞搭配該影片（分享連結用）

影片有人工中文字幕時，會依時間軸對齊到每一句韓文（line.zh），前端就不必再用機器翻譯。
YouTube 前幾名都沒有韓文字幕時，改從 LRCLIB（lrclib.net）找有時間軸的同步歌詞。

YouTube 會封鎖雲端主機（Vercel / AWS 等）的 IP。若部署在 Vercel 上一直出現「被 YouTube 擋下」，
請改用本機模式（python server.py），或設定以下其中一組環境變數讓請求走 Proxy：
  WEBSHARE_PROXY_USERNAME + WEBSHARE_PROXY_PASSWORD   Webshare「Residential」輪替住宅 Proxy
  YT_PROXY_URL                                       其他 Proxy，例如 http://user:pass@host:port
"""
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from concurrent.futures import ThreadPoolExecutor
import json
import os
import re

import requests

try:
    from youtube_transcript_api import (
        YouTubeTranscriptApi,
        RequestBlocked,
        TranscriptsDisabled,
        VideoUnavailable,
        VideoUnplayable,
        AgeRestricted,
        InvalidVideoId,
        PoTokenRequired,
    )
    from youtube_transcript_api.proxies import GenericProxyConfig, WebshareProxyConfig
except ImportError:
    YouTubeTranscriptApi = None

DEFAULT_LIMIT = 8          # 預設檢查前幾支影片
MAX_LIMIT = 15
MAX_FETCH_ATTEMPTS = 5     # 最多實際下載幾條字幕來驗證內容
REQUEST_TIMEOUT = 12
MIN_TRANSLATION_COVERAGE = 0.5  # 中文字幕至少要對齊到一半的韓文句子才採用

SEARCH_API_URL = "https://www.youtube.com/youtubei/v1/search?prettyPrint=false"
SEARCH_PAGE_URL = "https://www.youtube.com/results"
SEARCH_CLIENT = {"clientName": "WEB", "clientVersion": "2.20260801.00.00", "hl": "zh-TW", "gl": "TW"}
VIDEOS_ONLY = "EgIQAQ%3D%3D"   # 搜尋篩選：只要「影片」
LRCLIB_API_URL = "https://lrclib.net/api"
LRCLIB_UA = "HangulMaster (https://github.com/kuoyichun/LearnToSingKpop)"
# 中文字幕優先順序：繁體 → 未標示 → 簡體
ZH_PRIORITY = ["zh-tw", "zh-hant", "zh-hant-tw", "zh-hk", "zh-hant-hk", "zh", "zh-hans", "zh-cn", "zh-sg"]
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)

VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
URL_ID_RE = re.compile(r"(?:youtu\.be/|/shorts/|/embed/|/live/|/v/|[?&]v=)([A-Za-z0-9_-]{11})")
HANGUL_RE = re.compile(r"[가-힣]")
LETTER_RE = re.compile(r"[A-Za-zㄱ-ㆎ가-힣぀-ヿ一-鿿]")
# 字幕中的非歌詞雜訊：[음악]、[Music]、(박수)、【間奏】、♪、LRC 逐字時間 <00:12.34> 等
NOISE_RE = re.compile(
    r"\[[^\]]*\]|【[^】]*】|<\d+:\d+(?:\.\d+)?>|"
    r"[(（][^)）]*(?:음악|박수|웃음|音樂|音乐|music|applause|laugh)[^)）]*[)）]|[♪♫♬♩]",
    re.IGNORECASE,
)
LRC_TIME_RE = re.compile(r"\[(\d+):(\d+(?:\.\d+)?)\]")
# 標題含這些字的通常不是歌曲本身（除非使用者搜尋時自己有打）
OFF_TOPIC_RE = re.compile(
    r"reaction|리액션|teaser|티저|behind|비하인드|making|메이킹|interview|인터뷰|"
    r"#shorts|vlog|브이로그|challenge|챌린지|playlist|플레이리스트|1\s*hour|1시간|"
    r"tutorial|lesson|piano|피아노|instrumental|\binst\b|\bmr\b|karaoke|노래방|cover|커버",
    re.IGNORECASE,
)

STATUS_RANK = {"manual": 0, "auto": 1}


class TimeoutSession(requests.Session):
    """requests 預設沒有逾時，避免單一請求卡住整個函式。"""

    def request(self, *args, **kwargs):
        kwargs.setdefault("timeout", REQUEST_TIMEOUT)
        return super().request(*args, **kwargs)


def get_proxy_config():
    user = os.environ.get("WEBSHARE_PROXY_USERNAME")
    password = os.environ.get("WEBSHARE_PROXY_PASSWORD")
    if user and password:
        return WebshareProxyConfig(proxy_username=user, proxy_password=password)
    url = os.environ.get("YT_PROXY_URL")
    if url:
        return GenericProxyConfig(http_url=url, https_url=url)
    return None


def new_transcript_api():
    # YouTubeTranscriptApi 不是 thread-safe，每個執行緒各建一個
    return YouTubeTranscriptApi(proxy_config=get_proxy_config(), http_client=TimeoutSession())


def extract_video_id(text, allow_bare_id=False):
    """從 YouTube 網址取出影片 ID；allow_bare_id 時也接受單純的 11 碼 ID。"""
    text = (text or "").strip()
    if allow_bare_id and VIDEO_ID_RE.match(text):
        return text
    m = URL_ID_RE.search(text) if "youtu" in text else None
    return m.group(1) if m else None


# ---------------------------------------------------------------- YouTube 搜尋

def text_of(node):
    if not node:
        return ""
    if isinstance(node, str):
        return node
    if "simpleText" in node:
        return node["simpleText"]
    if "runs" in node:
        return "".join(run.get("text", "") for run in node["runs"])
    return node.get("content", "")


def iter_nodes(node, key):
    """依文件順序找出所有 key 對應的物件（YouTube 的 JSON 結構常改，用遞迴找比較耐用）。"""
    if isinstance(node, dict):
        for k, v in node.items():
            if k == key:
                yield v
            else:
                yield from iter_nodes(v, key)
    elif isinstance(node, list):
        for item in node:
            yield from iter_nodes(item, key)


def parse_video_renderer(v):
    video_id = v.get("videoId")
    if not video_id:
        return None
    return {
        "videoId": video_id,
        "title": text_of(v.get("title")),
        "channel": text_of(v.get("ownerText") or v.get("longBylineText") or v.get("shortBylineText")),
        "duration": text_of(v.get("lengthText")),
        "views": text_of(v.get("shortViewCountText") or v.get("viewCountText")),
    }


def parse_lockup(lockup):
    if lockup.get("contentType") != "LOCKUP_CONTENT_TYPE_VIDEO" or not lockup.get("contentId"):
        return None
    meta = lockup.get("metadata", {}).get("lockupMetadataViewModel", {})
    rows = (
        meta.get("metadata", {}).get("contentMetadataViewModel", {}).get("metadataRows", [])
    )
    parts = [text_of(p.get("text")) for row in rows for p in row.get("metadataParts", [])]
    duration = next(
        (
            text_of(b.get("text"))
            for b in iter_nodes(lockup.get("contentImage", {}), "thumbnailBadgeViewModel")
            if re.match(r"^\d+:\d{2}(:\d{2})?$", text_of(b.get("text")))
        ),
        "",
    )
    return {
        "videoId": lockup["contentId"],
        "title": text_of(meta.get("title")),
        "channel": parts[0] if parts else "",
        "duration": duration,
        "views": parts[1] if len(parts) > 1 else "",
    }


def extract_videos(data):
    videos, seen = [], set()
    for key, parser in (("videoRenderer", parse_video_renderer), ("lockupViewModel", parse_lockup)):
        for node in iter_nodes(data, key):
            video = parser(node) if isinstance(node, dict) else None
            if video and video["videoId"] not in seen:
                seen.add(video["videoId"])
                videos.append(video)
        if videos:
            break
    return videos


def extract_initial_data(html):
    m = re.search(r'ytInitialData"?\]?\s*=\s*', html)
    if not m:
        return None
    start = html.find("{", m.end())
    data, _ = json.JSONDecoder().raw_decode(html, start)
    return data


def search_youtube(query, limit):
    session = TimeoutSession()
    session.headers.update({"User-Agent": BROWSER_UA, "Accept-Language": "zh-TW,zh;q=0.9,ko;q=0.8,en;q=0.7"})
    session.cookies.set("SOCS", "CAI", domain=".youtube.com")  # 略過歐盟 cookie 同意頁
    proxy = get_proxy_config()
    if proxy:
        session.proxies = proxy.to_requests_dict()

    videos, first_error = [], None
    try:  # 1) InnerTube 搜尋 API
        res = session.post(
            SEARCH_API_URL,
            json={"context": {"client": SEARCH_CLIENT}, "query": query, "params": VIDEOS_ONLY},
        )
        res.raise_for_status()
        videos = extract_videos(res.json())
    except Exception as e:
        first_error = e
    if not videos:  # 2) 退而求其次：解析搜尋結果網頁裡的 ytInitialData
        try:
            res = session.get(SEARCH_PAGE_URL, params={"search_query": query, "sp": VIDEOS_ONLY})
            res.raise_for_status()
            videos = extract_videos(extract_initial_data(res.text) or {})
        except Exception as e:
            raise RuntimeError(str(first_error or e)) from e
    return videos[:limit]


# ---------------------------------------------------------------- 字幕

def probe_video(video_id):
    """列出影片字幕軌，找出韓文人工字幕 / 韓文自動字幕。"""
    try:
        transcript_list = new_transcript_api().list(video_id)
    except RequestBlocked:
        return {"status": "blocked", "note": "YouTube 封鎖了伺服器 IP"}
    except TranscriptsDisabled:
        return {"status": "none", "note": "此影片沒有字幕"}
    except (VideoUnavailable, VideoUnplayable, AgeRestricted, InvalidVideoId) as e:
        return {"status": "unavailable", "note": type(e).__name__}
    except Exception as e:
        return {"status": "error", "note": f"{type(e).__name__}: {e}"[:200]}

    manual = auto = zh = None
    for transcript in transcript_list:
        code = transcript.language_code.lower()
        if code.split("-")[0] == "zh" and not transcript.is_generated:
            if zh is None or zh_rank(code) < zh_rank(zh.language_code.lower()):
                zh = transcript
        if code.split("-")[0] != "ko":
            continue
        if transcript.is_generated:
            auto = auto or transcript
        else:
            manual = manual or transcript
    if manual:
        return {"status": "manual", "manual": manual, "auto": auto, "zh": zh}
    if auto:
        return {"status": "auto", "auto": auto, "zh": zh}
    return {"status": "none", "note": "沒有韓文字幕軌"}


def zh_rank(code):
    return ZH_PRIORITY.index(code) if code in ZH_PRIORITY else len(ZH_PRIORITY)


def clean_lines(snippets):
    lines = []
    for s in snippets:
        text = NOISE_RE.sub(" ", s["text"].replace("\n", " "))
        text = re.sub(r"\s+", " ", text).strip(" -–—")
        if text and LETTER_RE.search(text):
            lines.append({"start": round(s["start"], 2), "duration": round(s["duration"], 2), "text": text})
    return lines


def is_korean_lyrics(lines):
    if len(lines) < 4:
        return False, "字幕內容太少"
    hangul_lines = sum(1 for line in lines if HANGUL_RE.search(line["text"]))
    if hangul_lines / len(lines) < 0.2:
        return False, "內容不是韓文"
    return True, None


def fetch_track(video_id, transcript):
    """下載字幕並確認內容真的是韓文歌詞；失敗時回傳 (None, 原因)。"""
    try:
        fetched = transcript.fetch()
    except PoTokenRequired:
        return None, "YouTube 要求 PO Token，無法下載"
    except RequestBlocked:
        return None, "YouTube 封鎖了伺服器 IP"
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"[:200]

    lines = clean_lines(fetched.to_raw_data())
    ok, reason = is_korean_lyrics(lines)
    if not ok:
        return None, reason if reason == "字幕內容太少" else "字幕標成韓文，但內容不是韓文"
    return {
        "videoId": video_id,
        "source": "youtube",
        "language": transcript.language,
        "languageCode": transcript.language_code,
        "isGenerated": transcript.is_generated,
        "lines": lines,
    }, None


def align_translation(lines, zh_lines):
    """把中文字幕依時間重疊度分配到韓文句子；回傳每句的中文（對不到的是 None）。"""
    spans = []
    for i, line in enumerate(lines):
        start = line["start"]
        end = start + (line.get("duration") or 0)
        if i + 1 < len(lines) and (end <= start or end > lines[i + 1]["start"]):
            end = lines[i + 1]["start"]
        spans.append((start, end if end > start else start + 3))

    assigned = [[] for _ in lines]
    for z in zh_lines:
        a, b = z["start"], z["start"] + max(z.get("duration") or 0, 0.5)
        best, best_overlap = None, 0.0
        for i, (s, e) in enumerate(spans):
            overlap = min(b, e) - max(a, s)
            if overlap > best_overlap:
                best, best_overlap = i, overlap
        if best is not None and best_overlap >= 0.3 * (b - a):
            assigned[best].append(z["text"])
    return [" ".join(dict.fromkeys(texts)) if texts else None for texts in assigned]


def attach_translation(transcript, zh_track):
    """影片有人工中文字幕時，對齊後放進每一句的 zh 欄位。"""
    if not zh_track:
        return
    try:
        zh_lines = clean_lines(zh_track.fetch().to_raw_data())
    except Exception:
        return
    aligned = align_translation(transcript["lines"], zh_lines)
    coverage = sum(1 for z in aligned if z) / len(aligned) if aligned else 0
    if coverage < MIN_TRANSLATION_COVERAGE:
        return
    for line, zh in zip(transcript["lines"], aligned):
        if zh:
            line["zh"] = zh
    transcript["translation"] = {
        "language": zh_track.language,
        "languageCode": zh_track.language_code,
        "coverage": round(coverage, 2),
    }


# ---------------------------------------------------------------- LRCLIB 同步歌詞（備援）

def lrclib_session():
    session = TimeoutSession()
    session.headers.update({"User-Agent": LRCLIB_UA})
    return session


def parse_lrc(synced):
    entries = []
    for raw in (synced or "").splitlines():
        times = LRC_TIME_RE.findall(raw)
        text = LRC_TIME_RE.sub("", raw).strip()
        entries.extend((int(m) * 60 + float(sec), text) for m, sec in times)
    entries.sort(key=lambda e: e[0])
    snippets = []
    for i, (start, text) in enumerate(entries):
        nxt = entries[i + 1][0] if i + 1 < len(entries) else start + 5
        snippets.append({"text": text, "start": start, "duration": min(max(nxt - start, 0.5), 10)})
    return clean_lines(snippets)  # 空白行（間奏）只用來決定上一句的結束時間


def lrc_transcript(record, video_id):
    lines = parse_lrc(record.get("syncedLyrics"))
    if record.get("instrumental") or not is_korean_lyrics(lines)[0]:
        return None
    return {
        "videoId": video_id,
        "source": "lrclib",
        "lrclibId": record.get("id"),
        "song": " - ".join(x for x in (record.get("artistName"), record.get("trackName")) if x),
        "songDuration": record.get("duration"),
        "language": "LRCLIB",
        "languageCode": "ko",
        "isGenerated": False,
        "lines": lines,
    }


def search_lrclib(query):
    """回傳第一筆有韓文同步歌詞的 LRCLIB 紀錄；找不到或連不上回傳 None。"""
    try:
        res = lrclib_session().get(f"{LRCLIB_API_URL}/search", params={"q": query})
        res.raise_for_status()
        records = res.json()
    except Exception:
        return None
    for record in records[:10] if isinstance(records, list) else []:
        if lrc_transcript(record, ""):
            return record
    return None


def pick_video_for_lrc(videos, query, song_duration):
    """歌詞時間軸是照音源做的，優先挑長度跟音源差不多的影片（官方音源、無前奏的 MV）。"""
    def key(item):
        rank, video = item
        seconds = duration_seconds(video.get("duration"))
        close = bool(song_duration) and seconds is not None and abs(seconds - song_duration) <= 4
        return (video["status"] == "unavailable", is_off_topic(video, query), not close, rank)
    return min(enumerate(videos), key=key)[1]


def handle_lrc(video_id, lrc_id):
    try:
        res = lrclib_session().get(f"{LRCLIB_API_URL}/get/{lrc_id}")
        res.raise_for_status()
        transcript = lrc_transcript(res.json(), video_id)
    except Exception as e:
        return 502, {"code": "lrclib_failed", "error": f"LRCLIB 讀取失敗：{e}"}
    if not transcript:
        return 404, {"code": "not_found", "error": "LRCLIB 這筆歌詞沒有可用的韓文同步歌詞。"}
    return 200, {"videoId": video_id, "transcript": transcript}


def duration_seconds(text):
    parts = [int(p) for p in re.findall(r"\d+", text or "")]
    total = 0
    for p in parts:
        total = total * 60 + p
    return total if parts else None


def is_off_topic(video, query):
    words = {m.group(0).lower() for m in OFF_TOPIC_RE.finditer(video["title"])}
    if any(w not in query.lower() for w in words):
        return True
    seconds = duration_seconds(video.get("duration"))
    return seconds is not None and not (60 <= seconds <= 600)


def handle_search(query, limit):
    try:
        videos = search_youtube(query, limit)
    except Exception as e:
        return 502, {"code": "search_failed", "error": f"YouTube 搜尋失敗：{e}"}
    if not videos:
        return 404, {"code": "not_found", "error": "YouTube 找不到相關影片，請換個關鍵字。", "candidates": []}

    with ThreadPoolExecutor(max_workers=len(videos)) as pool:
        probes = list(pool.map(lambda v: probe_video(v["videoId"]), videos))

    # 排序：與歌曲無關的影片放最後 → 人工字幕優先於自動字幕 → 依 YouTube 搜尋排名
    options = []
    for rank, (video, probe) in enumerate(zip(videos, probes)):
        video["thumbnail"] = f"https://i.ytimg.com/vi/{video['videoId']}/mqdefault.jpg"
        video["status"], video["note"] = probe["status"], probe.get("note", "")
        for kind in ("manual", "auto"):
            if probe.get(kind):
                options.append((is_off_topic(video, query), STATUS_RANK[kind], rank, video, probe[kind]))
    options.sort(key=lambda o: o[:3])

    selected = None
    for _, _, _, video, track in options[:MAX_FETCH_ATTEMPTS]:
        transcript, reason = fetch_track(video["videoId"], track)
        if transcript:
            attach_translation(transcript, probes[videos.index(video)].get("zh"))
            selected = transcript
            video["status"] = "auto" if track.is_generated else "manual"
            break
        has_auto = any(o[3] is video and o[4].is_generated for o in options)
        video["status"] = "auto" if not track.is_generated and has_auto else "none"
        video["note"] = reason

    result = {"query": query, "candidates": videos}
    if not selected:  # YouTube 都沒有韓文字幕 → 改找 LRCLIB 同步歌詞
        record = search_lrclib(query)
        if record:
            video = pick_video_for_lrc(videos, query, record.get("duration"))
            selected = lrc_transcript(record, video["videoId"])
    if selected:
        result.update(selected=selected["videoId"], transcript=selected)
        return 200, result
    if all(p["status"] == "blocked" for p in probes):
        result.update(
            code="blocked",
            error="YouTube 封鎖了伺服器的 IP，無法讀取字幕。請改用本機模式（python server.py）或設定 Proxy。",
        )
        return 502, result
    result.update(
        code="not_found",
        error=f"無法取得：前 {len(videos)} 個搜尋結果都沒有可用的韓文字幕，LRCLIB 也找不到同步歌詞。",
    )
    return 404, result


def handle_video(video_id):
    probe = probe_video(video_id)
    if probe["status"] == "blocked":
        return 502, {"code": "blocked", "error": "YouTube 封鎖了伺服器的 IP，無法讀取字幕。請改用本機模式（python server.py）或設定 Proxy。"}
    reason = probe.get("note", "")
    for kind in ("manual", "auto"):
        if probe.get(kind):
            transcript, reason = fetch_track(video_id, probe[kind])
            if transcript:
                attach_translation(transcript, probe.get("zh"))
                return 200, {"videoId": video_id, "transcript": transcript}
    return 404, {"code": "not_found", "error": f"無法取得此影片的韓文字幕（{reason}）。"}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        params = parse_qs(urlparse(self.path).query)
        query = (params.get("q") or [""])[0].strip()
        video_id = (params.get("videoId") or [""])[0].strip()
        lrc_id = (params.get("lrc") or [""])[0].strip()
        try:
            limit = min(max(int((params.get("limit") or [DEFAULT_LIMIT])[0]), 1), MAX_LIMIT)
        except ValueError:
            limit = DEFAULT_LIMIT

        if YouTubeTranscriptApi is None:
            status, body = 500, {"code": "server_error", "error": "伺服器缺少 youtube-transcript-api 套件。"}
        elif video_id:
            target = extract_video_id(video_id, allow_bare_id=True)
            if target and lrc_id.isdigit():
                status, body = handle_lrc(target, lrc_id)
            elif target:
                status, body = handle_video(target)
            else:
                status, body = 400, {"code": "bad_request", "error": "videoId 格式不正確。"}
        elif query:
            target = extract_video_id(query)  # 搜尋框直接貼 YouTube 網址也可以
            status, body = handle_video(target) if target else handle_search(query, limit)
        else:
            status, body = 400, {"code": "bad_request", "error": "請提供 q（歌名 / 歌手）或 videoId。"}

        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        # 成功的結果讓 Vercel CDN 快取 6 小時，同一首歌再查就不用再打 YouTube
        self.send_header("Cache-Control", "public, s-maxage=21600" if status == 200 else "no-store")
        self.end_headers()
        self.wfile.write(payload)

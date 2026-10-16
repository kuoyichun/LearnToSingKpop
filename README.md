# HANGUL MASTER

輸入「歌名 + 歌手」，自動搜尋 YouTube、找出有韓文字幕的影片，逐句顯示韓文 / 拼音 / 中文翻譯，跟著影片一起學唱。

## 使用方式

1. 在搜尋框輸入歌名與歌手（例如 `Supernova aespa`），也可以直接貼 YouTube 網址。
2. 系統會檢查前 8 個搜尋結果，優先選「人工韓文字幕」，沒有才用「YouTube 自動字幕」。
3. 左側清單可切換其他也有字幕的影片；全部都沒有時會顯示「無法取得」。
4. 找不到字幕時，仍可展開「手動模式」自己貼網址與轉錄稿。

## 執行方式

### 本機模式（最穩定，推薦）

YouTube 會封鎖雲端主機的 IP，在自己電腦上跑最不容易失敗：

```bash
pip install -r requirements.txt
python server.py        # 自動開啟 http://localhost:8000
```

### Vercel

直接部署即可（`/api` 由 `api/index.py` 提供）。若搜尋時一直出現「被 YouTube 擋下」，
代表 Vercel 的 IP 被封鎖，需要在 Vercel 專案的 Environment Variables 設定 Proxy：

| 變數 | 說明 |
| --- | --- |
| `WEBSHARE_PROXY_USERNAME` / `WEBSHARE_PROXY_PASSWORD` | [Webshare](https://www.webshare.io/) 的「Residential」輪替住宅 Proxy |
| `YT_PROXY_URL` | 其他 Proxy，例如 `http://user:pass@host:port` |

## API

- `GET /api?q=歌名 歌手`：搜尋並回傳候選影片（含字幕狀態）與最佳影片的字幕
- `GET /api?videoId=XXXXXXXXXXX`：取得指定影片的韓文字幕

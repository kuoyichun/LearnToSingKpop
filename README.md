# HANGUL MASTER

輸入「歌名 + 歌手」，自動搜尋 YouTube、找出有韓文字幕的影片，逐句顯示韓文 / 拼音 / 中文翻譯，跟著影片一起學唱。

## 使用方式

1. 在搜尋框輸入歌名與歌手（例如 `Supernova aespa`），也可以直接貼 YouTube 網址。
2. 系統會檢查前 8 個搜尋結果，優先選「人工韓文字幕」，沒有才用「YouTube 自動字幕」；
   都沒有時改找 [LRCLIB](https://lrclib.net) 的同步歌詞，再找不到才顯示「無法取得」。
3. 影片若有人工中文字幕，會直接用官方翻譯；對不上的句子才用機器翻譯。
4. 左側清單可切換其他也有字幕的影片；找不到字幕時仍可展開「手動模式」自己貼轉錄稿。

## 練習功能

| 功能 | 說明 |
| --- | --- |
| 速度 | 0.5× / 0.75× / 1× 慢速練唱 |
| 單句重複 | 按 🔊 或 `R` 播放單句時重複 1 / 2 / 3 / 5 次或無限 |
| A-B 循環 | 唱到開始句按 `A`、結束句按 `B`，`Esc` 取消 |
| 時間軸微調 | 字幕比歌聲早就按 `+`、晚就按 `−`（每次 0.5 秒，會記住） |
| 背歌詞模式 | 遮住韓文 / 拼音 / 中文，點歌詞文字可以偷看 |
| 快捷鍵 | 空白鍵 播放/暫停、`←` `→` 上/下一句 |
| 學習紀錄 | 學過的歌（含翻譯）存在瀏覽器，下次點一下就開，不用再連 YouTube |
| 分享連結 | 網址帶 `?v=影片ID`（LRCLIB 歌詞另帶 `&lrc=`、微調帶 `&offset=`）；`?q=歌名` 可直接搜尋 |

手機版的影片會固定在畫面上方，歌詞在下面捲動。

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
- `GET /api?videoId=XXXXXXXXXXX`：取得指定影片的韓文字幕（有人工中文字幕時一併對齊）
- `GET /api?videoId=XXXXXXXXXXX&lrc=123`：用 LRCLIB 第 123 號歌詞搭配該影片

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
| 分享連結 | 整首歌（影片、時間軸、歌詞、官方中文、微調）壓縮在網址 `#s=` 後面，不需要伺服器；手機按「🔗 分享」會開分享面板 |

手機版的影片會固定在畫面上方，歌詞在下面捲動。

## 執行方式

### GitHub Pages（只用手動模式，最簡單）

直接開 `https://kuoyichun.github.io/LearnToSingKpop/`。這種純靜態網站沒有 `/api`，搜尋框會自動停用、展開「手動模式」：
貼上 YouTube 網址與韓文轉錄稿 → 載入後按「🔗 分享」，就能把整首歌的連結傳到手機或給朋友，對方打開就能練。

### 讓 Claude 幫你找歌（`add-song` skill）

在**自己電腦**上用 Claude（例如 Claude 桌面版，Chrome 已連上 Claude in Chrome 擴充功能）開這個專案，
說「我要練 IU 的 Dear my crazy soulmate」，Claude 會依照 `.claude/skills/add-song/SKILL.md`：
到 YouTube 找有韓文字幕的影片 → 取出轉錄稿 → 貼進上面的網站 → 回傳分享連結。

### 本機模式（最穩定，推薦）

YouTube 會封鎖雲端主機的 IP，在自己電腦上跑最不容易失敗：

```bash
pip install -r requirements.txt
python server.py        # 自動開啟 http://localhost:8000
```

### 用手機連家裡的電腦

```bash
python server.py --lan  # 會印出手機要開的網址，例如 http://192.168.1.23:8000
```

- 手機要連同一個 Wi-Fi；Windows 第一次執行時，防火牆詢問請允許 Python 使用「私人網路」。
- 電腦要關掉自動睡眠；建議在路由器把電腦設成固定 IP，網址才不會變（學習紀錄是跟著網址存的）。
- 出門在外（4G/5G）要連回家：在電腦和手機都裝 [Tailscale](https://tailscale.com/)（免費），
  再用 Tailscale 顯示的電腦名稱或 IP 開 `http://<名稱>:8000`。不建議在路由器開 port 對外公開。

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

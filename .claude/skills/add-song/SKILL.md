---
name: add-song
description: 使用者說要練某首歌時使用（例如「我要練 IU 的 Dear my crazy soulmate」「幫我加 aespa Supernova」「找這首歌的歌詞」）。用 Claude in Chrome 到 YouTube 找有韓文字幕的影片、取出有時間軸的韓文轉錄稿，貼進 HANGUL MASTER 網站的手動模式，回傳一個手機打開就能練習的分享連結。
---

# 加一首歌到 HANGUL MASTER

網站：https://kuoyichun.github.io/LearnToSingKpop/ （使用者若給了別的網址，以使用者的為準）

分享連結的 `#s=` 後面就是整首歌（影片 ID、時間軸、歌詞），網站不需要伺服器，任何人打開連結都能直接練習。

## 前提

需要 Claude in Chrome（`mcp__claude-in-chrome__*` 工具）。沒有這些工具時，告訴使用者這一步要在**自己電腦**上的 Claude 執行（Claude 桌面版，且 Chrome 已連上 Claude in Chrome 擴充功能），不要假裝完成，也不要編造字幕。

## 步驟

1. **準備瀏覽器**：一次 ToolSearch 載入 `tabs_context_mcp, tabs_create_mcp, navigate, computer, read_page, find, form_input, javascript_tool, tabs_close_mcp`。先呼叫 `tabs_context_mcp`，再開一個新分頁工作，不要動使用者原本的分頁。

2. **搜尋 YouTube**：前往 `https://www.youtube.com/results?search_query=<歌手 歌名>`（要 URL 編碼）。從結果挑候選影片，順序：
   1. 歌手或經紀公司官方頻道的 MV（例如 이지금 [IU Official]、HYBE LABELS、SMTOWN、JYP Entertainment、1theK、Stone Music）
   2. 官方音源、Lyric Video
   3. 其他

   使用者沒有特別要求時，跳過 Reaction、Teaser、Cover、Dance Practice、Shorts、一小時循環、Live。最多檢查 5 支。

3. **找韓文轉錄稿**（每支候選影片）：
   - 前往 `https://www.youtube.com/watch?v=<影片ID>`，用 `javascript_tool` 執行 `document.querySelector('video')?.pause()` 先暫停。
   - 展開說明欄（「...更多」/「...more」），點「顯示轉錄稿」/「Show transcript」/「스크립트 표시」。
   - 在轉錄稿面板底部的語言選單選「韓文」/「한국어」/「Korean」。優先選**沒有**「自動產生」/「자동 생성」/「auto-generated」字樣的那個；自動產生的只有在所有候選都沒有人工韓文字幕時才用。
   - 沒有轉錄稿按鈕或沒有韓文選項，就換下一支。

4. **取出字幕**：用 `javascript_tool` 執行：

   ```js
   [...document.querySelectorAll('ytd-transcript-segment-renderer')].map(seg => {
     const time = seg.querySelector('.segment-timestamp')?.textContent.trim();
     const text = seg.querySelector('.segment-text')?.textContent.trim();
     return time && text ? `${time}\n${text}` : '';
   }).filter(Boolean).join('\n')
   ```

   回傳空字串時（YouTube 改版），改用 `read_page` 讀轉錄稿面板，自己整理成「時間一行、歌詞一行」的格式。

   檢查：至少 4 行，而且至少兩成的行含有韓文字（가-힣），不然換下一支。

5. **貼進網站**：前往網站。GitHub Pages 上「手動模式」會自動展開（沒展開就點「手動模式：自己貼網址與轉錄稿」）。
   - `#yt-url` 填 `https://www.youtube.com/watch?v=<影片ID>`
   - `#transcript-input` 填第 4 步的字幕（`form_input` 失敗時用 `javascript_tool` 直接設定 `value`）
   - 點「START LEARNING」（`#load-btn`）
   - 等到出現 `.lyric-row`，而且 `#lesson-title` 有文字（播放器載入後才會補上標題，最多等 10 秒左右）
   - 用 `javascript_tool` 讀 `location.href`，這就是分享連結（要包含 `#s=`）。不要按「🔗 分享」，剪貼簿可能會跳出權限詢問。

6. **收尾**：關掉自己開的分頁，回覆使用者：
   - 歌名、用的是哪支影片（標題、頻道），字幕是人工還是自動產生（自動的要提醒可能有錯字）
   - 歌詞行數
   - 完整的分享連結（連結很長是正常的，歌詞就在裡面）

   所有候選都沒有韓文字幕時，直接說「無法取得」，並列出檢查過的影片。

## 注意

- 不要登入、按讚、留言、訂閱，也不要改 YouTube 設定。
- 避免點會跳出確認視窗的東西；出現同意 Cookie 或要求登入的畫面時，停下來問使用者。
- 同一個步驟失敗 2～3 次就停下來，說明卡在哪裡。

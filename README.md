# 10MA Uptrend Watchlist

美股 **10MA** 上升趨勢觀察名單 —— 全美上市普通股掃描，篩選「MA 仍在向上 + 一底高於一底」的股票，
並以 **VCP 收縮指數 × 底部確定性** 綜合排序。承接
[20MAwarchlist](https://github.com/yppmatthewtw-cmd/20MAwarchlist) R3 管線
（session `01W6xAAkt7gTzMnKbpnuQ9Fg`），把各頁 MA 由 20 天改為 10 天（PAGE 2 用 5 天）。

## 報告（`reports/`）

| 版本 | 內容 |
|------|------|
| R10.00 | **版面重做**（數據同 R9 一樣，2026-09-03 收盤，185 隻）：(1) **一打開就見表** —— 標題→頂欄→總表，所有說明（本版更新／市場背景／篩選規則／數據來源）連同每頁嘅統計 chips、跌出名單同圖例全部搬到表下面；(2) **收窄欄位** —— 突破／回補／守底／量比／遞減／RS／均線七欄由兩行標題（最闊 110px）縮到 34–44px（單位上標題、解釋入 tooltip 同底部圖例），Ticker 欄 180px → 124px，取消「底部序列」同「類別」兩欄（底部序列改喺走勢圖 tooltip、類別收入 Ticker 格內小標籤）；(3) **整體 compact** —— 字級 12.5→11.5px、內距 8→4px、走勢圖 150×40→100×30、原因欄預設三行（有「展開全文」掣），行高 100→79px；13 頁全部喺 1400px 視窗內一次過睇曬，唔使向右捲，螢幕再闊時兩欄原因會自動食埋剩餘闊度 |
| R9.00 | 數據更新至 **2026-09-03 收盤**（173 個交易日）：總表 185 隻（61 隻新上榜、57 隻跌出）；**介面三項改動** —— (1) 頂欄加**淺色／深色主題掣**（記喺瀏覽器，未揀就跟系統）；(2) **更新內容唔再高亮**：相對上一版嘅改動一律改用灰色小字（▲▼、+x%），全份報告冇紅色，剩低嘅顏色只有綠色（達標）同琥珀色（警示）；(3) 新增**催化欄**，一句講清楚「喺咩催化之下先至由底回升」（日期·事件·效果），可按有無催化排序；**數據** —— 9月2日冇收市快照（鏡像 commit 喺開市中途），收市價由 9月3日快照嘅官方 net-change 反推（真實），但當日成交量完全缺失，自動歸類為 price-only 日並排除喺量比／VCP 成交量項／流動性中位數之外；APH 1 拆 2 以鏡像開市中途價做支點確認後重算歷史 |
| R8.00 | **批判性審視版**（數據仍為 2026-09-01 收盤）：5 個角度審視 R7 → 修正 4 項數據缺陷（補值日唔再製造底部；成交量不完整日唔入量比／VCP；universe 剔除基金／信託／優先股；S&P 500 改用 GICS 類別），總表 171 → 181 隻；併購釘價目標公司紅色標記＋一鍵隱藏（新聞核實後多咗 **SMTI**——R7 總表 #3 標「跟大市」其實係 MiMedx 約 $35 收購目標——同 BLFS／PSNL 換股、TXNM 延期、VOYA 迫售）；內容層逐行對照序列：13 行盤後／錯日百分比改為收市對收市、過時「現價」用字改寫、MAN／NAVI／SRPT／STEP／NWS 催化劑歸因改正、分析員評級另立「評級」類別、事件日其實下跌嘅 badge 加紅色「事件日 −X%」、信心標籤上限由來源決定、純價格 highlight 移除；總表斜率／MA 統一 MA10；**所有相對 R7 嘅更新以紅色標示**（新上榜／跌出／排名箭嘴／有變嘅格）並可「只顯示有實質更新嘅行」；涉及規則嘅建議（釘價股剔除、確定性三項飽和、PAGE 2 狀態條件、覆蓋度、突破幅度、VCP 跳空、回撤首段、MA 最低升幅、雙類股）列於更新卡由用戶決定 |
| R7.00 | 數據更新至 **2026-09-01 收盤**（星期二，171 個交易日）：總表 171 隻（23 隻新上榜、30 隻跌出），ITGR 因 KKR $127 全現金收購（溢價 51.8%）躍上前列；`extend_series.py` 改為**按比例重算拆股歷史**而非整隻剔除（兩日共保留 10 隻真拆股，如 RUSHA 3:2、NXL 1拆30），只有唔似拆股嘅 COCHW 剔除；市場背景卡加入 09-01 一節（荷莫茲油輪遇襲、標普跌 0.71%、市寬 70.2% 下跌）|
| R6.01 | **純深色主題**：調色盤只定義喺 bare `:root`，移除 media query 同 `[data-theme]` 覆蓋，無論瀏覽器／系統設定都保持深色；順手修好 `.slope` 被 `.subsc` 同 specificity 蓋過、斜率一直顯示灰色而非綠色嘅串接衝突 |
| R6.00 | 數據更新至 **2026-08-31 收盤**（星期一）：容器網絡封鎖所有行情站、鏡像當日未出快照，改由本 repo 的 GitHub Actions runner 抓同源 Nasdaq screener 快照回傳，`extend_series.py` 接駁上序列（5,127 隻反推前收與 08-28 中位偏差 0.000%，8 隻合股股票剔除）；12 子頁＋總表全部重掃，24 隻新上榜逐隻研究，市場背景卡加入 08-31 一節 |
| R5.00 | 每個時間框再拆**大型（≥$100億）／中型（$20–100億）／小型（&lt;$20億）**三個子頁，共 12 個子頁＋總表（178 隻不重複）；新增**主要催化劑欄**（醒目 badge，標明業績／併購／臨床／監管／回購／指引／大單／AI／重組），Ticker 欄加市值；沿用 R2 的分欄排序、欄寬拖曳、原因分欄與熱炒 highlight |
| R2.00 | R1 基礎上改為**分欄排序版**：VCP／確定性分開兩欄（綜合分數只留 PAGE 1）、確定性 7 項證據分 7 欄，全部欄標題可點擊排序（先降後升），頂欄加「按VCP排列／按確定性排列／預設排名」；下跌／回升原因分兩欄濃縮，市場熱炒 news-driven 催化劑以 highlight 標示；所有欄寬可拖曳調整 |
| R1.00 | 全美掃描 · 5 頁：總覽（爆發潛力分數）＋ 1星期(5MA)/2星期/1個月/2個月(10MA) 四個時間框，各頁按綜合分數（0.5×VCP＋0.5×確定性）取 top 50；含底部確定性 7 項量化、下跌→回升原因欄（[Bigdata.com](https://bigdata.com) 新聞索引＋公開網頁）、2026年6–8月市場背景卡；Ticker 連結開 TradingView chart layout |

報告為獨立 HTML，直接用瀏覽器開啟；頁面切換內建。R10.00 起打開即見表、說明喺最底，13 頁喺 1400px 視窗內唔使向右捲；R9.00 起頂欄有**淺色／深色主題掣**（選擇記喺瀏覽器，未揀過就跟系統設定）；R6.01–R8 為純深色，R6.00 及之前跟隨瀏覽器設定。

## 篩選規則（10MA R1）

1. **Universe**：全美上市普通股（Nasdaq/NYSE/AMEX），存續至數據終點、歷史 ≥90 交易日、
   價格 ≥$2、20 日中位成交額 ≥$1M。
2. **MA 上升（本版重點）**：各頁以自己的時間框比較 —— PAGE 2：**5 天 MA** 較 5 個交易日前高；
   PAGE 3/4/5：**10 天 MA** 分別較 10 / 21 / 42 個交易日前高；且 MA 最後 3 日逐日上升、期內 ≥70% 日子上升。
3. **「底」**（用戶原話：「大約跌了三天，然後見底回升了大約三天」）：某日收盤係 ±3 日內最低，
   且 3 日前收盤高過佢、3 日後收盤高過佢；相鄰 ≤3 日重複底去重。
4. **一底高於一底**：最後 45 個交易日內 ≥2 個底且逐個遞升；最近一個底喺 25 個交易日內。
5. **VCP 指數（0–100）**：10日波幅/前30日波幅（35%）＋近10日高低區間佔價（25%）＋
   近10日成交量/前30日成交量（20%）＋近15日區間/前30–45日區間（20%），四項以全體合資格股票百分位合成。
6. **確定性分數（0–100，7 項）**：1.1 突破中間高位（25%）· 1.2 回補幅度（10%）· 1.3 守底時間（15%）·
   2.1 下試量縮（15%）· 2.2 回撤遞減（10%）· 2.3 相對強度（10%）· 2.4 均線位置（價>20MA＋20MA>50MA＋50MA向上，15%）；
   定義與 20MA R3 完全一致。
7. **排名（PAGE 2–5）= 綜合分數 = 0.5×VCP + 0.5×確定性**；**爆發潛力分數（PAGE 1）**
   = 0.4×VCP + 0.4×確定性 + 0.2×覆蓋度。

## 數據來源與重建

環境內可達的數據源為 GitHub 每日鏡像，逐 git commit 重建每日收盤/成交量序列（171 個交易日，
2025-12-26 → 2026-09-01）：

- 價格/成交量：[zyhe16/top-us-stock-tickers](https://github.com/zyhe16/top-us-stock-tickers)
  每日 Nasdaq 快照（`tickers/all.csv` + `tickers/sp500.csv`），依 commit 時間映射至美股交易日；
  無快照的交易日以前值填補；尾日收盤以官方 net-change 校正。
- GICS 類別（S&P 500）：[klaywang24/market-chronicle](https://github.com/klaywang24/market-chronicle)
- 交易所歸屬：[irachex/open-stock-data](https://github.com/irachex/open-stock-data)
- **最新交易日**：鏡像未出當日快照時（其更新排程於 08-31 改版），由本 repo 的
  `.github/workflows/fetch_eod_snapshot.yml` 在 GitHub Actions runner 上抓同一個 Nasdaq screener
  來源並 commit 回來；容器的網絡政策封鎖所有行情網站，runner 則無此限制。
  `scripts/extend_series.py` 以「當日收盤 − 官方 net-change」反推前收，與序列既有的前一日收盤對賬後才接駁。
  偏差 >20% 者為公司行動：比例乾淨（吻合度 0.5% 內、細數一邊 ≤5）者按比例重算歷史股數基準
  （價格乘比例、成交量除比例，成交額不變）而保留；其餘整隻剔除。

- **R8 數據修正**（`scripts/screener8.py`）：鏡像無快照嘅 4 日（03-18、08-11、08-12、08-26，全市場收盤同成交量
  照抄前一日）由數據自動偵測（>98% 股票收盤及成交量不變），底部只在真實收盤子序列上判定；成交量不完整日（02-25、08-27，
  全市場成交量中位數 <70%）同補值日不計入量比及 VCP 成交量項；universe 剔除封閉式基金／信託／優先股／票據
  （銀行及 REIT 名中有 "Trust" 者、BDC、MLP、ADR 保留）；S&P 500 成份股類別改用 GICS。

驗證：重建序列與 20MA R3 報告交叉核對，74/74 上榜股現價完全一致；另經獨立代理人對抗性驗證
（spec 合規 / 獨立重算合資格集 / VCP·評分數學 / 底部結構）；R8 前另作 5 角度批判性審視（方法論／數據品質／
內容／排名／可用性），發現及處置記錄於 `data/review8.json` 並顯示於報告更新卡。內容層由 `scripts/news_checks.py`
把每段研究文字對照收市序列（日期＋百分比、來源係咪 URL、併購價 vs 現價、「跟大市」但有 ≥8% 單日升幅），
`merge_news8.py` 每次合併都會列出警告。

限制：快照只有收盤價與成交量（無日內高低價），VCP 以收盤/成交量計算；價格未除息調整；
外國註冊而非 S&P 500 的美國上市股票（部分 ADR）缺完整歷史，未納入掃描。

## 重新產生報告

```bash
# 先 clone 三個數據 repo（路徑可用環境變數覆蓋：TICKERS_REPO / CHRONICLE_REPO / OPENSTOCK_REPO）
export WORK_DIR=./data
python3 scripts/extract_series.py    # 由 git 歷史重建序列 -> data/series2.pkl

# R1 / R2（4 個時間框單頁）
python3 scripts/screener10.py        # -> data/screen_results10.json
python3 scripts/build_report10.py    # -> data/10MA_uptrend_watchlistGit_R2.00_*.html

# R5（12 個時間框 × 市值子頁）
python3 scripts/screener5.py         # -> data/screen_results5.json
python3 scripts/merge_news5.py       # 合併新聞研究＋催化劑標籤 -> data/news5.json
python3 scripts/build_report5.py     # -> data/10MA_uptrend_watchlistGit_R5.00_*.html

# 每日更新（R6 起，腳本以環境變數串接，唔使再複製）
#   先在 GitHub 觸發 fetch_eod_snapshot workflow 取當日快照，pull 返嚟之後：
TRADE_DATE=2026-09-01 IN_SERIES=series3.pkl OUT_SERIES=series4.pkl \
  python3 scripts/extend_series.py                       # 接駁當日 -> data/series4.pkl
SERIES=series4.pkl OUT_JSON=screen_results7.json \
  python3 scripts/screener6.py                           # -> data/screen_results7.json
python3 scripts/merge_news7.py                           # 沿用 news6 + 新上榜研究 -> data/news7.json
SCREEN_JSON=screen_results7.json NEWS_JSON=news7.json REV=R7.00 \
  python3 scripts/build_report6_dark.py                  # -> data/10MA_uptrend_watchlistGit_R7.00_*.html

# R10（版面重做：說明搬到最底、欄位收窄、一屏睇曬）
#   數據同 R9 一樣，只換 renderer
python3 scripts/apply_review10.py                          # review9 + 版面說明 -> review10.json
SCREEN_JSON=screen_results9.json NEWS_JSON=news9.json PREV_SCREEN=screen_results8.json PREV_NEWS=news8.json \
  PREV_REV=R8 REV=R10.00 REVIEW_JSON=review10.json python3 scripts/build_report_r10.py

# R9（最新交易日 + 淺色／深色 + 催化欄）
#   09-02 冇收市快照：由 09-03 快照嘅 net-change 反推收市價，成交量當缺失
IN_SERIES=series4.pkl OUT_SERIES=series5.pkl GAP_DATE=2026-09-02 TRADE_DATE=2026-09-03 \
  python3 scripts/extend_series_gap.py                     # -> data/series5.pkl（173 日）
SERIES=series5.pkl OUT_JSON=screen_results9.json python3 scripts/screener9.py
python3 scripts/merge_news9.py                             # news8 + 新上榜研究 + 催化欄一句 -> news9.json
python3 scripts/apply_review9.py                           # 審視層帶到 R9（重算釘價價差、保留未決事項）
SCREEN_JSON=screen_results9.json NEWS_JSON=news9.json PREV_SCREEN=screen_results8.json PREV_NEWS=news8.json \
  PREV_REV=R8 REV=R9.00 REVIEW_JSON=review9.json python3 scripts/build_report9.py

# R8（審視修正版 + 紅色差異標示）
python3 scripts/patch_volume.py                          # 以鏡像較完整嘅成交量補齊當日 bar（價格須完全相同）
SERIES=series4.pkl OUT_JSON=screen_results8.json python3 scripts/screener8.py   # 含 4 項數據修正
python3 scripts/apply_review8.py                         # news7 -> news8 底稿 + review8.json（過時文字、釘價股標記）
python3 scripts/merge_news8.py                           # 加入新上榜研究；並以 news_checks.py 對照序列列出警告
python3 scripts/apply_review8b.py                        # 內容／排名審視結果（含 apply_review8_fact.py 嘅網上核實）
SCREEN_JSON=screen_results8.json NEWS_JSON=news8.json PREV_SCREEN=screen_results7.json PREV_NEWS=news7.json \
  PREV_REV=R7 REV=R8.00 REVIEW_JSON=review8.json python3 scripts/build_report8.py   # 紅色 = 相對 R7 嘅更新
python3 scripts/news_checks.py news8.json screen_results8.json   # 隨時可獨立跑：文字 vs 序列、來源、併購價

#   （R6.00 為跟隨系統主題的版本：python3 scripts/build_report6.py）
```

新聞研究由 AI 代理透過 Bigdata.com 新聞索引及公開網頁搜尋產生，結果暫存於 session scratchpad
（`r5_*.json` / `r6_res_*.json` / `r7_res_*.json` / `r8_res_*.json`），由 `merge_news5.py`…`merge_news8.py`
逐版合併入 `data/news5.json`…`news8.json` —— 每版只研究「新上榜」的股票，其餘沿用上一版。
Bigdata.com 額度已耗盡，改以 WebSearch 完成；R5 有 13 隻因搜尋額度用盡而未覆蓋的股票已用新代理補做，
R6 的 24 隻及 R7 的 21 隻新上榜全部搵到個股消息；R8 因數據修正而新上榜嘅 22 隻同樣逐隻研究。

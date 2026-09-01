# 10MA Uptrend Watchlist

美股 **10MA** 上升趨勢觀察名單 —— 全美上市普通股掃描，篩選「MA 仍在向上 + 一底高於一底」的股票，
並以 **VCP 收縮指數 × 底部確定性** 綜合排序。承接
[20MAwarchlist](https://github.com/yppmatthewtw-cmd/20MAwarchlist) R3 管線
（session `01W6xAAkt7gTzMnKbpnuQ9Fg`），把各頁 MA 由 20 天改為 10 天（PAGE 2 用 5 天）。

## 報告（`reports/`）

| 版本 | 內容 |
|------|------|
| R6.01 | **純深色主題**：調色盤只定義喺 bare `:root`，移除 media query 同 `[data-theme]` 覆蓋，無論瀏覽器／系統設定都保持深色；順手修好 `.slope` 被 `.subsc` 同 specificity 蓋過、斜率一直顯示灰色而非綠色嘅串接衝突 |
| R6.00 | 數據更新至 **2026-08-31 收盤**（星期一）：容器網絡封鎖所有行情站、鏡像當日未出快照，改由本 repo 的 GitHub Actions runner 抓同源 Nasdaq screener 快照回傳，`extend_series.py` 接駁上序列（5,127 隻反推前收與 08-28 中位偏差 0.000%，8 隻合股股票剔除）；12 子頁＋總表全部重掃，24 隻新上榜逐隻研究，市場背景卡加入 08-31 一節 |
| R5.00 | 每個時間框再拆**大型（≥$100億）／中型（$20–100億）／小型（&lt;$20億）**三個子頁，共 12 個子頁＋總表（178 隻不重複）；新增**主要催化劑欄**（醒目 badge，標明業績／併購／臨床／監管／回購／指引／大單／AI／重組），Ticker 欄加市值；沿用 R2 的分欄排序、欄寬拖曳、原因分欄與熱炒 highlight |
| R2.00 | R1 基礎上改為**分欄排序版**：VCP／確定性分開兩欄（綜合分數只留 PAGE 1）、確定性 7 項證據分 7 欄，全部欄標題可點擊排序（先降後升），頂欄加「按VCP排列／按確定性排列／預設排名」；下跌／回升原因分兩欄濃縮，市場熱炒 news-driven 催化劑以 highlight 標示；所有欄寬可拖曳調整 |
| R1.00 | 全美掃描 · 5 頁：總覽（爆發潛力分數）＋ 1星期(5MA)/2星期/1個月/2個月(10MA) 四個時間框，各頁按綜合分數（0.5×VCP＋0.5×確定性）取 top 50；含底部確定性 7 項量化、下跌→回升原因欄（[Bigdata.com](https://bigdata.com) 新聞索引＋公開網頁）、2026年6–8月市場背景卡；Ticker 連結開 TradingView chart layout |

報告為獨立 HTML，直接用瀏覽器開啟；頁面切換內建。R6.01 起為純深色主題（R6.00 及之前跟隨瀏覽器 light/dark 設定）。

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

環境內可達的數據源為 GitHub 每日鏡像，逐 git commit 重建每日收盤/成交量序列（170 個交易日，
2025-12-26 → 2026-08-31）：

- 價格/成交量：[zyhe16/top-us-stock-tickers](https://github.com/zyhe16/top-us-stock-tickers)
  每日 Nasdaq 快照（`tickers/all.csv` + `tickers/sp500.csv`），依 commit 時間映射至美股交易日；
  無快照的交易日以前值填補；尾日收盤以官方 net-change 校正。
- GICS 類別（S&P 500）：[klaywang24/market-chronicle](https://github.com/klaywang24/market-chronicle)
- 交易所歸屬：[irachex/open-stock-data](https://github.com/irachex/open-stock-data)
- **最新交易日**：鏡像未出當日快照時（其更新排程於 08-31 改版），由本 repo 的
  `.github/workflows/fetch_eod_snapshot.yml` 在 GitHub Actions runner 上抓同一個 Nasdaq screener
  來源並 commit 回來；容器的網絡政策封鎖所有行情網站，runner 則無此限制。
  `scripts/extend_series.py` 以「當日收盤 − 官方 net-change」反推前收，與序列既有的前一日收盤對賬後才接駁，
  偏差 >20% 者（合股／拆股）整隻剔除。

驗證：重建序列與 20MA R3 報告交叉核對，74/74 上榜股現價完全一致；另經獨立代理人對抗性驗證
（spec 合規 / 獨立重算合資格集 / VCP·評分數學 / 底部結構）。

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

# R6（更新至最新收盤）
#   先在 GitHub 觸發 fetch_eod_snapshot workflow 取當日快照，pull 返嚟之後：
TRADE_DATE=2026-08-31 python3 scripts/extend_series.py   # series2 + 當日 -> data/series3.pkl
python3 scripts/screener6.py         # -> data/screen_results6.json
python3 scripts/merge_news6.py       # 沿用 news5 + 新上榜研究 -> data/news6.json
python3 scripts/build_report6.py      # -> data/10MA_uptrend_watchlistGit_R6.00_*.html（跟隨系統主題）
python3 scripts/build_report6_dark.py # -> data/10MA_uptrend_watchlistGit_R6.01_*.html（純深色）
```

新聞研究由 AI 代理透過 Bigdata.com 新聞索引及公開網頁搜尋產生，結果暫存於 session scratchpad
（`r5_res_*.json` / `r5_redo_*.json` / `r5_cat_*.json` / `r6_res_*.json`），由 `merge_news5.py`、
`merge_news6.py` 合併入 `data/news5.json`、`data/news6.json`。Bigdata.com 額度已耗盡，改以 WebSearch 完成；
R5 有 13 隻因搜尋額度用盡而未覆蓋的股票已用新代理補做，R6 的 24 隻新上榜全部搵到個股消息。

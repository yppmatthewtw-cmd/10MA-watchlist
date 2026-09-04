#!/usr/bin/env python3
"""R10 = R9's data and research with a rebuilt layout, so the review layer is
carried over unchanged and three layout notes are put in front of it.

Kept separate from apply_review9*.py because nothing here touches the numbers:
same screen_results9.json, same news9.json, same findings — only the page
changes, and the update card should say so plainly rather than implying a
rescan.
"""
import json, os

SCRATCH = os.environ.get("WORK_DIR", "./data")
IN = os.environ.get("IN_REVIEW", "review9.json")
OUT = os.environ.get("OUT_REVIEW", "review10.json")

r = json.load(open(f"{SCRATCH}/{IN}"))
scr = json.load(open(f"{SCRATCH}/screen_results9.json"))
n = len(scr["page1"])

layout_notes = [
    {"title": "[本版做法] 一打開就見表，說明全部搬到最底",
     "text": "R9 打開之後要先滑過更新卡、市場背景同篩選規則先見到第一行股票。R10 改為：標題 → 頂欄（時間框／市值／排序／各種掣）→ 表，"
             "其餘全部（本版更新、市場背景、篩選規則、數據來源同備註）搬到表下面嘅「說明」區。每頁嘅統計 chips、跌出名單同圖例亦一併移到表後面。"},
    {"title": "[本版做法] 收窄欄位，唔使向右 scroll",
     "text": f"欄寬由內容決定改為由版面決定（table-layout: fixed ＋ colgroup）：突破／回補／守底／量比／遞減／RS／均線七欄由原本兩行標題"
             f"（最闊 110px）縮到 34–44px，單位搬上標題、解釋搬入 tooltip 同底部圖例；Ticker 欄由 180px 收到 124px（公司名截短、"
             "MA 數值同「已重上MA」改為 tooltip 同符號）。另外「底部序列」同「類別」兩欄取消 —— 底部序列本身喺走勢圖有綠點標示、"
             "完整序列改喺格內 tooltip；類別收入 Ticker 格內做一個小標籤。結果：13 頁全部喺 1400px 闊嘅視窗內一次過睇曬，唔使橫向捲。",
     "tickers": []},
    {"title": "[本版做法] 行高壓縮，一屏睇多幾行",
     "text": "字級由 12.5px 減到 11.5px、內距由 8px 減到 4px、走勢圖由 150×40 縮到 100×30、時間框 chips 兩個一行；"
             "下跌／回升原因預設只顯示三行（滑鼠停留有全文，頂欄有「展開全文」掣一鍵展開全部）。行高由約 100px 減到 79px，"
             "1440px 螢幕一屏由 8 行變 10 行。螢幕再闊嘅話，兩欄原因會自動食埋剩餘闊度（1920px 時每欄闊約一倍），"
             "所以大螢幕唔會右邊吉一大條。"},
    {"title": "[備註] 數據同 R9 完全一樣",
     "text": f"R10 冇重新掃描：同一個 2026-09-03 收盤序列、同一批 {n} 隻股票、同一份研究同審視結果。頁內「新上榜／有更新」"
             "嘅灰色標示仍然係相對 R8（即上一次數據更新）而言，所以同 R9 見到嘅一樣。"},
]

r["notes"] = layout_notes + r["notes"]
r["headline"] = ("R10 係版面重做：一打開除咗標題就係頂欄同總表，所有說明（本版更新、市場背景、篩選規則、數據來源）"
                 "全部搬到表下面；七個證據欄同 Ticker 欄大幅收窄、取消「底部序列」同「類別」兩欄（內容改用 tooltip 同小標籤保留）、"
                 "行高由約 100px 減到 79px，1400px 視窗已經可以一次過睇曬所有欄，唔使向右捲。"
                 "數據同研究同 R9 一模一樣（2026-09-03 收盤，" + str(n) + " 隻），下面 R9 嘅審視結論同未決事項全部照舊。 ")
if r.get("review_summary"):
    r["headline"] += ""
json.dump(r, open(f"{SCRATCH}/{OUT}", "w"), ensure_ascii=False, indent=1)
print(f"wrote {SCRATCH}/{OUT} · notes {len(r['notes'])} (added {len(layout_notes)}) · flags {len(r['ticker_flags'])}")

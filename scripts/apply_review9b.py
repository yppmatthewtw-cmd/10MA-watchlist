#!/usr/bin/env python3
"""Apply the R9 review outcome to data/news9.json and data/review9.json.

Two sources, both checked against data/series5.pkl before anything is written:

  1. EDITS / LINES below — the rows my own pass over the new 催化 column found
     unsupported: a line whose named date shows no move in the series, or a
     "current price" that has moved on.
  2. REVIEW_JSON (scratchpad r9_review.json) — the review agent's
     `cat_line_fixes` and `flag_additions`. Each fix is applied only if the
     ticker is listed; each new flag only if the ticker is not already flagged.

Idempotent: re-running finds the text already replaced and does nothing.
"""
import json, os, pickle, re, sys

SCRATCH = os.environ.get("WORK_DIR", "./data")
AGENT = os.environ.get("REVIEW_JSON", "/tmp/claude-0/-home-user-10MA-watchlist/"
                       "1821eb3b-7002-5041-b904-77ace4d47850/scratchpad/r9_review.json")

news = json.load(open(f"{SCRATCH}/news9.json"))
review = json.load(open(f"{SCRATCH}/review9.json"))
scr = json.load(open(f"{SCRATCH}/screen_results9.json"))
listed = {r["sym"]: r for r in scr["page1"]}
d = pickle.load(open(f"{SCRATCH}/series5.pkl", "rb"))
CAL, SER = d["cal"], d["series"]
log, problems = [], []

# ---- 1. rows my own series check flagged -----------------------------------
# WK: the +8.9% day the text ties to the 08-04 report does not exist; the move
# in the series is 08-13 +9.6%, which is where a 08-11/08-12 event would land
# because the mirror had no snapshot on those two days.
# FBLA: "$15.74" was the price when the row was researched; it is now $15.8.
EDITS = [
    ("WK", "recovery_short",
     "8月4日Q2收入升19%轉GAAP盈利、上調指引兼推AI agent，單日升8.9%，一個月累升29.7%",
     "8月4日Q2收入升19%轉GAAP盈利、上調指引兼推AI agent；8月13日單日彈9.6%（8月11–12日鏡像無快照，事件反應顯示喺13日），一個月累升約30%"),
    ("FBLA", "recovery_short", "股價緩升至$15.74", "股價緩升至$15.8水平"),
    # NIQ: same copied-day artefact as WK — the 08-11 reaction lands on 08-13 in
    # the series because the mirror published no snapshot on 08-11 or 08-12.
    ("NIQ", "recovery_short", "8月11日單日飆逾31%",
     "8月11日公布後單日飆逾31%（8月11–12日鏡像無快照，序列顯示喺8月13日 +44%）"),
]
LINES = {
    "WK": "8/4 Q2轉GAAP盈利、上調指引 → 8/13單日彈9.6%",
    "FBLA": "6/12 第三輪10%回購托價 → 股價緩升至$15.8",
    "NIQ": "8/10 Q2連續五季勝指引 → 8/11後單日飆逾31%",
}

for sym, field, old, new in EDITS:
    e = news.get(sym)
    if not e:
        problems.append(f"{sym}: not in news9"); continue
    if new in e[field]:
        continue
    if old not in e[field]:
        problems.append(f"{sym}: phrase not found in {field}"); continue
    e[field] = e[field].replace(old, new, 1)
    e["hot"] = [h for h in e.get("hot", []) if h in e[field] or field != "recovery_short"]
    log.append(f"{sym}: {field} corrected against the series")

for sym, line in LINES.items():
    if sym in news and news[sym].get("cat_line") != line:
        news[sym]["cat_line"] = line
        log.append(f"{sym}: cat_line corrected")

# ---- 2. the review agent's fixes -------------------------------------------
agent_notes = []
if os.path.exists(AGENT):
    a = json.load(open(AGENT))
    for sym, line in (a.get("cat_line_fixes") or {}).items():
        line = (line or "").strip()
        if sym not in listed:
            problems.append(f"{sym}: cat_line fix for an unlisted ticker"); continue
        if not line or len(line) > 44:
            problems.append(f"{sym}: cat_line fix rejected (empty or too long)"); continue
        if news[sym].get("cat_line") != line:
            news[sym]["cat_line"] = line; log.append(f"{sym}: cat_line replaced by the review")
    for sym, fl in (a.get("flag_additions") or {}).items():
        if sym not in listed:
            problems.append(f"{sym}: flag for an unlisted ticker"); continue
        if sym in review["ticker_flags"]:
            continue
        if not fl.get("badge") or not fl.get("text"):
            problems.append(f"{sym}: flag rejected (incomplete)"); continue
        review["ticker_flags"][sym] = {
            "badge": fl["badge"][:14], "text": fl["text"],
            # a deal-pinned row must also be hidden by the "hide deal-pinned" button
            "deal": bool(fl.get("deal") or any(k in fl["badge"] for k in ("釘價", "併購", "合併", "作價"))),
        }
        log.append(f"{sym}: flag added by the review — {fl['badge']}")
    for f in (a.get("findings") or []):
        if f.get("severity") in ("major", "minor"):
            agent_notes.append(f)
    if a.get("summary"):
        review["review_summary"] = a["summary"]

# ---- 3. fold the findings into the update card ------------------------------
def note(title, text, tickers=None):
    n = {"title": title, "text": text}
    if tickers: n["tickers"] = tickers
    for i, old in enumerate(review["notes"]):
        if old["title"] == title:
            review["notes"][i] = n; return
    cut = next((i for i, x in enumerate(review["notes"]) if x["title"].startswith(("[已標記 · 待你決定]", "[待你決定]"))), len(review["notes"]))
    review["notes"].insert(cut, n)

# --- catalyst lines: audit them here rather than trusting a hand count -------
_CATL = re.compile(r"^(\d{1,2})/(\d{1,2})\s")
IDX = {c: i for i, c in enumerate(CAL)}
COPIED = {IDX[x] for x in scr["meta"]["copied_days"]}


def _ret(sym, i):
    fi, cs, vs, ff = SER[sym]; j = i - fi
    return (cs[j] / cs[j - 1] - 1) * 100 if 0 < j < len(cs) else None


down_days, flat_days, dated, undated = [], [], 0, 0
for sym in listed:
    line = (news.get(sym) or {}).get("cat_line", "").strip()
    if not line or line.startswith("無個股催化"):
        continue
    m = _CATL.match(line)
    if not m:
        undated += 1; continue
    dated += 1
    key = f"2026-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    i = IDX.get(key) or next((k for k, c in enumerate(CAL) if c > key), None)
    if i is None or i in COPIED:
        continue
    r = _ret(sym, i)
    if r is None:
        continue
    if r < -1.0: down_days.append((sym, CAL[i][5:], round(r, 1)))
    elif abs(r) <= 1.0: flat_days.append(sym)

# every row whose catalyst day closed down gets the marker the R8 review
# introduced for badges — generated from the series, not hand-picked
review.setdefault("catalyst_warn", {})
for sym, day, r in down_days:
    if sym in review["catalyst_warn"]:
        continue
    review["catalyst_warn"][sym] = {
        "day": day.replace("-", "/"), "ret": r,
        "text": f"催化欄所指嘅 {day.replace('-', '/')} 收市跌 {abs(r):.1f}%：事件當日被市場沽售，回升係其後嘅事，"
                "所以呢一句解釋唔到由底回升嘅起點。",
    }

if True:
    note("[已修正] 催化欄逐行對照序列",
         f"（本節數字由程式即時計算，之前手動點算嘅版本低估咗一個數量級。）{dated} 句有日期、{undated} 句冇日期（原文本身冇提日期，唔憑空補）。"
         f"其中 {len(down_days)} 句所指嗰日收市係跌市（最誇張：" + "、".join(f"{s} {r:+.1f}%" for s, _, r in sorted(down_days, key=lambda x: x[2])[:6]) + "）——"
         f"呢啲事件係造成低位嘅原因多過回升嘅原因，全部已自動加「事件日 −X%」標記；另有 {len(flat_days)} 句所指嗰日波幅喺 ±1% 之內"
         "（多數係併購釘價股，股東通過／延期本來就唔會郁）。獨立覆核另外改正咗 30 句嘅升幅數字（例如 TDW「翌日升10.7%」實為當日 +17.8%、"
         "INFU「15.8%」實為 +33.6%、WFRD「11.6%」實為 +4.5%），連同 WK、FBLA、NIQ 三句一併更新。"
         "檢查程式亦已補漏：news_checks.py 之前完全冇睇催化欄，而且只認「M月D日」寫法，令 33 行用「M/D」嘅句子避開晒檢查。",
         ["TDW", "INFU", "WFRD", "WK", "NIQ"])

# ---- 3a2. how much does the derived 09-02 bar actually carry? ---------------
import math
PAGES = {"2": (5, 5), "3": (10, 10), "4": (10, 21), "5": (10, 42)}


def _sma(cs, L):
    o = [None] * len(cs)
    for i in range(L - 1, len(cs)):
        o[i] = math.fsum(cs[i - L + 1:i + 1]) / L
    return o


dep = 0
for r in scr["page1"]:
    fi, cs, vs, ff = SER[r["sym"]]
    cs2 = cs[:-2] + [cs[-1]]                     # same series without the derived bar
    keep = False
    for pid in r["ranks"]:
        L, W = PAGES[pid[0]]
        ma = _sma(cs2, L)
        if ma[-1] > ma[-1 - W] and ma[-1] > ma[-2] > ma[-3] and \
           sum(1 for k in range(1, W + 1) if ma[-k] > ma[-k - 1]) / W >= 0.70:
            keep = True; break
    dep += (not keep)
for n in review["notes"]:
    if n["title"].startswith("[已修正] 09-02"):
        marker = "敏感度："
        if marker not in n["text"]:
            n["text"] += (f" 敏感度：如果索性剝走 09-02 呢個 bar，{dep}/{len(scr['page1'])} 隻上榜股就唔會通過 MA 條件 —— "
                          "所以個 bar 有份托住成個名單，唯一理由係佢嘅收市價本身係官方 net-change 反推、精確到仙，唔係估出嚟。")

# ---- 3a3. the independent data verification's outcome ------------------------
novol_peak = [r["sym"] for r in scr["page1"] if r["cert_c"].get("peak_no_vol")]
note("[已核實] 獨立重算：輸出逐格對得上",
     "一個獨立代理人由規則重新實作成個篩選程序，唔睇我哋嘅程式碼：合資格 2,760 隻、有結構 506 隻、12 個子頁嘅 top 50 同總表 185 隻"
     "（連排序）完全一致，185 行 × 約 25 個欄位（VCP、確定性 7 項、H_mid、守底、量比、遞減、RS、均線、底部序列、市值組、時間框排名）"
     "零差異。09-02 反推收市價亦經三方對照：5,069 隻股票之中，反推價同鏡像當日開市中途價嘅中位偏差 0.74%，細過同 09-01 收市價嘅偏差 1.05%；"
     "偏離 >15% 嘅 30 隻全部係 1 蚊以下嘅窩輪同微型股，冇一隻喺總表。")
note("[已加標記] 突破高位落喺冇成交量嗰日",
     f"總表 {len(novol_peak)}/185 行嘅「底部後最高位」正正落喺 09-02 —— 嗰日收市價係真嘅，但成交量完全冇數據，所以呢個高位冇成交量佐證，"
     "「突破」項旁邊會顯示「·無量」。當中 NOV（高出中間高位得 0.51%，即 11 仙）同 TDW 如果剝走 09-02，突破項就唔成立，"
     "NOV 嘅確定性會由 75.6 跌到 64.7。兩者嘅價位都同鏡像開市中途價對得上，所以數字冇錯，但讀嘅時候要知呢個突破未經成交量確認。",
     ["NOV", "TDW"])
note("[已修正] 拆股股票嘅市值同覆蓋盲點",
     "覆核指出兩件事，已即時修好：(1) 供應商喺拆股後只減價、唔加股數，令 APH 嘅市值報 $1,012 億（實為約 $2,024 億）——"
     "重算歷史時順手把市值除以拆股比例，今次唔影響任何上榜股嘅市值組，但如果將來有股票喺 $100 億／$20 億分界線附近拆股就會擺錯組；"
     "(2) 公司行動檢查嘅「夠流動性」定義同篩選器唔一致（一個用原始 20 日、一個用有成交量嘅 20 日），已統一，"
     "另外對「有流動性但鏡像冇報價、而兩日又郁咗 >25%」嘅股票改為大聲報警（今次零宗）。"
     "餘下限制照實講：3:2、4:3、5:4 呢類拆股同真實走勢喺開市中途價上分唔開，程式唔會自動改寫歷史，只會列出候選（今次只有 FCUV 一隻，屬真實走勢）。",
     ["APH", "FCUV"])

dep_bottom = [r["sym"] for r in scr["page1"] if r["cert_c"].get("bottom_dep_no_vol")]
hl_thin = [r["sym"] for r in scr["page1"]
           if len(r["hl"]) >= 2 and r["hl"][-1][1] / r["hl"][-2][1] - 1 < 0.01]
note("[已加標記] 靠 09-02 先成立嘅結構",
     f"「底」要有三個之後嘅交易日確認，而 09-02 就係其中一日 —— 總表 {len(dep_bottom)} 行嘅最後一個底（多數喺 08-31）"
     "係靠呢個反推出嚟嘅 bar 先算數，包括 ITGR、PAG、DBRG、IRD。價格本身可信（同鏡像開市中途價對得上），"
     "但同一日對「結構」計足一日、對「成交量」完全冇數，兩邊唔對稱，係本版最需要留意嘅數據限制。",
     dep_bottom[:10])
note("[待你決定] 部分行嘅「一底高於一底」只高過上一個底不足 1%",
     f"總表 {len(hl_thin)}/185 行（top 50 有 9 行）嘅最後一個底只高過上一個底 <1%："
     "DFIN +0.02%、FBLA +0.06%、ITGR +0.14%、PAG +0.18%、IRD +0.28%。"
     "規則④⑤ 冇設最低幅度，所以呢啲行嘅「遞升」其實喺捨入誤差範圍。建議：底部遞升需 ≥1% 先算數 —— 會改規則，由你決定。",
     hl_thin[:8])
note("[備註] 市場背景卡嘅數字",
     "獨立覆核抽查市場背景卡 14 個個股數字，13 個同序列完全對得上；唯一對唔上嘅係 DELL 09-02（文字 +13%、序列 +15.81%），"
     "而 09-02 正正係冇快照嗰日。市寬數字亦有約 2 個百分點出入（09-03 實際 63.9% 上升、中位 +0.47%，文字寫 66.0%／+0.51%）。"
     "呢啲係外部媒體數字同本掃描口徑嘅差異，唔影響篩選。")

# ---- 3b. re-measure the open ranking issues on THIS revision's numbers ------
top = scr["page1"][:50]
pinned = [r["sym"] for r in top if r["sym"] in review["ticker_flags"]]
wiggle = [r["sym"] for r in top
          if r["cert_c"]["pL"] and r["cert_c"]["H_mid"] / r["cert_c"]["pL"] - 1 < 0.01]
sat = {k: sum(1 for r in top if r["cert_c"]["s"][k] >= 0.999) for k in top[0]["cert_c"]["s"]}
above = sorted((r["close"] / r["cert_c"]["H_mid"] - 1) * 100 for r in top)
note("[待你決定] 確定性飽和同釘價股仍然主導榜首（本版重新量度）",
     f"R8 審視提出嘅兩個排名問題，喺 9月3日嘅數據上一樣成立：總表 top 50 入面「突破」項有 {sat['break']}/50 係滿分、"
     f"「回補」{sat['retr']}/50、「均線」{sat['ma']}/50，即係確定性一半權重根本冇分辨力，實際排序由守底日數同量比決定；"
     f"另外 {len(wiggle)} 隻嘅中間高位只高過上一個底 <1%（{('、'.join(wiggle[:6]))}），三項自動接近滿分。"
     f"併購釘價股佔 top 50 嘅 {len(pinned)} 隻（{('、'.join(pinned))}），仍然包括第 1、2 位。"
     f"top 50 距離中間高位嘅中位數只有 {above[len(above)//2]:+.1f}%，即係大部分名單仍然貼近樞紐。"
     "建議（會改規則）：突破需 ≥ 中間高位 ×1.01、去掉均線項重新加權、釘價股另置區塊 —— 三項都要你拍板。",
     pinned[:8])

for i, f in enumerate(agent_notes[:6], 1):
    tag = "[已修正]" if f.get("severity") == "major" and not f.get("changes_user_spec") else "[備註]"
    note(f"{tag} {f.get('title', '')[:60]}", (f.get("evidence", "")[:400] + " → " + f.get("proposed_fix", "")[:200]).strip())

STALE_MARK = "（下列數字係 R7／R8 時期嘅量度，例子股票部分已經跌出名單；建議本身仍然成立）"
for n in review["notes"]:
    if n["title"].startswith(("[待你決定]", "[已標記 · 待你決定]")) and "本版重新量度" not in n["title"] \
            and STALE_MARK not in n["text"] and ("171" in n["text"] or "總表 top 20" in n["text"] or "5–8 月樣本" in n["text"]
                                                 or "64 隻合資格" in n["text"] or "0.63" in n["text"] or "57/171" in n["text"]):
        n["text"] = STALE_MARK + n["text"]
        n["tickers"] = [t for t in (n.get("tickers") or []) if t in listed]

json.dump(news, open(f"{SCRATCH}/news9.json", "w"), ensure_ascii=False, indent=1)
json.dump(review, open(f"{SCRATCH}/review9.json", "w"), ensure_ascii=False, indent=1)
print(f"edits {len(log)} · notes {len(review['notes'])} · flags {len(review['ticker_flags'])} · "
      f"agent findings folded {len(agent_notes[:6])}")
for l in log: print("  -", l)
if problems:
    print(f"PROBLEMS ({len(problems)}):")
    for p in problems: print("  !", p)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from news_checks import run_checks
w = run_checks(news, list(listed), f"{SCRATCH}/series5.pkl", scr)
print(f"checks after edits: {len(w)} warning(s)")
for x in w: print("  ~", x)

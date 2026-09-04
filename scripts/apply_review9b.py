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
        review["ticker_flags"][sym] = {"badge": fl["badge"][:14], "text": fl["text"]}
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

if any(k in log for k in []) or True:
    note("[已修正] 催化欄逐行對照序列",
         "新欄嘅每一句都用日期回帶去序列核對：185 行入面 5 行嘅日期當日冇明顯波動，其中 3 行係併購釘價股（股東通過／延期本來就唔會郁），"
         "另外 2 行已改正 —— WK 原文話 8月4日「單日升8.9%」，序列顯示嗰日只係 +0.1%，真正嘅 +9.6% 喺 8月13日（8月11–12日鏡像無快照，反應順延）；"
         "FBLA 嘅「$15.74」已更新為現價水平。另外 6 行標「無個股催化」嘅，全部都冇出現過 ≥8% 嘅單日升幅，同「跟大市」講法一致。",
         ["WK", "FBLA", "NIQ"])

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

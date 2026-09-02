#!/usr/bin/env python3
"""Apply the R7 critical-review outcome to the R8 inputs.

Reads data/news7.json + data/screen_results8.json, writes data/news8.json and
data/review8.json (headline / notes / rule_notes / ticker_flags consumed by
build_report8.py). Two classes of change:

1. Mechanical fixes that do not touch the user's rules:
   - blurbs that quote a stale close ("8月28日收$127.04") lose the stale clause;
   - deal-pinned acquisition targets get a red flag on their catalyst badge so a
     reader knows the "contraction" is a cash offer, not a coiling breakout.
2. Judge-driven items from the review workflow (JUDGE_JSON): headline, notes,
   rule_notes, extra ticker flags, and any per-ticker text/confidence edits.
"""
import json, os, re, sys

SCRATCH = os.environ.get("WORK_DIR", "./data")
JUDGE = os.environ.get("JUDGE_JSON")          # optional: judge output from the workflow
DEALS = os.environ.get("DEAL_JSON", "/tmp/claude-0/-home-user-10MA-watchlist/"
                       "1821eb3b-7002-5041-b904-77ace4d47850/scratchpad/deal_class.json")

news = json.load(open(f"{SCRATCH}/news7.json"))
scr = json.load(open(f"{SCRATCH}/screen_results8.json"))
listed = {r["sym"] for r in scr["page1"]}
review = {"headline": "", "notes": [], "rule_notes": [], "ticker_flags": {}}
log = []

# ---- 1a. stale close references -------------------------------------------
STALE = re.compile(r'[，,；;]?\s*(?:8月2[0-9]日|至8月2[0-9]日)收[報]?\$?[\d\.]+\s*[。]?')
for sym in listed:
    e = news[sym]
    for k in ("recovery_short", "decline_short"):
        t = e[k]
        t2 = STALE.sub("", t).replace("，。", "。").rstrip("，,；; ")
        if not t2.endswith("。") and t.endswith("。"): t2 += "。"
        t2 = t2.replace("至8月28日", "").strip()
        # OGN quoted the 08-28 close as the arb spread; the number is stale, the point is not
        t2 = re.sub(r'價差收窄\$[\d\.]+、距\$14僅[\d\.]+%', '價差持續收窄，貼近$14作價', t2)
        if t2 != t:
            # keep hot spans that still occur; drop the rest rather than point at nothing
            e["hot"] = [h for h in e.get("hot", []) if h in t2] if k == "recovery_short" else e.get("hot", [])
            e[k] = t2
            log.append(f"{sym}: {k} stale close reference removed")

# ---- 1b. deal-pinned targets ----------------------------------------------
deals = json.load(open(DEALS)) if os.path.exists(DEALS) else {}
deals.setdefault("APGE", {"kind": "target"})     # AbbVie is acquiring Apogee; the auto-classifier left it unclear
for sym, d in deals.items():
    if sym not in listed: continue
    if d["kind"] == "target":
        review["ticker_flags"][sym] = {
            "badge": "併購目標 · 價已釘",
            "text": "被收購／私有化目標：股價貼住作價，波幅收縮係交易所致，唔係蓄勢突破；VCP 高分屬機械假象，爆發潛力應打大折扣",
        }
    elif d["kind"] == "rumour":
        review["ticker_flags"][sym] = {
            "badge": "併購傳聞",
            "text": "催化劑為收購傳聞，未有作價；消息真偽同時間表未定",
        }

# ---- 2. judge-driven items -------------------------------------------------
if JUDGE and os.path.exists(JUDGE):
    j = json.load(open(JUDGE))
    review["headline"] = j.get("headline", "")
    for item in j.get("ranked", []):
        if item["action"] in ("fix_now", "fix_now_flag_red"):
            review["notes"].append({"title": f"[已修正] {item['title']}", "text": item["concrete_change"]})
        elif item["action"] == "ask_user":
            review["notes"].append({"title": f"[待你決定] {item['title']}", "text": item["rationale"] + " → 建議：" + item["concrete_change"]})
        elif item["action"] == "note_only":
            review["notes"].append({"title": f"[備註] {item['title']}", "text": item["rationale"]})
    review["rule_notes"] = j.get("rule_notes", [])
    for sym, fl in (j.get("ticker_flags") or {}).items():
        review["ticker_flags"][sym] = fl
    for sym, edits in (j.get("news_edits") or {}).items():
        if sym in news:
            news[sym].update(edits); log.append(f"{sym}: judge edit {list(edits)}")

json.dump(news, open(f"{SCRATCH}/news8.json", "w"), ensure_ascii=False, indent=1)
json.dump(review, open(f"{SCRATCH}/review8.json", "w"), ensure_ascii=False, indent=1)
print(f"news8.json written · {len(log)} text edits · {len(review['ticker_flags'])} ticker flags · "
      f"{len(review['notes'])} notes · {len(review['rule_notes'])} rule notes")
for l in log: print("  -", l)

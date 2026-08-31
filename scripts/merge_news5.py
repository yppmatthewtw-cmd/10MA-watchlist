#!/usr/bin/env python3
"""Merge R5 news inputs into data/news5.json — one entry per listed ticker.

Sources:
  data/news.json            full R1 research text for the original 74
  data/news_condensed.json  R2 condensed text + hot spans for those 74
  scratchpad r5_cat_*.json  catalyst label + kind for those 74
  scratchpad r5_res_*.json  condensed text + hot + catalyst for the 104 new ones

Validates that every page-1 ticker is covered, that each hot span really occurs
in its recovery text, and reports anything missing instead of silently dropping.
"""
import glob, json, os, sys

SCRATCH = os.environ.get("WORK_DIR", "./data")
AGENT_DIR = os.environ.get("AGENT_DIR",
                           "/tmp/claude-0/-home-user-10MA-watchlist/"
                           "1821eb3b-7002-5041-b904-77ace4d47850/scratchpad")

scr = json.load(open(f"{SCRATCH}/screen_results5.json"))
need = [r["sym"] for r in scr["page1"]]
news = json.load(open(f"{SCRATCH}/news.json"))
cond = json.load(open(f"{SCRATCH}/news_condensed.json"))

out, problems = {}, []

cats = {}
for f in sorted(glob.glob(f"{AGENT_DIR}/r5_cat_*.json")):
    for e in json.load(open(f)):
        cats[e["sym"]] = e
for sym, c in cond.items():
    n = news.get(sym, {})
    cat = cats.get(sym, {})
    out[sym] = {
        "decline_short": c["decline_short"],
        "recovery_short": c["recovery_short"],
        "hot": c.get("hot") or [],
        "catalyst": (cat.get("catalyst") or "").strip(),
        "ckind": (cat.get("ckind") or "無").strip(),
        "confidence": n.get("confidence", "低"),
        "sources": n.get("sources", []),
        "decline_full": n.get("decline_zh", ""),
        "recovery_full": n.get("recovery_zh", ""),
    }
    if sym not in cats:
        problems.append(f"{sym}: no catalyst label")

res_files = sorted(glob.glob(f"{AGENT_DIR}/r5_res_*.json"),
                   key=lambda p: int(p.rsplit("_", 1)[1].split(".")[0]))
for f in res_files:
    for e in json.load(open(f)):
        sym = e["sym"]
        if sym in out:
            problems.append(f"{sym}: duplicate entry in {os.path.basename(f)}")
            continue
        out[sym] = {
            "decline_short": e["decline_short"],
            "recovery_short": e["recovery_short"],
            "hot": e.get("hot") or [],
            "catalyst": (e.get("catalyst") or "").strip(),
            "ckind": (e.get("ckind") or "無").strip(),
            "confidence": e.get("confidence", "低"),
            "sources": e.get("sources", []),
        }

for sym, e in out.items():
    bad = [h for h in e["hot"] if h not in e["recovery_short"]]
    if bad:
        problems.append(f"{sym}: hot span not in recovery text -> {bad}")
        e["hot"] = [h for h in e["hot"] if h in e["recovery_short"]]
    if e["catalyst"] and e["ckind"] == "無":
        problems.append(f"{sym}: catalyst set but ckind 無")
    if len(e["catalyst"]) > 14:
        problems.append(f"{sym}: catalyst too long ({len(e['catalyst'])}) -> {e['catalyst']}")

missing = [s for s in need if s not in out]
extra = [s for s in out if s not in need]
print(f"page1 tickers {len(need)} · merged entries {len(out)} · "
      f"missing {len(missing)} · extra {len(extra)}")
if missing: print("MISSING:", missing)
if extra: print("extra (not listed, kept):", extra[:20])
kinds = {}
for s in need:
    e = out.get(s)
    if not e: continue
    k = e["ckind"] if e["catalyst"] else "無"
    kinds[k] = kinds.get(k, 0) + 1
print("catalyst kinds:", dict(sorted(kinds.items(), key=lambda x: -x[1])))
conf = {}
for s in need:
    e = out.get(s)
    if e: conf[e["confidence"]] = conf.get(e["confidence"], 0) + 1
print("confidence:", conf)
if problems:
    print(f"PROBLEMS ({len(problems)}):")
    for p in problems: print("  -", p)

json.dump(out, open(f"{SCRATCH}/news5.json", "w"), ensure_ascii=False, indent=1)
print("wrote", f"{SCRATCH}/news5.json")
sys.exit(1 if missing else 0)

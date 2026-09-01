#!/usr/bin/env python3
"""Merge R7 news inputs into data/news7.json — one entry per listed ticker.

R7 carries the R6 research forward for every ticker it already covered and adds
the names new to the 2026-09-01 scan, so only genuinely new tickers need fresh
research.

Sources:
  data/news6.json           research carried over from R6
  scratchpad r7_res_*.json  condensed text + hot + catalyst for the new names
  scratchpad r7_redo_*.json re-runs for a new name a first pass could not cover

Validates that every page-1 ticker is covered, that each hot span really occurs
in its recovery text, and reports anything missing instead of silently dropping.
"""
import glob, json, os, sys

SCRATCH = os.environ.get("WORK_DIR", "./data")
AGENT_DIR = os.environ.get("AGENT_DIR",
                           "/tmp/claude-0/-home-user-10MA-watchlist/"
                           "1821eb3b-7002-5041-b904-77ace4d47850/scratchpad")

scr = json.load(open(f"{SCRATCH}/screen_results7.json"))
need = [r["sym"] for r in scr["page1"]]
prev = json.load(open(f"{SCRATCH}/news6.json"))

out, problems = {}, []

for sym, e in prev.items():
    out[sym] = dict(e)

def batch_no(p):
    return int(p.rsplit("_", 1)[1].split(".")[0])

# redo files come last on purpose: they re-researched tickers whose first pass
# ran out of search budget, so their entries supersede the empty ones.
def numbered(pattern):
    # the agents' input files sit beside their outputs; keep only r5_x_<n>.json
    return sorted((p for p in glob.glob(pattern)
                   if p.rsplit("_", 1)[1].split(".")[0].isdigit()), key=batch_no)

res_files = numbered(f"{AGENT_DIR}/r7_res_*.json") + numbered(f"{AGENT_DIR}/r7_redo_*.json")
redone = []
for f in res_files:
    is_redo = "r5_redo_" in f
    for e in json.load(open(f)):
        sym = e["sym"]
        if sym in out:
            if is_redo:
                redone.append(sym)
            else:
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
unsourced = [s for s in need if s in out and not out[s]["sources"]]
print(f"page1 tickers {len(need)} · merged entries {len(out)} · "
      f"missing {len(missing)} · extra {len(extra)}")
if redone: print(f"re-researched (redo pass superseded first pass): {sorted(set(redone))}")
if unsourced: print(f"still no company-specific sources ({len(unsourced)}): {unsourced}")
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

json.dump(out, open(f"{SCRATCH}/news7.json", "w"), ensure_ascii=False, indent=1)
print("wrote", f"{SCRATCH}/news7.json")
sys.exit(1 if missing else 0)

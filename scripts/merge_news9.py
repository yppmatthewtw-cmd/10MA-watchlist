#!/usr/bin/env python3
"""Build data/news9.json: news8 carried forward + the R9 additions (later
revisions reuse it with PREV_NEWS / OUT_NEWS / SCREEN_JSON / SERIES / AGENT_PREFIX).

Two kinds of input from the research agents in the session scratchpad:
  r9_res_*.json    full entries for tickers new to the R9 lists (with cat_line)
  r9_lines_*.json  {ticker: cat_line} for the tickers carried over from R8 —
                   the new 催化 column's one-liner, summarised from that
                   ticker's own existing text, not researched afresh

Everything from R8 keeps its text; only cat_line is added. The merge then runs
the same consistency checks the R8 review introduced (news_checks.py) and
reports what is missing rather than dropping it silently.
"""
import glob, json, os, sys

SCRATCH = os.environ.get("WORK_DIR", "./data")
AGENT_DIR = os.environ.get("AGENT_DIR",
                           "/tmp/claude-0/-home-user-10MA-watchlist/"
                           "1821eb3b-7002-5041-b904-77ace4d47850/scratchpad")
PREV_NEWS = os.environ.get("PREV_NEWS", "news8.json")
OUT = os.environ.get("OUT_NEWS", "news9.json")
SCREEN = os.environ.get("SCREEN_JSON", "screen_results9.json")
# which session's agent files to read: r9_res_*.json / r9_lines_*.json by default
PREFIX = os.environ.get("AGENT_PREFIX", "r9")

scr = json.load(open(f"{SCRATCH}/{SCREEN}"))
need = [r["sym"] for r in scr["page1"]]
out = json.load(open(f"{SCRATCH}/{PREV_NEWS}"))
problems, added, lines_set = [], [], 0

FIELDS = ("decline_short", "recovery_short", "hot", "catalyst", "ckind", "confidence", "sources", "cat_line")


def numbered(pattern):
    return sorted((p for p in glob.glob(pattern)
                   if p.rsplit("_", 1)[1].split(".")[0].isdigit()),
                  key=lambda p: int(p.rsplit("_", 1)[1].split(".")[0]))


for f in numbered(f"{AGENT_DIR}/{PREFIX}_res_*.json"):
    for e in json.load(open(f)):
        sym = e.get("sym")
        if not sym:
            problems.append(f"{os.path.basename(f)}: entry without a sym"); continue
        if sym in out and sym not in added:
            problems.append(f"{sym}: already in {PREV_NEWS}; research entry ignored"); continue
        out[sym] = {
            "decline_short": (e.get("decline_short") or "").strip(),
            "recovery_short": (e.get("recovery_short") or "").strip(),
            "hot": e.get("hot") or [],
            "catalyst": (e.get("catalyst") or "").strip(),
            "ckind": (e.get("ckind") or "無").strip(),
            "confidence": (e.get("confidence") or "低").strip(),
            "sources": e.get("sources") or [],
            "cat_line": (e.get("cat_line") or "").strip(),
        }
        added.append(sym)

for f in numbered(f"{AGENT_DIR}/{PREFIX}_lines_*.json"):
    for sym, line in json.load(open(f)).items():
        if sym not in out:
            problems.append(f"{sym}: cat_line for a ticker with no news entry"); continue
        line = (line or "").strip()
        if len(line) > 44:   # ~26 CJK chars, plus digits and latin tickers
            problems.append(f"{sym}: cat_line too long ({len(line)}) -> {line}")
        out[sym]["cat_line"] = line
        lines_set += 1

# a catalyst line that claims an event while the badge says 跟大市 (or the other
# way round) would put two different stories in the same row
for sym in need:
    e = out.get(sym)
    if not e: continue
    line = (e.get("cat_line") or "").strip()
    has_cat = bool((e.get("catalyst") or "").strip())
    if not line:
        problems.append(f"{sym}: no cat_line")
    elif line.startswith("無個股催化") and has_cat:
        problems.append(f"{sym}: cat_line says 無個股催化 but the badge is «{e['catalyst']}»")
    elif has_cat is False and not line.startswith("無個股催化"):
        problems.append(f"{sym}: badge is 跟大市 but cat_line claims «{line}»")
    for k in FIELDS:
        e.setdefault(k, [] if k in ("hot", "sources") else "")

missing = [s for s in need if s not in out]
unsourced = [s for s in need if s in out and not out[s]["sources"]]
print(f"listed {len(need)} · entries {len(out)} · newly researched {len(added)} · "
      f"cat_line set {lines_set} · missing {len(missing)}")
if added: print("  new:", added)
if missing: print("  MISSING:", missing)
if unsourced: print(f"  no company-specific sources ({len(unsourced)}): {unsourced}")

kinds, conf = {}, {}
for s in need:
    e = out.get(s)
    if not e: continue
    k = e["ckind"] if e["catalyst"] else "無"
    kinds[k] = kinds.get(k, 0) + 1
    conf[e["confidence"]] = conf.get(e["confidence"], 0) + 1
print("catalyst kinds:", dict(sorted(kinds.items(), key=lambda x: -x[1])), "| confidence:", conf)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from news_checks import run_checks
warns = run_checks(out, need, f"{SCRATCH}/{os.environ.get('SERIES', 'series5.pkl')}", scr)
if warns:
    print(f"CHECKS ({len(warns)} warning(s) — text vs series / sources / deal prices):")
    for w in warns: print("  ~", w)
if problems:
    print(f"PROBLEMS ({len(problems)}):")
    for p in problems: print("  -", p)

json.dump(out, open(f"{SCRATCH}/{OUT}", "w"), ensure_ascii=False, indent=1)
print("wrote", f"{SCRATCH}/{OUT}")
sys.exit(1 if missing else 0)

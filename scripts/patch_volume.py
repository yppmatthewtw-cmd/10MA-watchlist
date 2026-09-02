#!/usr/bin/env python3
"""Replace one day's volumes in a series with a later, more complete snapshot.

The runner's snapshot is taken ~2h after the close; the mirror's lands ~30 min
later and carries the late consolidated prints for a few dozen names. Prices are
identical (checked: 7,153/7,153 on 2026-09-01), so only volume is touched, and
only where the later print is higher. Records what changed so the report can
say so.
"""
import csv, io, json, os, pickle, subprocess, sys

SCRATCH = os.environ.get("WORK_DIR", "./data")
SERIES = os.environ.get("SERIES", "series4.pkl")
DATE = os.environ.get("TRADE_DATE", "2026-09-01")
ZREPO = os.environ.get("TICKERS_REPO", "/home/user/zyhe16/top-us-stock-tickers")

blob = subprocess.run(["git", "-C", ZREPO, "show", "HEAD:data/v2/tickers.csv"],
                      capture_output=True, text=True, check=True).stdout
later = {}
for r in csv.DictReader(io.StringIO(blob.lstrip("﻿"))):
    try:
        later[r["symbol"].strip()] = (float(r["price"]), float(r["volume"] or 0))
    except ValueError:
        pass

d = pickle.load(open(f"{SCRATCH}/{SERIES}", "rb"))
CAL, SER = d["cal"], d["series"]
if CAL[-1] != DATE:
    sys.exit(f"{SERIES} ends {CAL[-1]}, not {DATE}")

changed, price_mismatch = [], 0
for sym, (fi, cs, vs, ff) in SER.items():
    if fi + len(cs) != len(CAL) or sym not in later:
        continue
    p, v = later[sym]
    if abs(p - cs[-1]) > 1e-6:
        price_mismatch += 1          # never expected; refuse to touch such a row
        continue
    if v > vs[-1] * 1.01:
        changed.append((sym, vs[-1], v))
        vs[-1] = v
print(f"{DATE}: {len(changed)} volumes raised to the later print, {price_mismatch} price mismatches (untouched)")
pickle.dump({"cal": CAL, "series": SER}, open(f"{SCRATCH}/{SERIES}", "wb"))
json.dump({"date": DATE, "changed": [{"sym": s, "from": a, "to": b} for s, a, b in changed]},
          open(f"{SCRATCH}/volume_patch_{DATE}.json", "w"))

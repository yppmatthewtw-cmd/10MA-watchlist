#!/usr/bin/env python3
"""Append one trading day to the rebuilt price series from a Nasdaq screener
snapshot fetched by .github/workflows/fetch_eod_snapshot.yml.

The snapshot carries the day's last sale, net change and volume, so the day
before it can be re-derived (last sale - net change) and checked against the
series we already have. A ticker whose implied previous close disagrees with
ours by more than 20% has had a corporate action (the big movers here are all
reverse splits) and its history is no longer on the same share basis, so it is
dropped rather than spliced onto silently.

Writes data/series3.pkl (cal, series) and data/mcap_latest.json.
"""
import csv, json, os, pickle, statistics, sys

SCRATCH = os.environ.get("WORK_DIR", "./data")
DATE = os.environ.get("TRADE_DATE", "2026-08-31")
SPLIT_TOL = 0.20

d = pickle.load(open(f"{SCRATCH}/series2.pkl", "rb"))
CAL, SER = list(d["cal"]), d["series"]
if CAL[-1] >= DATE:
    sys.exit(f"series already reaches {CAL[-1]}; nothing to append for {DATE}")

def num(x):
    x = (x or "").replace("$", "").replace(",", "").strip()
    try:
        return float(x)
    except ValueError:
        return None

snap, mcap = {}, {}
for r in csv.DictReader(open(f"{SCRATCH}/snapshots/{DATE}.csv", encoding="utf-8")):
    sym = r["symbol"].strip()
    p, v, ch = num(r["lastsale"]), num(r["volume"]), num(r["netchange"])
    if not sym or p is None or p <= 0:
        continue
    snap[sym] = (p, v or 0.0, ch)
    m = num(r["marketCap"])
    if m and m > 0:
        mcap[sym] = m
print(f"snapshot {DATE}: {len(snap)} priced symbols, {len(mcap)} with a market cap")

n_old = len(CAL)
CAL.append(DATE)

kept = dropped_split = missing = stale = 0
devs = []
split_syms, missing_syms = [], []
out = {}
for sym, (fi, cs, vs, ff) in SER.items():
    if fi + len(cs) != n_old:          # already not trading at the old end
        out[sym] = (fi, cs, vs, ff)
        stale += 1
        continue
    if sym not in snap:                 # no quote today -> stops being current
        out[sym] = (fi, cs, vs, ff)
        missing += 1
        if len(missing_syms) < 25:
            missing_syms.append(sym)
        continue
    p, v, ch = snap[sym]
    prev = cs[-1]
    if ch is not None and prev > 0:
        dev = abs((p - ch) - prev) / prev
        devs.append(dev)
        if dev > SPLIT_TOL:
            dropped_split += 1
            split_syms.append((sym, round(prev, 4), round(p - ch, 4)))
            continue                    # history is on a different share basis
    out[sym] = (fi, cs + [p], vs + [v], ff)
    kept += 1

devs.sort()
med = statistics.median(devs) if devs else 0.0
p99 = devs[int(len(devs) * 0.99)] if devs else 0.0
print(f"overlap vs implied previous close: n={len(devs)} median {med*100:.4f}% p99 {p99*100:.3f}%")
print(f"extended {kept} · no quote today {missing} · dropped (corporate action) {dropped_split} · already stale {stale}")
if split_syms:
    print("  dropped:", split_syms)
if missing_syms:
    print("  sample without a quote:", missing_syms)

pickle.dump({"cal": CAL, "series": out}, open(f"{SCRATCH}/series3.pkl", "wb"))
json.dump(mcap, open(f"{SCRATCH}/mcap_latest.json", "w"))
print(f"wrote {SCRATCH}/series3.pkl ({len(out)} tickers, {len(CAL)} days -> {CAL[-1]})")

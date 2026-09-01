#!/usr/bin/env python3
"""Append one trading day to the rebuilt price series from a Nasdaq screener
snapshot fetched by .github/workflows/fetch_eod_snapshot.yml.

The snapshot carries the day's last sale, net change and volume, so the day
before it can be re-derived (last sale - net change) and checked against the
series we already have. A ticker whose implied previous close disagrees with ours by more than 20% has
had a corporate action. When the ratio lands on a clean split factor (3:2, 1:12,
1:20 ...) the history is rescaled onto the new share basis - prices by the ratio,
volumes inversely, which leaves dollar volume untouched - so the ticker keeps its
series. Anything else is dropped rather than spliced onto silently.

Chainable: IN_SERIES / OUT_SERIES / TRADE_DATE select the input series, the
output series and the day being appended, so each new session extends the
previous one. Also writes data/mcap_latest.json from the same snapshot.
"""
import csv, json, os, pickle, statistics, sys
from fractions import Fraction

SCRATCH = os.environ.get("WORK_DIR", "./data")
DATE = os.environ.get("TRADE_DATE", "2026-08-31")
IN_SERIES = os.environ.get("IN_SERIES", "series2.pkl")
OUT_SERIES = os.environ.get("OUT_SERIES", "series3.pkl")
SPLIT_TOL = 0.20        # beyond this the day-over-day move is a corporate action
SPLIT_FIT = 0.005       # a real split ratio is exact, so demand a tight fit
SPLIT_MAX_TERM = 40     # largest side of the ratio (1-for-30 reverse splits happen)
SPLIT_MIN_TERM = 5      # ... and the other side is always small (n:1, 3:2, 5:4)

def split_factor(ratio):
    """Return the clean split ratio near `ratio`, or None if it is not one.

    Splits are exact ratios with one small side, which is what separates them
    from a penny stock or warrant that simply moved more than SPLIT_TOL in a
    day — that move fits some awkward fraction, and rescaling on it would
    silently rewrite the ticker's whole history.
    """
    if ratio <= 0:
        return None
    f = Fraction(ratio).limit_denominator(SPLIT_MAX_TERM)
    lo, hi = sorted((f.numerator, f.denominator))
    if lo > SPLIT_MIN_TERM or hi > SPLIT_MAX_TERM:
        return None
    exact = f.numerator / f.denominator
    return exact if abs(exact - ratio) / ratio <= SPLIT_FIT else None

d = pickle.load(open(f"{SCRATCH}/{IN_SERIES}", "rb"))
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

kept = dropped_split = rescaled = missing = stale = 0
devs = []
split_syms, rescale_syms, missing_syms = [], [], []
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
            factor = split_factor((p - ch) / prev)
            if factor is None:
                dropped_split += 1
                split_syms.append((sym, round(prev, 4), round(p - ch, 4)))
                continue                # not a clean split; basis unknown
            # restate the history on the post-split basis (dollar volume is unchanged)
            cs = [c * factor for c in cs]
            vs = [x / factor for x in vs]
            rescaled += 1
            rescale_syms.append((sym, f"{Fraction(factor).limit_denominator(SPLIT_MAX_TERM)}"))
    out[sym] = (fi, cs + [p], vs + [v], ff)
    kept += 1

devs.sort()
med = statistics.median(devs) if devs else 0.0
p99 = devs[int(len(devs) * 0.99)] if devs else 0.0
print(f"overlap vs implied previous close: n={len(devs)} median {med*100:.4f}% p99 {p99*100:.3f}%")
print(f"extended {kept} (of which rescaled for a split {rescaled}) · no quote today {missing} · "
      f"dropped (corporate action) {dropped_split} · already stale {stale}")
if rescale_syms:
    print("  rescaled:", rescale_syms)
if split_syms:
    print("  dropped:", split_syms)
if missing_syms:
    print("  sample without a quote:", missing_syms)

pickle.dump({"cal": CAL, "series": out}, open(f"{SCRATCH}/{OUT_SERIES}", "wb"))
json.dump(mcap, open(f"{SCRATCH}/mcap_latest.json", "w"))
print(f"wrote {SCRATCH}/{OUT_SERIES} ({len(out)} tickers, {len(CAL)} days -> {CAL[-1]})")

#!/usr/bin/env python3
"""Append two trading days when only the later day's close snapshot exists.

The 09-01 → 09-03 case: our Actions runner fetches the Nasdaq screener after
the close, so the snapshot carries the day's close, its net change and its
volume. The net change re-derives the *previous* close exactly, which is the
only record of 09-02 we can get — the mirror's own commit that day landed at
10:33 ET, mid-session. So:

  * 09-02 gets a real close (lastsale - netchange) and **no volume** (0). Every
    volume metric in the screener skips a zero-volume day, the same way it
    already skips copied and partial-volume days, so nothing is fabricated.
  * 09-03 gets the close and the full-session volume from the snapshot.

Corporate actions cannot be caught by the usual overlap test (there is no day
where our series and the snapshot describe the same session), so the mirror's
mid-session 09-02 prices are used as a pivot:

    leg A = mirror 09-02 intraday / our 09-01 close   -> an action on 09-02
    leg B = derived 09-02 close   / mirror 09-02      -> an action on 09-03

Intraday pivots cannot separate a 3:2 split from a real 33% day, so only the
unambiguous case is rescaled automatically: a leg that at least halves or
doubles, lands on an n:1 / 1:n ratio within SPLIT_FIT, and belongs to a ticker
the screener could actually list (close >= $2, 20-day median dollar volume >=
$1M) — an overnight ±50% in a name that liquid is a corporate action, not a
trade. Smaller ratios and illiquid tickers are left on their real prices and
printed for review; unlike the same-day overlap check in extend_series.py, a
large day-over-day move here is ordinary and must not be treated as a splice
error.
"""
import csv, io, json, os, pickle, statistics, subprocess, sys
from fractions import Fraction

SCRATCH = os.environ.get("WORK_DIR", "./data")
ZREPO = os.environ.get("TICKERS_REPO", "/home/user/zyhe16/top-us-stock-tickers")
IN_SERIES = os.environ.get("IN_SERIES", "series4.pkl")
OUT_SERIES = os.environ.get("OUT_SERIES", "series5.pkl")
GAP_DATE = os.environ.get("GAP_DATE", "2026-09-02")     # derived close, no volume
DATE = os.environ.get("TRADE_DATE", "2026-09-03")       # the snapshot's own day
PIVOT_REF = os.environ.get("PIVOT_REF", "")             # mirror commit for GAP_DATE
AMBIG = (0.60, 1.65)    # inside this band a split and a real day are indistinguishable
SPLIT_FIT = 0.03        # the pivot is an intraday price, so allow 3% around the ratio
REVIEW_TOL = 0.20       # smaller moves in listable names are printed, never rescaled
MIN_PX, MIN_DV = 2.0, 1_000_000
COMMON = [Fraction(1, n) for n in range(2, 41)] + [Fraction(n, 1) for n in range(2, 41)]


def split_factor(ratio):
    """The n:1 / 1:n ratio `ratio` sits on, or None if it is a real move."""
    if ratio <= 0 or AMBIG[0] < ratio < AMBIG[1]:
        return None
    best = min(COMMON, key=lambda f: abs(float(f) - ratio))
    ex = float(best)
    return ex if abs(ex - ratio) / ratio <= SPLIT_FIT else None


def num(x):
    x = (x or "").replace("$", "").replace(",", "").strip()
    try:
        return float(x)
    except ValueError:
        return None


d = pickle.load(open(f"{SCRATCH}/{IN_SERIES}", "rb"))
CAL, SER = list(d["cal"]), d["series"]
if CAL[-1] >= GAP_DATE:
    sys.exit(f"series already reaches {CAL[-1]}; nothing to append for {GAP_DATE}")

snap, mcap = {}, {}
for r in csv.DictReader(open(f"{SCRATCH}/snapshots/{DATE}.csv", encoding="utf-8")):
    sym = r["symbol"].strip()
    p, v, ch = num(r["lastsale"]), num(r["volume"]), num(r["netchange"])
    if not sym or p is None or p <= 0 or ch is None:
        continue
    snap[sym] = (p, v or 0.0, ch)
    m = num(r["marketCap"])
    if m and m > 0:
        mcap[sym] = m

# mid-session prices from the mirror commit that lands inside GAP_DATE
ref = PIVOT_REF or subprocess.run(
    ["git", "-C", ZREPO, "log", "--format=%H %cI", "-40", "--", "tickers/all.csv"],
    capture_output=True, text=True).stdout
if not PIVOT_REF:
    ref = next((ln.split()[0] for ln in ref.splitlines() if ln.split()[1][:10] == GAP_DATE), "")
    if not ref:
        sys.exit(f"no mirror commit inside {GAP_DATE}; cannot pivot the split check")
blob = subprocess.run(["git", "-C", ZREPO, "show", f"{ref}:tickers/all.csv"],
                      capture_output=True, text=True).stdout
pivot = {}
for r in csv.DictReader(io.StringIO(blob.lstrip("﻿"))):
    p = num(r.get("price"))
    if r.get("symbol") and p and p > 0:
        pivot[r["symbol"].strip()] = p
print(f"snapshot {DATE}: {len(snap)} priced symbols · mirror pivot {ref[:8]} ({GAP_DATE}): {len(pivot)} prices")

n_old = len(CAL)
CAL += [GAP_DATE, DATE]
kept = rescaled = missing = stale = nopivot = 0
rescale_syms, big_moves, missing_syms, unchecked, fractional = [], [], [], [], []
out = {}
for sym, (fi, cs, vs, ff) in SER.items():
    if fi + len(cs) != n_old:
        out[sym] = (fi, cs, vs, ff); stale += 1; continue
    if sym not in snap:
        out[sym] = (fi, cs, vs, ff); missing += 1
        if len(missing_syms) < 25: missing_syms.append(sym)
        continue
    p3, v3, ch = snap[sym]
    p2 = p3 - ch                       # the 09-02 close, exact
    prev = cs[-1]
    if p2 <= 0 or prev <= 0:
        out[sym] = (fi, cs, vs, ff); missing += 1; continue
    mp = pivot.get(sym)
    # the screener measures liquidity over the last 20 days that carry a volume
    # figure; measuring it over raw calendar days here would put names either
    # side of the $1M line depending on which script you asked
    _gv = [j for j in range(len(cs)) if vs[j] > 0][-20:]
    listable = prev >= MIN_PX and _gv and statistics.median([cs[j] * vs[j] for j in _gv]) >= MIN_DV
    factor = 1.0
    if mp and listable:
        for leg in ((mp / prev), (p2 / mp)):
            f = split_factor(leg)
            if f: factor *= f
        if factor != 1.0:
            cs = [c * factor for c in cs]
            vs = [x / factor for x in vs]
            rescaled += 1
            rescale_syms.append((sym, f"{Fraction(factor).limit_denominator(40)}",
                                 round(prev, 2), round(mp, 2), round(p2, 2)))
        elif max(abs(mp / prev - 1), abs(p2 / mp - 1)) > REVIEW_TOL:
            big_moves.append((sym, round(prev, 3), round(mp, 3), round(p2, 3)))
            for lab, leg in (("09-02", mp / prev), ("09-03", p2 / mp)):
                for fr in (Fraction(3, 2), Fraction(2, 3), Fraction(4, 3), Fraction(3, 4),
                           Fraction(5, 4), Fraction(4, 5), Fraction(5, 3), Fraction(3, 5)):
                    if abs(float(fr) - leg) / leg <= 0.012:
                        fractional.append((sym, lab, f"{fr}", round(leg, 4)))
    elif not mp:
        nopivot += 1
        if listable and abs(p2 / prev - 1) > 0.25:
            unchecked.append((sym, round(prev, 3), round(p2, 3), round((p2 / prev - 1) * 100, 1)))
    if factor != 1.0 and sym in mcap:
        # the vendor halves the price on a split but keeps the pre-split share
        # count, so its market cap moves with the price; undo that
        mcap[sym] = mcap[sym] / factor
    out[sym] = (fi, cs + [p2, p3], vs + [0.0, v3], ff)
    kept += 1

print(f"extended {kept} · rescaled for a split {rescaled} · no quote in the snapshot {missing} · "
      f"already stale {stale} · no mirror pivot {nopivot}")
if rescale_syms: print("  rescaled:", rescale_syms)
if big_moves:
    print(f"  listable names with a >{REVIEW_TOL:.0%} leg, kept on their real prices "
          f"(sym, 09-01 close, mirror 09-02 intraday, 09-02 close):")
    for b in sorted(big_moves, key=lambda x: -abs(x[3] / x[1] - 1))[:20]: print("   ", b)
if unchecked:
    print("  NO CORPORATE-ACTION CHECK POSSIBLE (listable, no mirror pivot, >25% over two days):")
    for u in unchecked: print("   !", u)
if fractional:
    print("  fractional-ratio candidates — NOT rescaled, verify by hand if a split is announced:")
    for x in fractional: print("   ?", x)
if missing_syms: print("  sample without a quote:", missing_syms)

pickle.dump({"cal": CAL, "series": out}, open(f"{SCRATCH}/{OUT_SERIES}", "wb"))
json.dump(mcap, open(f"{SCRATCH}/mcap_latest.json", "w"))
print(f"wrote {SCRATCH}/{OUT_SERIES} ({len(out)} tickers, {len(CAL)} days -> {CAL[-1]}); "
      f"{GAP_DATE} carries closes only (volume 0 = no data)")

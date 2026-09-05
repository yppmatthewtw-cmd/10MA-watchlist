#!/usr/bin/env python3
"""Cross-check the Nasdaq-screener price series against Yahoo Finance daily bars
and fill the days that have no real data, writing a new series and a report.

What gets filled (only where Yahoo has the ticker and the bars around the day
agree with ours, so both sources are on the same share basis):
  * copied days   — the mirror published no snapshot, so close and volume were
                    carried forward: both replaced by Yahoo's bar;
  * price-only    — 09-02, re-derived from the next day's net change: the close
                    is kept (it is exact) and only the volume is filled;
  * partial-volume days — the snapshot was taken before the tape was complete:
                    the volume is replaced, the close kept.
Every other day is compared, never changed: the report lists how well the two
sources agree, per day and per ticker, and the 09-04 close — which has no
second snapshot of its own — is checked the same way.

Yahoo's unadjusted close is split-adjusted (its history is restated onto the
current share basis, as ours is after extend_series.py's rescale) but not
dividend-adjusted, which is the right comparator for a last-sale series.

Env: WORK_DIR, IN_SERIES (series6.pkl), YAHOO (the .csv.gz from
scripts/fetch_yahoo.py), OUT_SERIES (series7.pkl), OUT_REPORT
(yahoo_crosscheck.json). Day classes are detected the same way screener9 does.
"""
import csv, gzip, json, os, pickle, statistics, sys

SCRATCH = os.environ.get("WORK_DIR", "./data")
IN_SERIES = os.environ.get("IN_SERIES", "series6.pkl")
OUT_SERIES = os.environ.get("OUT_SERIES", "series7.pkl")
OUT_REPORT = os.environ.get("OUT_REPORT", "yahoo_crosscheck.json")
YAHOO = os.environ.get("YAHOO", "")
CLOSE_TOL = 0.005        # closes agree when within 0.5%
BASIS_TOL = 0.01         # ... and a fill needs the neighbouring days within 1%

d = pickle.load(open(f"{SCRATCH}/{IN_SERIES}", "rb"))
CAL, SER = list(d["cal"]), d["series"]
N = len(CAL); IDX = {c: i for i, c in enumerate(CAL)}

if not YAHOO:
    cands = sorted(p for p in os.listdir(f"{SCRATCH}/yahoo") if p.startswith("eod_") and p.endswith(".csv.gz"))
    if not cands:
        sys.exit("no data/yahoo/eod_*.csv.gz; run the fetch_yahoo_eod workflow first")
    YAHOO = f"{SCRATCH}/yahoo/{cands[-1]}"
Y = {}
with gzip.open(YAHOO, "rt") as f:
    for r in csv.DictReader(f):
        try:
            c, v = float(r["close"]), float(r["volume"] or 0)
        except ValueError:
            continue
        if c > 0:
            Y.setdefault(r["symbol"], {})[r["date"]] = (c, v, float(r.get("adj_close") or c))
ydates = sorted({dt for m in Y.values() for dt in m})
print(f"yahoo: {len(Y)} symbols, {len(ydates)} dates {ydates[0]}..{ydates[-1]} from {os.path.basename(YAHOO)}")
cal_only = [c for c in CAL if c not in set(ydates)]
yahoo_only = [c for c in ydates if c not in IDX]
if cal_only or yahoo_only:
    print("calendar mismatch — in our series only:", cal_only, "| in yahoo only:", yahoo_only)

# ---- day classes, detected as screener9 does -----------------------------
cur = [s for s, (fi, cs, vs, ff) in SER.items() if fi + len(cs) == N]
SYN, NOVOL, PARTIAL = set(), set(), set()
for k in range(1, N):
    same = tot = zero = 0; ratios = []
    for s in cur:
        fi, cs, vs, ff = SER[s]; j = k - fi
        if j >= 1:
            tot += 1
            if cs[j] == cs[j - 1] and vs[j] == vs[j - 1]: same += 1
            if vs[j] == 0: zero += 1
        if j >= 21 and vs[j] > 0:
            m = statistics.median(vs[j - 20:j])
            if m > 0: ratios.append(vs[j] / m)
    if tot and same / tot > 0.98: SYN.add(k)
    if tot and zero / tot > 0.90: NOVOL.add(k)
    if ratios and statistics.median(ratios) < 0.7: PARTIAL.add(k)
SYN -= NOVOL
print("copied:", [CAL[k] for k in sorted(SYN)], "| price-only:", [CAL[k] for k in sorted(NOVOL)],
      "| partial-volume:", [CAL[k] for k in sorted(PARTIAL)])
FILL_DAYS = SYN | NOVOL | PARTIAL

# ---- compare, day by day ---------------------------------------------------
day_stats = {}          # date -> {n, med_abs_pct, within_tol_pct, vol_med_ratio}
tick_bad = {}           # sym -> [(date, ours, yahoo, pct)] for closes off by > tol on real days
for k, day in enumerate(CAL):
    diffs, vr = [], []
    for s in cur:
        m = Y.get(s)
        if not m or day not in m: continue
        fi, cs, vs, ff = SER[s]; j = k - fi
        if j < 0: continue
        yc, yv, _ = m[day]
        pct = (cs[j] / yc - 1) * 100
        diffs.append(abs(pct))
        if vs[j] > 0 and yv > 0: vr.append(vs[j] / yv)
        if k not in FILL_DAYS and abs(pct) > CLOSE_TOL * 100:
            tick_bad.setdefault(s, []).append((day, cs[j], yc, round(pct, 2)))
    if diffs:
        day_stats[day] = {"n": len(diffs), "med_abs_pct": round(statistics.median(diffs), 3),
                          "within_tol_pct": round(100 * sum(1 for x in diffs if x <= CLOSE_TOL * 100) / len(diffs), 1),
                          "vol_med_ratio": round(statistics.median(vr), 3) if vr else None,
                          "cls": "copied" if k in SYN else "price_only" if k in NOVOL else "partial_vol" if k in PARTIAL else "real"}

# ---- fill -------------------------------------------------------------------
out = {}
fills = {CAL[k]: {"close_and_volume": 0, "volume_only": 0, "skipped_basis": 0, "no_yahoo": 0} for k in sorted(FILL_DAYS)}
filled_syms = set()
for s, (fi, cs, vs, ff) in SER.items():
    cs, vs = list(cs), list(vs)
    m = Y.get(s)
    for k in sorted(FILL_DAYS):
        j = k - fi
        if j < 0 or j >= len(cs): continue
        day = CAL[k]; rec = fills[day]
        if not m or day not in m:
            rec["no_yahoo"] += 1; continue
        yc, yv, _ = m[day]
        # same share basis? the nearest real days on both sides must agree
        ok = True
        for jj in (j - 1, j + 1):
            kk = fi + jj
            if 0 <= jj < len(cs) and kk not in FILL_DAYS and CAL[kk] in m:
                if abs(cs[jj] / m[CAL[kk]][0] - 1) > BASIS_TOL: ok = False
        if not ok:
            rec["skipped_basis"] += 1; continue
        if k in SYN:
            cs[j] = round(yc, 4); vs[j] = yv; rec["close_and_volume"] += 1
        else:                                   # price-only / partial: the close stands
            if yv > 0:
                vs[j] = yv; rec["volume_only"] += 1
        filled_syms.add(s)
    out[s] = (fi, cs, vs, ff)

pickle.dump({"cal": CAL, "series": out}, open(f"{SCRATCH}/{OUT_SERIES}", "wb"))

worst = sorted(((s, max(abs(x[3]) for x in v), len(v)) for s, v in tick_bad.items()), key=lambda x: -x[1])
report = {
    "yahoo_file": os.path.basename(YAHOO), "yahoo_symbols": len(Y), "series_symbols": len(SER), "current_symbols": len(cur),
    "compared_symbols": sum(1 for s in cur if s in Y),
    "fill_days": {CAL[k]: ("copied" if k in SYN else "price_only" if k in NOVOL else "partial_vol") for k in sorted(FILL_DAYS)},
    "fills": fills, "filled_symbols": len(filled_syms),
    "day_stats": day_stats,
    "tickers_off_on_real_days": len(tick_bad),
    "worst": [{"sym": s, "max_abs_pct": round(mx, 2), "days": n, "sample": tick_bad[s][:3]} for s, mx, n in worst[:25]],
    "calendar_only_ours": cal_only, "calendar_only_yahoo": yahoo_only,
}
json.dump(report, open(f"{SCRATCH}/{OUT_REPORT}", "w"), ensure_ascii=False, indent=1)

real = [v for v in day_stats.values() if v["cls"] == "real"]
print(f"compared {report['compared_symbols']}/{len(cur)} current tickers; real days: median of daily median |diff| "
      f"{statistics.median(v['med_abs_pct'] for v in real):.3f}%, within 0.5%: {statistics.median(v['within_tol_pct'] for v in real):.1f}%")
for day in sorted(fills):
    print(f"  {day} ({report['fill_days'][day]}): {fills[day]}  | yahoo-vs-ours {day_stats.get(day)}")
print(f"09-04: {day_stats.get(CAL[-1])}")
print(f"tickers with a >0.5% close difference on a real day: {len(tick_bad)}; worst: {[(s, mx, n) for s, mx, n in worst[:8]]}")
print("wrote", f"{SCRATCH}/{OUT_SERIES}", "and", f"{SCRATCH}/{OUT_REPORT}")

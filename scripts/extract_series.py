#!/usr/bin/env python3
"""v2: union(all.csv, sp500.csv) per snapshot; align to official US trading calendar;
bounded forward-fill; official 08-27 correction; validate vs R1."""
import os, subprocess, csv, io, datetime, pickle

SCRATCH = os.environ.get("WORK_DIR", "./data")
REPO = os.environ.get("TICKERS_REPO", "/home/user/zyhe16/top-us-stock-tickers")

HOLIDAYS = {
    "2025-11-27", "2025-12-25",
    "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25",
    "2026-06-19", "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25",
}
def is_td(d): return d.weekday() < 5 and d.isoformat() not in HOLIDAYS
def prev_td(d):
    d -= datetime.timedelta(days=1)
    while not is_td(d): d -= datetime.timedelta(days=1)
    return d
def us_dst(d):
    # US DST: second Sunday of March through first Sunday of November
    import calendar
    mar = [x for x in calendar.Calendar().itermonthdates(d.year, 3)
           if x.month == 3 and x.weekday() == 6][1]
    nov = [x for x in calendar.Calendar().itermonthdates(d.year, 11)
           if x.month == 11 and x.weekday() == 6][0]
    return mar <= d < nov

def commit_to_date(ts):
    d = ts.date()
    # US close = 16:00 ET = 20:00 UTC during DST, 21:00 UTC in standard time
    cutoff = 20 if us_dst(d) else 21
    return d if (ts.hour >= cutoff and is_td(d)) else prev_td(d)

log = subprocess.run(["git", "-C", REPO, "log", "--format=%H|%aI|%s"],
                     capture_output=True, text=True, check=True).stdout
by_date = {}
for line in log.strip().split("\n"):
    sha, iso, subj = line.split("|", 2)
    if "auto-update ticker lists" not in subj.lower(): continue
    ts = datetime.datetime.fromisoformat(iso).astimezone(datetime.timezone.utc)
    dd = commit_to_date(ts).isoformat()
    if dd not in by_date or ts > by_date[dd][0]:
        by_date[dd] = (ts, sha)

snap_dates = sorted(by_date)
# full trading calendar between first and last snapshot date
d0 = datetime.date.fromisoformat(snap_dates[0]); d1 = datetime.date.fromisoformat(snap_dates[-1])
cal = []
d = d0
while d <= d1:
    if is_td(d): cal.append(d.isoformat())
    d += datetime.timedelta(days=1)
missing = [x for x in cal if x not in by_date]
print(f"trading days {len(cal)}, snapshots {len(snap_dates)}, missing {len(missing)}: {missing}")

close, vol = {}, {}
def ingest(blob, ddate):
    for row in csv.DictReader(io.StringIO(blob.lstrip("﻿"))):
        try:
            sym = row["symbol"].strip(); p = float(row["price"]); v = float(row["volume"] or 0)
        except (ValueError, KeyError, TypeError): continue
        if p <= 0 or not sym: continue
        close.setdefault(sym, {})[ddate] = p
        vol.setdefault(sym, {})[ddate] = v

for dd in snap_dates:
    _, sha = by_date[dd]
    for path in ("tickers/all.csv", "tickers/sp500.csv"):
        blob = subprocess.run(["git", "-C", REPO, "show", f"{sha}:{path}"],
                              capture_output=True, text=True).stdout
        if blob: ingest(blob, dd)

# official 08-27 correction from HEAD v2 (Nasdaq net-change implies official prev close);
# a 5% guard keeps the raw snapshot when the implied value diverges implausibly
# (verified: the 37 guarded tickers are all ineligible, so screening is unaffected)
blob = subprocess.run(["git", "-C", REPO, "show", "HEAD:data/v2/tickers.csv"],
                      capture_output=True, text=True).stdout
fixed = 0
for row in csv.DictReader(io.StringIO(blob.lstrip("﻿"))):
    sym = row["symbol"].strip()
    try: p = float(row["price"]); chg = float(row["price_change"])
    except (ValueError, TypeError): continue
    if sym in close and "2026-08-27" in close[sym]:
        op = round(p - chg, 4)
        if op > 0 and abs(op - close[sym]["2026-08-27"]) / op < 0.05:
            close[sym]["2026-08-27"] = op; fixed += 1
print("08-27 official corrections:", fixed)

# align each ticker to calendar with bounded ffill (gap <= 3 consecutive missing)
cal_idx = {d: i for i, d in enumerate(cal)}
series = {}   # sym -> (first_idx, [closes...], [vols...], ffill_count)
for sym, cmap in close.items():
    idxs = sorted(cal_idx[d] for d in cmap if d in cal_idx)
    if not idxs: continue
    fi, li = idxs[0], idxs[-1]
    cs, vs, ff, gap, ok = [], [], 0, 0, True
    vmap = vol.get(sym, {})
    lastc = lastv = None
    for i in range(fi, li + 1):
        d = cal[i]
        if d in cmap:
            lastc = cmap[d]; lastv = vmap.get(d, 0.0); gap = 0
        else:
            gap += 1; ff += 1
            if gap > 3: ok = False; break
        cs.append(lastc); vs.append(lastv)
    if ok:
        series[sym] = (fi, cs, vs, ff)

print(f"tickers aligned: {len(series)}")
pickle.dump({"cal": cal, "series": series}, open(f"{SCRATCH}/series2.pkl", "wb"))

# ---- validate vs R1 ----
R1 = {"CTSH": (64.33, 59.42), "WDAY": (204.11, 188.11), "NTAP": (186.86, 194.32),
      "FCX": (76.35, 71.16), "ORCL": (150.91, 146.99), "EMR": (155.26, 158.94),
      "TGT": (162.92, 156.13), "ACN": (189.36, 178.58), "HPQ": (30.42, 29.47),
      "BX": (142.99, 141.74), "AMGN": (431.49, 421.41), "GPN": (91.99, 90.41),
      "FDS": (306.56, 288.31), "LDOS": (140.66, 138.08), "NOW": (144.34, 125.46)}
print("\n== close/20MA vs R1 (calendar-aligned) ==")
devs = []
for t, (rc, rma) in R1.items():
    if t not in series: print(f"{t}: NO DATA"); continue
    fi, cs, vs, ff = series[t]
    c = cs[-1]; ma = sum(cs[-20:]) / 20
    dc = (c - rc) / rc * 100; dm = (ma - rma) / rma * 100
    devs.append(abs(dm))
    print(f"{t}: close {c:.2f} vs {rc} ({dc:+.2f}%) | 20MA {ma:.2f} vs {rma} ({dm:+.2f}%) | ffilled {ff}")
print(f"mean |20MA dev|: {sum(devs)/len(devs):.2f}%")

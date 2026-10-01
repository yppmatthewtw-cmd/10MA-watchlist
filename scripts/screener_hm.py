#!/usr/bin/env python3
"""Hot-money pull-back screen (R23 onward): stocks whose run-up was driven by
hot money and news, that had a 10MA uptrend, have pulled back to a rising
20-day moving average, and whose volatility has come down.

Replaces the top-decile-momentum screen of R21-R22 (screener_mp.py). The
universe, the price sources (Yahoo daily bars; Nasdaq snapshots audited
against them; intraday roll-up for an unpublished last day) and the bar
handling are unchanged; the setup, pages and scores are new.

Measured on the last close t, with H = highest close of the last 63 sessions
(set hi sessions ago) and the run-up leg = from the lowest close in the 63
sessions before H up to H:

  C1 熱錢＋消息  (a) event day: a session inside the leg (last 60 sessions, not
                after H) closing >= +8% on the day, or opening >= +5% above the
                previous close, on volume >= 3x the mean of the 50 sessions
                before it;  (b) hot money: mean dollar volume over the leg (at
                least the 5 sessions into H) >= 2x the mean over the 60
                sessions before the leg began.
  C2 曾有10MA上升 at some session t0 in the last 30 (t0 <= t-1) the R1-R20 10MA
                test held: MA10[t0] > MA10[t0-10] by >= 5%, MA10[t0] > MA10[t0-1]
                > MA10[t0-2], and MA10 rose on >= 7 of the 10 steps ending t0.
  C3 回落到20MA  MA20 above its value 5 sessions earlier; H set 2..25 sessions
                ago; close 3%..30% below H; at H the close sat >= 8% above that
                day's MA20; close within -3%..+3% of MA20 and the low of one of
                the last 3 sessions within 1.5% of that day's MA20 (undercuts
                count).
  C4 波幅減低    ATR5 / ATR20 <= 0.9, and the last 5 sessions' mean true range
                (as % of the prior close) <= 0.7x the leg's.
                True ranges count real bars only (a close-only hole day is
                skipped).

Pages: 總表 (all), 大型 / 中型 / 小型 by market cap (>= $10B / $2-10B / < $2B).

Scores (0-100; every term piecewise-linear and clipped, so the workbook can
recompute them from the inputs beside them):
  熱錢分數  0.4 lin(leg dollar-volume ratio, 2->0, 6->1) + 0.3 lin(event-day
            volume multiple, 3->0, 10->1) + 0.3 lin(leg gain, 25%->0, 100%->1)
  10MA分數  0.5 lin(best 10-session MA10 rise, 5%->0, 25%->1)
            + 0.5 lin(share of rising MA10 steps, 70%->0, 100%->1)
  回調質素  0.30 量縮 + 0.25 貼近20MA + 0.20 20MA斜率 + 0.10 回調深度 + 0.15 企穩
  波幅收窄  0.5 lin(ATR5/ATR20, 0.9->0, 0.5->1) + 0.5 lin(ATR5%/leg ATR%, 0.7->0, 0.3->1)
  綜合分數  0.25 熱錢 + 0.20 10MA + 0.30 回調質素 + 0.25 波幅收窄   (ranks every page)

Env: WORK_DIR (./data), YAHOO (.csv.gz), SUPP (comma list of supplement
.csv.gz: back-fill and/or intraday roll-up), SERIES (series pickle), SNAP_DATES
(comma list of snapshot files in data/snapshots; audited), OUT_JSON, LAST_DATE.
"""
import csv, gzip, io, json, math, os, pickle, re, statistics, subprocess, sys

import numpy as np

W_ = os.environ.get("WORK_DIR", "./data")
YAHOO = os.environ["YAHOO"]
SERIES = os.environ.get("SERIES", "")
SNAP_DATES = [x for x in os.environ.get("SNAP_DATES", "").split(",") if x]
OUT_JSON = os.environ.get("OUT_JSON", "screen_hm23.json")
ZREPO = os.environ.get("TICKERS_REPO", "/home/user/zyhe16/top-us-stock-tickers")
MC = os.environ.get("CHRONICLE_REPO", "/home/user/klaywang24/market-chronicle")
IRA = os.environ.get("OPENSTOCK_REPO", "/home/user/irachex/open-stock-data")

PQ_W = {"vol": 0.30, "near": 0.25, "slope": 0.20, "depth": 0.10, "hold": 0.15}
HOT_W = {"dv": 0.4, "evol": 0.3, "leg": 0.3}
TR_W = {"rise": 0.5, "frac": 0.5}
VC_W = {"c20": 0.5, "cleg": 0.5}
SCORE_W = {"hot": 0.25, "trend": 0.20, "pq": 0.30, "vc": 0.25}

# Every threshold in one place, so the sensitivity pass can move one at a time.
P0 = {
    "ev_look": 60, "ev_ret": 0.08, "ev_gap": 0.05, "ev_vol": 3.0,
    "hot_dv": 2.0, "hot_min_leg": 5, "hot_base": 60,
    "ma10_look": 30, "ma10_rise": 0.05, "ma10_frac": 0.7,
    "ma20_slope_lag": 5,
    "hi_look": 63, "hi_ago_min": 2, "hi_ago_max": 25,
    "depth_min": 0.03, "depth_max": 0.30, "ext_min": 0.08,
    "dist_lo": -0.03, "dist_hi": 0.03, "touch_days": 3, "touch_tol": 0.015,
    "c20": 0.9, "cleg": 0.7,
}


def norm(sym):
    return sym.replace("/", ".").strip().upper()


# ---------------- metadata (same sources as screener9) ----------------
meta = {}
blob = subprocess.run(["git", "-C", ZREPO, "show", "HEAD:data/v2/tickers.csv"],
                      capture_output=True, text=True).stdout
for row in csv.DictReader(io.StringIO(blob.lstrip("﻿"))):
    s = row["symbol"].strip()
    meta[s] = {
        "name": re.sub(r"\s*\(Name to be changed[^)]*\)", "", row["name"]).split(" Common Stock")[0]
                .split(" Ordinary Shares")[0].strip().rstrip(","),
        "sector": row["sector"].strip() or "—", "industry": row["industry"].strip() or "—",
        "country": row["country"].strip(), "sp500": row["is_sp500"].strip() == "True",
        "mcap": float(row["market_cap"] or 0),
    }
gics = {}
for r in json.load(open(f"{MC}/data/sp500_constituents.json"))["rows"]:
    gics[norm(r["ticker"])] = {"gsec": r["sector"], "gsub": r["sub"]}
exch = {}
for ex in ("NASDAQ", "NYSE", "AMEX"):
    with open(f"{IRA}/symbols/{ex}.csv", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            exch[norm(row["code"])] = ex

# post-close Nasdaq snapshots: official last sale, net change, market cap
SNAP = {}
for dt in SNAP_DATES:
    m = {}
    with open(f"{W_}/snapshots/{dt}.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                last = float(str(r["lastsale"]).strip("$ ").replace(",", ""))
            except ValueError:
                continue
            try:
                chg = float(r["netchange"])
            except ValueError:
                chg = None
            try:
                mc = float(r["marketCap"] or 0)
            except ValueError:
                mc = 0.0
            try:
                vol = float(r["volume"] or 0)
            except ValueError:
                vol = 0.0
            m[r["symbol"].strip()] = {"last": last, "chg": chg, "mcap": mc, "vol": vol, "name": r["name"],
                                      "sector": r["sector"], "industry": r["industry"],
                                      "country": r["country"]}
    SNAP[dt] = m
LATEST_SNAP = SNAP[SNAP_DATES[-1]] if SNAP_DATES else {}

GICS_ZH = {
    "Information Technology": "科技", "Health Care": "醫療保健", "Financials": "金融",
    "Industrials": "工業", "Consumer Discretionary": "非必需消費", "Consumer Staples": "必需消費",
    "Energy": "能源", "Materials": "原材料", "Utilities": "公用事業", "Real Estate": "房地產",
    "Communication Services": "通訊服務",
}
ZH_SECTOR = {
    "Technology": "科技", "Consumer Discretionary": "非必需消費", "Health Care": "醫療保健",
    "Finance": "金融", "Industrials": "工業", "Consumer Staples": "必需消費",
    "Energy": "能源", "Basic Materials": "原材料", "Utilities": "公用事業",
    "Real Estate": "房地產", "Telecommunications": "通訊服務", "Miscellaneous": "其他",
}

_PREF = re.compile(r"\b(Preferred|Preference|Notes?|Debentures?|Subordinated)\b|\d+(\.\d+)?\s?%", re.I)
_FUND = re.compile(r"\b(Fund|ETF|ETN|Closed[- ]End|Municipal|Term Trust|Income Trust|Bond Trust|Royalty Trust|Mineral Trust)\b", re.I)
_TRUSTY = re.compile(r"\bTrust\b|Beneficial Interest", re.I)
_OPERATING_IND = re.compile(r"Bank|Savings|Real Estate|Building|Insurance|REIT|Hotel|Health|Pharma|Retail|Manufactur|Software|Oil|Gas|Electric|Restaurant", re.I)


def is_common_stock(sym, name, industry):
    name = name or ""; industry = industry or ""
    if "^" in sym or industry.startswith("Trusts Except"):
        return False
    if _PREF.search(name) or _FUND.search(name):
        return False
    if _TRUSTY.search(name) and not _OPERATING_IND.search(industry):
        return False
    return True


def info(sym):
    m = meta.get(sym) or meta.get(norm(sym))
    if m:
        return m
    s = LATEST_SNAP.get(sym)
    if s:   # listed since the mirror's metadata was cut
        return {"name": s["name"].split(" Common Stock")[0].split(" Ordinary Shares")[0].strip(),
                "sector": s["sector"] or "—", "industry": s["industry"] or "—",
                "country": s["country"], "sp500": False, "mcap": s["mcap"]}
    return {"name": sym, "sector": "—", "industry": "—", "country": "", "sp500": False, "mcap": 0.0}


# ---------------- bars ----------------
RAW = {}
CLOSE_ONLY = {}
with gzip.open(YAHOO, "rt") as f:
    for r in csv.DictReader(f):
        try:
            o, h, l, c, v = (float(r[k]) for k in ("open", "high", "low", "close", "volume"))
        except (ValueError, TypeError):
            continue
        if not (c > 0 and h > 0 and l > 0) or any(map(math.isnan, (o, h, l, c, v))):
            continue
        RAW.setdefault(r["symbol"], {})[r["date"]] = (o, h, l, c, v)
# ---------------- which session does each snapshot hold? ----------------
# The file name is the date the workflow was asked for, not proof of the data
# inside: the Nasdaq screener API had not rolled over when 2026-09-24.csv
# (still the 09-23 close) and 2026-09-28.csv (still the 09-25 close) were
# fetched at ~21:30 ET. Each snapshot's last sale is matched against Yahoo's
# daily closes; a file that matches another session is relabelled to it (or
# dropped if that session already has a snapshot), one matching none is dropped.
SNAP_AUDIT = {}
_ydays = {}
for sym, m in RAW.items():
    for d, b in m.items():
        _ydays.setdefault(d, {})[sym] = b[3]


def _match(sm, d):
    ys = _ydays.get(d, {})
    k = [abs(sm[x]["last"] / ys[x] - 1) <= 0.005 for x in sm if x in ys and ys[x] > 0]
    return (sum(k) / len(k), len(k)) if len(k) >= 500 else (0.0, len(k))


_fixed = {}
for fname in SNAP_DATES:
    sm = SNAP[fname]
    rate, n = _match(sm, fname)
    if rate >= 0.9:
        _fixed.setdefault(fname, sm); SNAP_AUDIT[fname] = {"holds": fname, "match": rate, "n": n}
        continue
    best = max(((_match(sm, d)[0], d) for d in _ydays if len(_ydays[d]) >= 500), default=(0.0, None))
    if best[0] >= 0.9 and best[1] not in _fixed and best[1] not in SNAP_DATES:
        _fixed[best[1]] = sm
        SNAP_AUDIT[fname] = {"holds": best[1], "match": best[0], "n": n, "own_match": rate, "action": "relabelled"}
    else:
        SNAP_AUDIT[fname] = {"holds": best[1], "match": best[0], "n": n, "own_match": rate, "action": "dropped"}
    print(f"snapshot {fname}: last sale matches Yahoo {fname} for {rate:.1%} only; it holds the "
          f"{best[1]} close ({best[0]:.1%}) -> {SNAP_AUDIT[fname]['action']}")
SNAP = _fixed
SNAP_DATES = sorted(SNAP)
LATEST_SNAP = SNAP[SNAP_DATES[-1]] if SNAP_DATES else {}

# a later, narrower fetch can carry bars the main file lacks (Yahoo drops whole
# days from its daily history and back-fills them later; an intraday roll-up
# stands in for a last session Yahoo has not yet published): take only the gaps
SUPP_ADDED = {}
SUPP_KEYS = set()
VOL_SCALE = {}
for path in [x for x in os.environ.get("SUPP", "").split(",") if x]:
    rows_ = []
    with gzip.open(path, "rt") as f:
        for r in csv.DictReader(f):
            try:
                b = tuple(float(r[k]) for k in ("open", "high", "low", "close", "volume"))
            except (ValueError, TypeError):
                continue
            if not (b[3] > 0 and b[1] > 0 and b[2] > 0) or any(map(math.isnan, b)):
                continue
            rows_.append((r["symbol"], r["date"], b))
    # An hourly roll-up misses the closing auction and other late prints (09-28:
    # its volume was a median 0.79 of the daily bar's on the 1,262 names that had
    # both), so its volume is scaled by that day's measured ratio.
    if "intraday" in os.path.basename(path):
        for d in {x[1] for x in rows_}:
            rs = [RAW[sy][d][4] / b[4] for sy, dd, b in rows_ if dd == d and d in RAW.get(sy, {})
                  and b[4] > 0 and RAW[sy][d][4] > 0]
            if len(rs) >= 200:
                VOL_SCALE[d] = {"ratio": float(np.median(rs)), "n": len(rs)}
    for sym, d, b in rows_:
        m = RAW.setdefault(sym, {})
        if d not in m:
            if d in VOL_SCALE:
                b = b[:4] + (b[4] * VOL_SCALE[d]["ratio"],)
            m[d] = b
            SUPP_ADDED[d] = SUPP_ADDED.get(d, 0) + 1
            SUPP_KEYS.add((sym, d))
if SUPP_ADDED:
    print("supplement filled:", dict(sorted(SUPP_ADDED.items())), "| volume scale:", VOL_SCALE)
# On a day with a (verified) post-close snapshot, a supplement row takes the
# official close and volume from it, its range widened to contain that close.
OFFICIAL = 0
for sym, d in SUPP_KEYS:
    r = SNAP.get(d, {}).get(sym)
    if r:
        o, h, l, c, v = RAW[sym][d]
        c = r["last"]
        RAW[sym][d] = (o, max(h, c), min(l, c), c, r["vol"] or v)
        OFFICIAL += 1
if SUPP_KEYS:
    print(f"supplement rows given a snapshot's official close and volume: {OFFICIAL} of {len(SUPP_KEYS)}")

per_day = {}
for m in RAW.values():
    for dt in m:
        per_day[dt] = per_day.get(dt, 0) + 1
CAL = sorted(per_day)
# the last day counts only once Yahoo has published it for (nearly) everyone:
# on 09-17 and 09-23 the runner saw 32 bars out of 2,758 for hours after the close
LAST = os.environ.get("LAST_DATE")
if not LAST:
    LAST = CAL[-1]
    while per_day[LAST] < 0.9 * per_day[CAL[CAL.index(LAST) - 1]]:
        print(f"{LAST}: only {per_day[LAST]} bars, not yet published — stepping back")
        LAST = CAL[CAL.index(LAST) - 1]
CAL = [d for d in CAL if d <= LAST]
IDX = {d: i for i, d in enumerate(CAL)}
# A hole day: an interior day Yahoo published for under half the symbols it has
# on the days either side (09-22-2026: 270 of ~3,850). A post-close Nasdaq
# snapshot of that day gives the official close and volume; the open, high and
# low are unknown, so the bar is written close-only (o = h = l = c). That can
# only hide a touch of the 20MA on that day, never invent one, and it shrinks
# that day's true range to the close-to-close move.
HOLES = {}
for k in range(1, len(CAL)):
    d = CAL[k]
    # the last day only reaches here when LAST_DATE named it; judge it by the day before
    ref = per_day[CAL[k - 1]] if k == len(CAL) - 1 else min(per_day[CAL[k - 1]], per_day[CAL[k + 1]])
    if per_day[d] < 0.5 * ref:
        HOLES[d] = {"yahoo": per_day[d], "neighbours": ref, "nasdaq_filled": 0, "carried": 0}
for d, h in HOLES.items():
    snap = SNAP.get(d, {})
    for sym, m in RAW.items():
        if d in m or not any(x < d for x in m) or not (d == LAST or any(d < x <= LAST for x in m)):
            continue
        r = snap.get(sym)
        if r:
            m[d] = (r["last"], r["last"], r["last"], r["last"], r.get("vol") or 0.0)
            CLOSE_ONLY.setdefault(sym, []).append(d)
            h["nasdaq_filled"] += 1
        else:
            h["carried"] += 1
    per_day[d] = sum(1 for m in RAW.values() if d in m)
    print(f"hole day {d}: yahoo {h['yahoo']} of ~{h['neighbours']}; close-only bars from the Nasdaq snapshot "
          f"{h['nasdaq_filled']}, still missing {h['carried']}" + ("" if snap else " (NO SNAPSHOT for this day)"))
print(f"yahoo: {len(RAW)} symbols, {len(CAL)} days {CAL[0]}..{LAST}, {per_day[LAST]} bars on the last day")

# Listing age follows the Nasdaq-screener series, as it did for R1-R22. Yahoo
# carries a security across a ticker change, so a de-SPAC listing arrives with
# months of cash-shell trading at the ~$10 trust value (FRNM: 42 sessions as
# Freenome, 185 in Yahoo). The series pickle (gitignored) did not survive the
# container reset of 2026-10-01, so the listing dates come from
# data/nasdaq_listing_dates.json (saved from the R21/R22 audits; only symbols
# listed after the series began on 2025-12-26 are needed), and a shell-history
# heuristic covers anything newer: a Yahoo history whose first 60 sessions sit
# at $9.5-12.5 with >= 85% of days moving under 1% is a SPAC shell, and the
# listing starts after the last such quiet session.
SCAL, SSER = [], {}
if SERIES and os.path.exists(f"{W_}/{SERIES}"):
    ser = pickle.load(open(f"{W_}/{SERIES}", "rb"))
    SCAL, SSER = ser["cal"], ser["series"]
    NQ_START = {sym: SCAL[e[0]] for sym, e in SSER.items()}
else:
    _ld = json.load(open(f"{W_}/nasdaq_listing_dates.json"))
    NQ_START = dict(_ld["dates"])
    SCAL = [_ld["series_first"]]
LATE = {}
SHELL = {}


def shell_end(ds, m):
    """Index of the last session of a leading SPAC-shell run, or -1."""
    if len(ds) < 60:
        return -1
    cl = [m[d][3] for d in ds]
    med = statistics.median(cl[:60])
    quiet = sum(1 for k in range(1, 60) if abs(cl[k] / cl[k - 1] - 1) < 0.01) / 59
    if not (9.5 <= med <= 12.5 and quiet >= 0.85):
        return -1
    end = 59
    while end + 1 < len(cl) and abs(cl[end + 1] / cl[end] - 1) < 0.03 and 9.0 <= cl[end + 1] <= 13.0:
        end += 1
    return end


BARS = {}
gaps = {}
for s, m in RAW.items():
    ds = sorted(d for d in m if d <= LAST)
    if not ds or ds[-1] != LAST:
        continue
    start = NQ_START.get(s)
    if not start:
        k = shell_end(ds, m)
        if k >= 0 and k + 1 < len(ds):
            start = ds[k + 1]
            NQ_START[s] = start
            SHELL[s] = {"shell_until": ds[k], "listed_from": start}
    if start and start > SCAL[0] and ds[0] < start:   # listed after the series began
        LATE[s] = {"yahoo_from": ds[0], "nasdaq_from": start,
                   "yahoo_only_sessions": sum(1 for d in ds if d < start)}
    i0 = IDX[ds[0]]
    missing = [d for d in CAL[i0:] if d not in m]
    if missing:          # a halted day: carry the close, zero volume, and count it
        gaps[s] = len(missing)
    o, h, l, c, v = [], [], [], [], []
    prev = None
    for d in CAL[i0:]:
        if d in m:
            b = m[d]; prev = b[3]
        else:
            b = (prev, prev, prev, prev, 0.0)
        o.append(b[0]); h.append(b[1]); l.append(b[2]); c.append(b[3]); v.append(b[4])
    BARS[s] = tuple(np.array(x, dtype=float) for x in (o, h, l, c, v))


def sma(a, L):
    out = np.full(len(a), np.nan)
    if len(a) >= L:
        cs = np.cumsum(np.insert(a, 0, 0.0))
        out[L - 1:] = (cs[L:] - cs[:-L]) / L
    return out


# ---------------- universe ----------------
counts = {"yahoo_current": len(BARS), "hist": 0, "price": 0, "common": 0, "liq": 0}
ELIG = {}
def listed_sessions(s):
    st = NQ_START.get(s)
    return sum(1 for d in CAL if d >= st) if st else len(BARS[s][3])


for s, (o, h, l, c, v) in BARS.items():
    if len(c) < 90 or listed_sessions(s) < 90: continue
    counts["hist"] += 1
    if c[-1] < 2.0: continue
    counts["price"] += 1
    mi = info(s)
    if not is_common_stock(s, mi["name"], mi["industry"]): continue
    counts["common"] += 1
    if np.median((c * v)[-20:]) < 1_000_000: continue
    counts["liq"] += 1
    ELIG[s] = True
print("universe:", counts, "| Yahoo history older than the Nasdaq listing:", len(LATE), "| shell histories detected:", len(SHELL))

# ---------------- per-stock measurements ----------------
def real_tr_pct(h, l, c, co):
    """True range as a fraction of the previous close, NaN on a close-only
    bar (a hole day filled from the snapshot has no range of its own)."""
    n = len(c)
    out = np.full(n, np.nan)
    for j in range(1, n):
        if j in co:
            continue
        out[j] = max(h[j] - l[j], abs(h[j] - c[j - 1]), abs(l[j] - c[j - 1])) / c[j - 1]
    return out


def nanmean_last(a, k):
    x = a[~np.isnan(a)]
    return float(x[-k:].mean()) if len(x) >= 1 else float("nan")


M = {}
for s in ELIG:
    o, h, l, c, v = BARS[s]
    n = len(c)
    m10, m20, m50 = sma(c, 10), sma(c, 20), sma(c, 50)
    co = {IDX[d] - (len(CAL) - n) for d in CLOSE_ONLY.get(s, []) if d in IDX}
    trp = real_tr_pct(h, l, c, co)
    look = min(P0["hi_look"], n)
    win = c[-look:]
    hi_i = n - look + int(np.flatnonzero(win == win.max())[-1])
    H = float(c[hi_i]); ago = n - 1 - hi_i
    rec = float(c.max())
    # run-up leg into the high: from the lowest close in the 63 sessions before it
    lo_from = max(hi_i - 63, 0)
    lo_i = lo_from + int(np.argmin(c[lo_from:hi_i + 1]))
    leg = H / c[lo_i] - 1
    # event-day candidates: every session in the last ev_look up to the high
    # that has 50 sessions of volume before it
    ev = []
    for j in range(max(hi_i - P0["ev_look"], 50), hi_i + 1):
        base_v = v[j - 50:j].mean()
        if base_v <= 0 or c[j - 1] <= 0:
            continue
        ev.append((j, float(c[j] / c[j - 1] - 1), float(o[j] / c[j - 1] - 1), float(v[j] / base_v)))
    # hot money: mean dollar volume over the leg vs the 60 sessions before it
    leg_s = lo_i if hi_i - lo_i + 1 >= P0["hot_min_leg"] else max(hi_i - P0["hot_min_leg"] + 1, 0)
    dv = c * v
    leg_dv = float(dv[leg_s:hi_i + 1].mean())
    base = dv[max(leg_s - P0["hot_base"], 0):leg_s]
    base_dv = float(base.mean()) if len(base) >= 20 and base.mean() > 0 else None
    dv_ratio = leg_dv / base_dv if base_dv else None
    # the R1-R20 10MA test on every session of the last ma10_look (t0 <= t-1)
    ma10 = []
    for t0 in range(max(n - 1 - P0["ma10_look"], 12), n - 1):
        if math.isnan(m10[t0 - 10]):
            continue
        rise = float(m10[t0] / m10[t0 - 10] - 1)
        three = bool(m10[t0] > m10[t0 - 1] > m10[t0 - 2])
        frac = sum(1 for k in range(t0 - 9, t0 + 1) if m10[k] > m10[k - 1]) / 10
        ma10.append((t0, rise, three, frac))
    # pull-back geometry
    ext_at_high = float(c[hi_i] / m20[hi_i] - 1) if not math.isnan(m20[hi_i]) else -1.0
    touch_j = [j for j in range(n - P0["touch_days"], n) if l[j] <= m20[j] * (1 + P0["touch_tol"])]
    low_gap = float(min(l[j] / m20[j] - 1 for j in range(n - P0["touch_days"], n)))
    day_r = c[1:] / c[:-1] - 1
    pb_days = day_r[hi_i:]
    worst_pb = float(pb_days.min()) if len(pb_days) else 0.0
    big_up = float(day_r[lo_i:hi_i].max()) if hi_i > lo_i else 0.0
    pre = v[max(hi_i - 19, 0):hi_i + 1]
    post = v[hi_i + 1:]
    vol_ratio = float(post.mean() / pre.mean()) if len(post) and pre.mean() > 0 else None
    # volatility now, over the last month, and over the leg
    atr5 = nanmean_last(trp, 5); atr20 = nanmean_last(trp, 20); atr14 = nanmean_last(trp, 14)
    leg_tr = trp[lo_i + 1:hi_i + 1]
    leg_tr = leg_tr[~np.isnan(leg_tr)]
    if len(leg_tr) < 3:
        leg_tr = trp[max(hi_i - 4, 1):hi_i + 1]; leg_tr = leg_tr[~np.isnan(leg_tr)]
    leg_atr = float(leg_tr.mean()) if len(leg_tr) else float("nan")
    rng = h[-1] - l[-1]
    clv = float((c[-1] - l[-1]) / rng) if rng > 0 else 0.5
    M[s] = {
        "n": n, "close": float(c[-1]), "prev": float(c[-2]), "open": float(o[-1]),
        "high": float(h[-1]), "low": float(l[-1]), "vol": float(v[-1]), "vol50": float(v[-50:].mean()),
        "ma10": float(m10[-1]), "ma20": float(m20[-1]), "ma50": float(m50[-1]),
        "ma20_lag": float(m20[-1 - P0["ma20_slope_lag"]]),
        "H": H, "hi_i": hi_i, "hi_date": CAL[len(CAL) - n + hi_i], "ago": ago, "rec": rec,
        "lo_i": lo_i, "leg_from": CAL[len(CAL) - n + lo_i], "leg": float(leg), "leg_days": hi_i - lo_i,
        "ev": ev, "dv_ratio": dv_ratio, "leg_dv": leg_dv, "base_dv": base_dv,
        "ma10": ma10,
        "ext": ext_at_high, "touch_dates": [CAL[len(CAL) - n + j] for j in touch_j], "low_gap": low_gap,
        "worst_pb": worst_pb, "big_up": big_up, "vol_ratio": vol_ratio,
        "atr5": atr5, "atr20": atr20, "atr14": atr14, "leg_atr": leg_atr,
        "c20": atr5 / atr20 if atr20 > 0 else float("nan"),
        "cleg": atr5 / leg_atr if leg_atr > 0 else float("nan"),
        "clv": clv, "range10": float((c[-10:].max() - c[-10:].min()) / c[-1]),
        "dv20": float(np.median(dv[-20:])), "halted_days": gaps.get(s, 0),
        "close_only": [d for d in CLOSE_ONLY.get(s, []) if d in IDX],
    }
    M[s]["ma10_last"] = float(m10[-1])

# breadth over the eligible universe, last six sessions
BREADTH = []
for k in range(len(CAL) - 6, len(CAL)):
    rs = []
    for s in ELIG:
        c = BARS[s][3]; n = len(c); j = k - (len(CAL) - n)
        if j >= 1:
            rs.append(c[j] / c[j - 1] - 1)
    BREADTH.append({"date": CAL[k], "med": float(np.median(rs)), "up": sum(r > 0 for r in rs) / len(rs), "n": len(rs)})
print("breadth:", [(b["date"][5:], round(b["med"] * 100, 2), round(b["up"] * 100, 1)) for b in BREADTH])


def best_event(m, P):
    """The qualifying event day with the largest volume multiple, or None."""
    q = [e for e in m["ev"] if (e[1] >= P["ev_ret"] or e[2] >= P["ev_gap"]) and e[3] >= P["ev_vol"]]
    return max(q, key=lambda e: e[3]) if q else None


def best_ma10(m, P):
    """The qualifying 10MA-uptrend session with the largest rise, or None."""
    q = [x for x in m["ma10"] if x[1] >= P["ma10_rise"] and x[2] and x[3] >= P["ma10_frac"]]
    return max(q, key=lambda x: x[1]) if q else None


def gates(m, P):
    d20 = m["close"] / m["ma20"] - 1
    return {
        "C1a": best_event(m, P) is not None,
        "C1b": m["dv_ratio"] is not None and m["dv_ratio"] >= P["hot_dv"],
        "C2": best_ma10(m, P) is not None,
        "C3": (m["ma20"] > m["ma20_lag"] and P["hi_ago_min"] <= m["ago"] <= P["hi_ago_max"]
               and (1 - P["depth_max"]) * m["H"] <= m["close"] <= (1 - P["depth_min"]) * m["H"]
               and m["ext"] >= P["ext_min"]
               and P["dist_lo"] <= d20 <= P["dist_hi"] and m["low_gap"] <= P["touch_tol"]),
        "C4": (not math.isnan(m["c20"]) and m["c20"] <= P["c20"]
               and not math.isnan(m["cleg"]) and m["cleg"] <= P["cleg"]),
    }


def screen(P):
    return {s for s, m in M.items() if all(gates(m, P).values())}


def lin(x, x0, x1):
    """0 at x0, 1 at x1, clipped (x0 > x1 allowed for a falling scale)."""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return 0.0
    return max(0.0, min(1.0, (x - x0) / (x1 - x0)))


def subscores(m, P):
    e = best_event(m, P); q = best_ma10(m, P)
    dist = m["close"] / m["ma20"] - 1
    return {
        "hot": {"dv": lin(m["dv_ratio"], 2.0, 6.0), "evol": lin(e[3] if e else None, 3.0, 10.0),
                "leg": lin(m["leg"], 0.25, 1.0)},
        "trend": {"rise": lin(q[1] if q else None, 0.05, 0.25), "frac": lin(q[3] if q else None, 0.7, 1.0)},
        "pq": {"vol": lin(m["vol_ratio"], 1.2, 0.6), "near": lin(abs(dist), 0.03, 0.0),
               "slope": lin(m["ma20"] / m["ma20_lag"] - 1, 0.0, 0.03),
               "depth": lin(1 - m["close"] / m["H"], 0.30, 0.15),
               "hold": 0.5 * m["clv"] + 0.5 * (1.0 if m["close"] >= m["ma20"] else 0.0)},
        "vc": {"c20": lin(m["c20"], 0.9, 0.5), "cleg": lin(m["cleg"], 0.7, 0.3)},
    }


def scores(sub):
    hot = 100 * sum(HOT_W[k] * sub["hot"][k] for k in HOT_W)
    trend = 100 * sum(TR_W[k] * sub["trend"][k] for k in TR_W)
    pq = 100 * sum(PQ_W[k] * sub["pq"][k] for k in PQ_W)
    vc = 100 * sum(VC_W[k] * sub["vc"][k] for k in VC_W)
    total = SCORE_W["hot"] * hot + SCORE_W["trend"] * trend + SCORE_W["pq"] * pq + SCORE_W["vc"] * vc
    return {"hot": hot, "trend": trend, "pq": pq, "vc": vc, "score": total}


LIST = screen(P0)
print(f"listed: {len(LIST)}")
GK = ("C1a", "C1b", "C2", "C3", "C4")
fun = {"eligible": len(M)}
alive = set(M)
for k in GK:
    alive = {s for s in alive if gates(M[s], P0)[k]}
    fun[k] = len(alive)
each = {k: sum(1 for s in M if gates(M[s], P0)[k]) for k in GK}
print("funnel:", fun, "| each gate alone:", each)

GZH = {"C1a": "C1a 事件日", "C1b": "C1b 熱錢", "C2": "C2 曾有10MA上升", "C3": "C3 回落20MA", "C4": "C4 波幅減低"}


def why(m, k, P):
    d20 = m["close"] / m["ma20"] - 1
    if k == "C1a":
        top = max(m["ev"], key=lambda e: e[3]) if m["ev"] else None
        return (f"高位前 60 日最大量日只有 {top[3]:.1f}× 50日均量（當日 {top[1]:+.1%}）；要 ≥{P['ev_vol']:.0f}× 兼當日 ≥{P['ev_ret']:+.0%} 或開市跳空 ≥{P['ev_gap']:+.0%}"
                if top else "高位前冇足夠成交歷史")
    if k == "C1b":
        return (f"升浪成交額係之前 60 日嘅 {m['dv_ratio']:.2f}×（要 ≥{P['hot_dv']:.1f}×）" if m["dv_ratio"] else "升浪前成交歷史不足")
    if k == "C2":
        if not m["ma10"]:
            return "10MA 歷史不足"
        b = max(m["ma10"], key=lambda x: x[1])
        return (f"近 30 日 MA10 最大 10 日升幅 {b[1]:+.1%}（{CAL[len(CAL) - m['n'] + b[0]]}；要 ≥{P['ma10_rise']:.0%}），"
                f"嗰時最後三值{'' if b[2] else '唔'}遞升、10 步升 {b[3]:.0%}（要 ≥{P['ma10_frac']:.0%}）")
    if k == "C3":
        parts = []
        if not m["ma20"] > m["ma20_lag"]: parts.append("MA20 唔係向上")
        if not (P["hi_ago_min"] <= m["ago"] <= P["hi_ago_max"]): parts.append(f"高位喺 {m['ago']} 日前")
        dd = m["close"] / m["H"] - 1
        if not ((1 - P["depth_max"]) * m["H"] <= m["close"] <= (1 - P["depth_min"]) * m["H"]): parts.append(f"距高位 {dd:+.1%}")
        if m["ext"] < P["ext_min"]: parts.append(f"高位時只高過 MA20 {m['ext']:.1%}")
        if not (P["dist_lo"] <= d20 <= P["dist_hi"]): parts.append(f"收市距 MA20 {d20:+.1%}")
        if m["low_gap"] > P["touch_tol"]: parts.append(f"近 3 日最低價距 MA20 {m['low_gap']:+.1%}")
        return "；".join(parts) or "—"
    if k == "C4":
        return f"ATR5/ATR20 {m['c20']:.2f}（要 ≤{P['c20']}）；ATR5 係升浪期 ATR 嘅 {m['cleg']:.2f}×（要 ≤{P['cleg']}）"
    return ""


# one-gate near misses
near = []
for s, m in M.items():
    if s in LIST:
        continue
    g = gates(m, P0)
    failed = [k for k, ok in g.items() if not ok]
    if len(failed) == 1:
        k = failed[0]
        near.append({"sym": s, "failed": k, "close": m["close"], "d20": m["close"] / m["ma20"] - 1,
                     "dd": m["close"] / m["H"] - 1, "ago": m["ago"], "low_gap": m["low_gap"], "why": why(m, k, P0),
                     "close_only": m["close_only"]})

# sensitivity: move each threshold one step either way, count churn
SENS = []
for key, alts in (("ev_ret", (0.06, 0.10)), ("ev_vol", (2.0, 4.0)), ("hot_dv", (1.5, 3.0)),
                  ("ma10_rise", (0.03, 0.08)), ("ma10_frac", (0.6, 0.8)), ("ext_min", (0.06, 0.10)),
                  ("depth_max", (0.25, 0.40)), ("dist_lo", (-0.02, -0.05)), ("dist_hi", (0.02, 0.05)),
                  ("touch_tol", (0.0, 0.03)), ("c20", (0.8, 1.0)), ("cleg", (0.6, 0.85)), ("hi_ago_max", (20, 40))):
    for a in alts:
        L2 = screen(dict(P0, **{key: a}))
        SENS.append({"param": key, "base": P0[key], "alt": a, "n": len(L2),
                     "added": sorted(L2 - LIST), "dropped": sorted(LIST - L2)})
# every threshold one step looser / tighter at once: the outer bounds of the list
LOOSE = dict(P0, ev_ret=0.06, ev_vol=2.0, hot_dv=1.5, ma10_rise=0.03, ma10_frac=0.6, ext_min=0.06, depth_max=0.40,
             dist_lo=-0.05, dist_hi=0.05, touch_tol=0.03, c20=1.0, cleg=0.85, hi_ago_max=40)
TIGHT = dict(P0, ev_ret=0.10, ev_vol=4.0, hot_dv=3.0, ma10_rise=0.08, ma10_frac=0.8, ext_min=0.10, depth_max=0.25,
             dist_lo=-0.02, dist_hi=0.02, touch_tol=0.0, c20=0.8, cleg=0.6, hi_ago_max=20)
for nm, P in (("全部放寬一級", LOOSE), ("全部收緊一級", TIGHT)):
    L2 = screen(P)
    SENS.append({"param": nm, "base": "", "alt": "", "n": len(L2), "added": sorted(L2 - LIST), "dropped": sorted(LIST - L2)})

# ---------------- cross-check against the Nasdaq sources ----------------


def xcheck(s):
    """Largest |Yahoo / Nasdaq - 1| over the last 63 sessions the Nasdaq series
    covers, plus the snapshot days (official last sale and last sale - net change)."""
    o, h, l, c, v = BARS[s]
    n = len(c)
    worst, days = 0.0, 0
    e = SSER.get(s)
    if e:
        fi, cs = e[0], e[1]
        for k, d in enumerate(SCAL):
            if d not in IDX or not (fi <= k < fi + len(cs)):
                continue
            j = IDX[d] - (len(CAL) - n)
            if j < n - 63 or j < 0:
                continue
            kk = k - fi
            if kk >= 1 and cs[kk] == cs[kk - 1] and e[2][kk] == e[2][kk - 1]:
                continue
            days += 1
            worst = max(worst, abs(c[j] / cs[k - fi] - 1))
    snaps = {}
    for dt, sm in SNAP.items():
        r = sm.get(s)
        if not r or dt not in IDX:
            continue
        j = IDX[dt] - (len(CAL) - n)
        d_last = c[j] / r["last"] - 1
        snaps[dt] = round(d_last * 100, 3)
        worst = max(worst, abs(d_last)); days += 1
        if r["chg"] is not None and j >= 1:
            prev_off = c[j - 1] / (r["last"] - r["chg"]) - 1
            worst = max(worst, abs(prev_off)); days += 1
    return {"max_abs_pct": round(worst * 100, 3), "points": days, "snap_pct": snaps}


def sector(s):
    mi = info(s); g = gics.get(norm(s), {})
    if mi.get("sp500") and g.get("gsec") in GICS_ZH:
        return g["gsec"], GICS_ZH[g["gsec"]], "GICS"
    return mi["sector"], ZH_SECTOR.get(mi["sector"], mi["sector"]), "Nasdaq"


def mcap(s):
    r = LATEST_SNAP.get(s)
    if r and r["mcap"] > 0:
        return r["mcap"]
    return info(s).get("mcap", 0.0) or 0.0


def cap_bucket(v):
    return "x" if v <= 0 else "a" if v >= 10e9 else "b" if v >= 2e9 else "c"


CAP_ZH = {"a": "大型", "b": "中型", "c": "小型", "x": "未分類"}


def flags(s, m):
    out = []
    if m["worst_pb"] <= -0.08:
        out.append(("gapdown", f"回調唔係有序回落：期內有一日跌 {m['worst_pb']*100:.1f}%"))
    if m["range10"] < 0.03 and m["big_up"] >= 0.15:
        out.append(("pinned", f"疑似釘價：10 日收市區間只有 {m['range10']*100:.1f}%，之前有單日 +{m['big_up']*100:.0f}%"))
    if m["close"] < m["ma20"] and m["vol"] > 1.5 * m["vol50"]:
        out.append(("heavy_break", f"今日放量（{m['vol']/m['vol50']:.1f}× 50日均量）收喺 20MA 下面"))
    if m["halted_days"]:
        out.append(("halted", f"序列有 {m['halted_days']} 日冇成交紀錄"))
    return out


# Tier 2: names that pass only with every threshold one step looser. Each
# carries the gates it fails at the base thresholds, so the reader sees what
# had to give. Their event day / 10MA session are chosen under the looser
# thresholds; their scores use the same formulas.
TIER2 = screen(LOOSE) - LIST


def needs(m):
    g = gates(m, P0)
    return [k for k in GK if not g[k]]


rows = []
for s in sorted(LIST) + sorted(TIER2):
    tier = 1 if s in LIST else 2
    PP = P0 if tier == 1 else LOOSE
    m = M[s]
    sub = subscores(m, PP)
    sc = scores(sub)
    e = best_event(m, PP); q = best_ma10(m, PP)
    sec, sec_zh, src = sector(s)
    mi = info(s); mc = mcap(s)
    o, h, l, c, v = BARS[s]
    n = len(c)
    ev_days = [x for x in m["ev"] if (x[1] >= PP["ev_ret"] or x[2] >= PP["ev_gap"]) and x[3] >= PP["ev_vol"]]
    rows.append({
        "sym": s, "tier": tier, "needs": needs(m) if tier == 2 else [],
        "needs_why": {k: why(m, k, P0) for k in needs(m)} if tier == 2 else {},
        "name": mi["name"], "exch": exch.get(norm(s), "—"),
        "sector": sec, "sector_zh": sec_zh, "sec_src": src, "industry": mi["industry"],
        "country": mi.get("country", ""), "sp500": mi.get("sp500", False),
        "mcap_b": round(mc / 1e9, 3), "cap": cap_bucket(mc),
        **{k: m[k] for k in ("close", "prev", "open", "high", "low", "vol", "vol50", "ma10_last", "ma20", "ma50",
                             "ma20_lag", "H", "hi_date", "ago", "rec", "leg_from", "leg", "leg_days",
                             "dv_ratio", "leg_dv", "base_dv", "ext", "touch_dates", "low_gap", "worst_pb", "big_up",
                             "vol_ratio", "atr5", "atr20", "atr14", "leg_atr", "c20", "cleg", "clv", "range10",
                             "dv20", "halted_days", "close_only")},
        "ev_date": CAL[len(CAL) - n + e[0]], "ev_ret": e[1], "ev_gap": e[2], "ev_vol": e[3], "ev_count": len(ev_days),
        "ev_dates": [CAL[len(CAL) - n + x[0]] for x in ev_days],
        "ma10_date": CAL[len(CAL) - n + q[0]], "ma10_rise": q[1], "ma10_frac": q[3],
        "sub": sub, **sc,
        "flags": flags(s, m), "xchk": xcheck(s),
        "last_intraday": (s, LAST) in SUPP_KEYS,
        "spark": {"dates": CAL[-60:], "close": [round(x, 4) for x in c[-60:]],
                  "ma10": [round(x, 4) for x in sma(c, 10)[-60:]],
                  "ma20": [round(x, 4) for x in sma(c, 20)[-60:]]},
    })
rows.sort(key=lambda r: (r["tier"], -r["score"]))
for i, r in enumerate(rows, 1):
    r["rank"] = i
pages = {}
for b in ("a", "b", "c"):
    pr = [r["sym"] for r in rows if r["cap"] == b]
    pages[b] = pr
    print(f"page {CAP_ZH[b]}: {len(pr)} (tier 1: {sum(1 for r in rows if r['cap'] == b and r['tier'] == 1)})")
print(f"tier 2: {len(TIER2)}")

# every eligible name's gate result, so a later layer can say why a stock is
# not listed without re-running the screen
GATES = {}
for s, m in M.items():
    g = gates(m, P0)
    e = best_event(m, P0)
    GATES[s] = {"fail": [k for k, ok in g.items() if not ok],
                "close": m["close"], "below50": m["close"] < m["ma50"], "h_rec": round(m["H"] / m["rec"], 4),
                "d20": round(m["close"] / m["ma20"] - 1, 4), "dd": round(m["close"] / m["H"] - 1, 4),
                "dv_ratio": None if m["dv_ratio"] is None else round(m["dv_ratio"], 2),
                "c20": None if math.isnan(m["c20"]) else round(m["c20"], 3),
                "cleg": None if math.isnan(m["cleg"]) else round(m["cleg"], 3),
                "ev_vol": None if not e else round(e[3], 2),
                "why": {k: why(m, k, P0) for k in GK if not g[k]}}

# every name that passes the hot-money + event-day test (C1a and C1b), whatever
# its pull-back state: where the hot money is, by sector, right now
HOT = []
for s, m in M.items():
    g = gates(m, P0)
    if not (g["C1a"] and g["C1b"]):
        continue
    e = best_event(m, P0); q = best_ma10(m, P0)
    n = m["n"]
    sec, sec_zh, _src = sector(s)
    mc = mcap(s)
    HOT.append({"sym": s, "name": info(s)["name"], "sector_zh": sec_zh, "industry": info(s)["industry"],
                "cap": cap_bucket(mc), "mcap_b": round(mc / 1e9, 3), "close": m["close"],
                "ev_date": CAL[len(CAL) - n + e[0]], "ev_ret": e[1], "ev_gap": e[2], "ev_vol": e[3],
                "leg_from": m["leg_from"], "leg": m["leg"], "hi_date": m["hi_date"], "ago": m["ago"],
                "dd": m["close"] / m["H"] - 1, "d20": m["close"] / m["ma20"] - 1, "dv_ratio": m["dv_ratio"],
                "ma10_ok": q is not None, "c20": m["c20"], "cleg": m["cleg"], "dv20": m["dv20"],
                "fail": [k for k, ok in g.items() if not ok]})
HOT.sort(key=lambda x: (x["sector_zh"], -x["dv_ratio"]))
SEC_U = {}
for s in M:
    z = sector(s)[1]
    SEC_U[z] = SEC_U.get(z, 0) + 1
print(f"hot-money names (C1a and C1b): {len(HOT)}")

out = {"meta": {"last_date": LAST, "cal_first": CAL[0], "n_days": len(CAL), "yahoo_file": os.path.basename(YAHOO),
                "bars_last_day": per_day[LAST], "universe": counts, "eligible": len(M),
                "funnel": fun, "each_gate": each, "params": P0, "params_loose": LOOSE, "params_tight": TIGHT,
                "n_tier1": len(LIST), "n_tier2": len(TIER2),
                "weights": {"hot": HOT_W, "trend": TR_W, "pq": PQ_W, "vc": VC_W, "score": SCORE_W},
                "snap_dates": SNAP_DATES, "series": SERIES, "holes": HOLES, "supp_added": SUPP_ADDED,
                "supp_official": OFFICIAL, "snap_audit": SNAP_AUDIT, "vol_scale": VOL_SCALE,
                "supp_keys_last": sum(1 for _s, _d in SUPP_KEYS if _d == LAST),
                "close_only_symbols": len(CLOSE_ONLY), "late_nasdaq_start": LATE, "shell_detected": SHELL, "breadth": BREADTH,
                "listing_source": "series" if SSER else "nasdaq_listing_dates.json",
                "cap_counts": {b: sum(1 for s in M if cap_bucket(mcap(s)) == b) for b in ("a", "b", "c", "x")},
                "recent_cut": CAL[-15]},
       "rows": rows, "pages": pages, "near_miss": near, "sensitivity": SENS, "gates": GATES,
       "hot": HOT, "sector_universe": SEC_U}
json.dump(out, open(OUT_JSON if os.path.isabs(OUT_JSON) else f"{W_}/{OUT_JSON}", "w"), ensure_ascii=False)
print("wrote", OUT_JSON, "| rows", len(rows), "| near misses", len(near))

#!/usr/bin/env python3
"""Momentum-pullback screen (R21 onward): high-momentum US stocks that have
pulled back to a rising 20-day moving average.

Replaces the 10MA uptrend / higher-lows screen of R1-R20 (screener9.py). The
universe rules are unchanged; everything after the universe is new.

Price source: Yahoo daily bars (open/high/low/close/volume, split-adjusted,
not dividend-adjusted) fetched on a GitHub Actions runner by
.github/workflows/fetch_yahoo_eod.yml. The touch test needs the day's low, and
the Nasdaq-screener series the earlier revisions used carries closes only.
That series and the post-close Nasdaq snapshots are used here as the check on
Yahoo, not as an input: a listed row whose two sources disagree is flagged.

Universe (same as R1-R20): a bar on the last trading day, >= 90 sessions of
history, close >= $2, operating common stock (ADRs, banks/REITs named "Trust",
BDCs and MLPs stay; funds, preferreds and notes go), 20-day median dollar
volume >= $1M.

Setup — all of these, on the last close t:
  S1 trend      MA20 above its value 5 sessions earlier; MA20 > MA50; MA50 above
                its value 10 sessions earlier; close > MA50.
  S2 high       the highest close of the last 63 sessions was set 2..25 sessions
                ago, and is within 5% of the highest close in the data window
                (from 2025-12-26, about nine months — not a true all-time high).
  S3 depth      close is 3%..30% below that high.
  S4 extended   some close in the last 25 sessions sat >= 8% above that day's
                MA20 (the stock went away from the line before coming back).
  S5 at 20MA    close within -3%..+3% of MA20, and on at least one of the last
                3 sessions the low came within 1.5% of that day's MA20
                (low <= MA20 x 1.015; undercuts count).

Momentum, one page per look-back W in {21, 42, 63, 126} sessions (1/2/3/6
months): the W-session return ranks in the top decile of the whole eligible
universe (percentile >= 90) and is positive. A stock that passes the setup and
is top-decile on at least one look-back is listed; 覆蓋度 = how many.

Scores (0-100):
  動能分數   weighted mean of the four return percentiles (0.2/0.2/0.3/0.3),
             re-weighted over the look-backs a young listing has.
  回調質素   0.25 量縮 + 0.20 貼近20MA + 0.15 20MA斜率 + 0.15 回調深度
             + 0.15 企穩 + 0.10 波幅收窄 (each 0-1, piecewise linear, below).
  綜合分數   0.5 x 動能 + 0.5 x 回調質素            (ranks each page)
  爆發潛力   0.4 x 動能 + 0.4 x 回調質素 + 0.2 x 覆蓋度/4 x 100   (ranks page 1)

Env: WORK_DIR (./data), YAHOO (.csv.gz), SERIES (series pickle for the
cross-check), SNAP_DATES (comma list of post-close snapshot dates in
data/snapshots), OUT_JSON, LAST_DATE (optional; default = last complete day).
"""
import csv, gzip, io, json, math, os, pickle, re, statistics, subprocess, sys

import numpy as np

W_ = os.environ.get("WORK_DIR", "./data")
YAHOO = os.environ["YAHOO"]
SERIES = os.environ.get("SERIES", "series23.pkl")
SNAP_DATES = [x for x in os.environ.get("SNAP_DATES", "").split(",") if x]
OUT_JSON = os.environ.get("OUT_JSON", "screen_mp21.json")
ZREPO = os.environ.get("TICKERS_REPO", "/home/user/zyhe16/top-us-stock-tickers")
MC = os.environ.get("CHRONICLE_REPO", "/home/user/klaywang24/market-chronicle")
IRA = os.environ.get("OPENSTOCK_REPO", "/home/user/irachex/open-stock-data")

LOOKS = (21, 42, 63, 126)
LOOK_LABEL = {21: "1個月", 42: "2個月", 63: "3個月", 126: "6個月"}
MOM_W = {21: 0.2, 42: 0.2, 63: 0.3, 126: 0.3}
PQ_W = {"vol": 0.25, "near": 0.20, "slope": 0.15, "depth": 0.15, "hold": 0.15, "contr": 0.10}

# Every threshold in one place, so the sensitivity pass can move one at a time.
P0 = {
    "ma20_slope_lag": 5, "ma50_slope_lag": 10,
    "hi_look": 63, "hi_ago_min": 2, "hi_ago_max": 25, "near_record": 0.95,
    "depth_min": 0.03, "depth_max": 0.30,
    "ext_look": 25, "ext_min": 0.08,
    "dist_lo": -0.03, "dist_hi": 0.03, "touch_days": 3, "touch_tol": 0.015,
    "decile": 0.90,
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
# a later, narrower fetch can carry bars the main file lacks (Yahoo drops whole
# days from its daily history and back-fills them later): take only the gaps
SUPP_ADDED = {}
for path in [x for x in os.environ.get("SUPP", "").split(",") if x]:
    with gzip.open(path, "rt") as f:
        for r in csv.DictReader(f):
            try:
                b = tuple(float(r[k]) for k in ("open", "high", "low", "close", "volume"))
            except (ValueError, TypeError):
                continue
            if not (b[3] > 0 and b[1] > 0 and b[2] > 0) or any(map(math.isnan, b)):
                continue
            m = RAW.setdefault(r["symbol"], {})
            if r["date"] not in m:
                m[r["date"]] = b
                SUPP_ADDED[r["date"]] = SUPP_ADDED.get(r["date"], 0) + 1
if SUPP_ADDED:
    print("supplement filled:", dict(sorted(SUPP_ADDED.items())))

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

# Listing age follows the Nasdaq-screener series, as it did for R1-R20. Yahoo
# carries a security across a ticker change, so a de-SPAC listing arrives with
# months of cash-shell trading at the ~$10 trust value (FRNM: 42 sessions as
# Freenome, 185 in Yahoo). The same series also starts late for 24 large caps
# whose mirror history broke on 03-18 (ACN, CB, ETN ...), where Yahoo's longer
# history is the right one. So: the 90-session rule counts Nasdaq sessions, a
# return is measured only from a day the ticker was already listed under its
# own symbol, and the moving averages and highs use every Yahoo bar.
ser = pickle.load(open(f"{W_}/{SERIES}", "rb"))
SCAL, SSER = ser["cal"], ser["series"]
NQ_START = {sym: SCAL[e[0]] for sym, e in SSER.items()}
LATE = {}

BARS = {}
gaps = {}
for s, m in RAW.items():
    ds = sorted(d for d in m if d <= LAST)
    if not ds or ds[-1] != LAST:
        continue
    start = NQ_START.get(s)
    if start and ds[0] < start:
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
print("universe:", counts, "| Yahoo history older than the Nasdaq listing:", len(LATE))

# ---------------- per-stock measurements ----------------
M = {}
for s in ELIG:
    o, h, l, c, v = BARS[s]
    n = len(c)
    m20, m50 = sma(c, 20), sma(c, 50)
    prevc = np.concatenate(([c[0]], c[:-1]))
    tr = np.maximum(h - l, np.maximum(abs(h - prevc), abs(l - prevc)))
    atr14 = tr[-14:].mean()
    st = NQ_START.get(s, CAL[0])
    rets = {W: (c[-1] / c[-1 - W] - 1) if n > W and CAL[-1 - W] >= st else None for W in LOOKS}
    look = min(P0["hi_look"], n)
    win = c[-look:]
    hi_rel = int(np.flatnonzero(win == win.max())[-1])
    hi_i = n - look + hi_rel
    H = float(c[hi_i]); ago = n - 1 - hi_i
    rec = float(c.max())
    ext_j = [j for j in range(max(n - P0["ext_look"], 0), n) if not math.isnan(m20[j])]
    ext = max(c[j] / m20[j] - 1 for j in ext_j)
    ext_day = CAL[len(CAL) - n + max(ext_j, key=lambda j: c[j] / m20[j])]
    touch_j = [j for j in range(n - P0["touch_days"], n) if l[j] <= m20[j] * (1 + P0["touch_tol"])]
    low_gap = min(l[j] / m20[j] - 1 for j in range(n - P0["touch_days"], n))
    # run-up leg into the high: from the lowest close in the 63 sessions before it
    lo_from = max(hi_i - 63, 0)
    lo_i = lo_from + int(np.argmin(c[lo_from:hi_i + 1]))
    leg = H / c[lo_i] - 1
    day_r = c[1:] / c[:-1] - 1
    leg_days = day_r[lo_i:hi_i]                                # returns of days lo_i+1..hi_i
    big_up = float(leg_days.max()) if len(leg_days) else 0.0
    pb_days = day_r[hi_i:]                                     # returns of days hi_i+1..t
    worst_pb = float(pb_days.min()) if len(pb_days) else 0.0
    pre = v[max(hi_i - 19, 0):hi_i + 1]
    post = v[hi_i + 1:]
    vol_ratio = (post.mean() / pre.mean()) if len(post) and pre.mean() > 0 else None
    atr5 = tr[-5:].mean(); atr20 = tr[-20:].mean()
    rng = h[-1] - l[-1]
    clv = (c[-1] - l[-1]) / rng if rng > 0 else 0.5
    M[s] = {
        "n": n, "close": float(c[-1]), "prev": float(c[-2]), "open": float(o[-1]),
        "high": float(h[-1]), "low": float(l[-1]), "vol": float(v[-1]),
        "vol50": float(v[-50:].mean()),
        "ma20": float(m20[-1]), "ma50": float(m50[-1]), "ma10": float(sma(c, 10)[-1]),
        "ma20_lag": float(m20[-1 - P0["ma20_slope_lag"]]), "ma50_lag": float(m50[-1 - P0["ma50_slope_lag"]]),
        "rets": rets, "H": H, "hi_date": CAL[len(CAL) - n + hi_i], "ago": ago, "rec": rec,
        "ext": float(ext), "ext_day": ext_day,
        "touch_dates": [CAL[len(CAL) - n + j] for j in touch_j], "low_gap": float(low_gap),
        "leg": float(leg), "leg_from": CAL[len(CAL) - n + lo_i], "big_up": big_up,
        "worst_pb": worst_pb, "vol_ratio": vol_ratio,
        "atr_pct": float(atr14 / c[-1]), "contr": float(atr5 / atr20) if atr20 > 0 else 1.0,
        "clv": float(clv), "range10": float((c[-10:].max() - c[-10:].min()) / c[-1]),
        "dv20": float(np.median((c * v)[-20:])), "halted_days": gaps.get(s, 0),
        "close_only": [d for d in CLOSE_ONLY.get(s, []) if d in IDX],
    }

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

# universe-wide return percentiles per look-back (0 = weakest, 1 = strongest)
PCT, CUT = {}, {}
for W in LOOKS:
    items = sorted(((s, M[s]["rets"][W]) for s in M if M[s]["rets"][W] is not None), key=lambda x: x[1])
    nW = len(items)
    for i, (s, _) in enumerate(items):
        PCT.setdefault(s, {})[W] = i / (nW - 1)
    CUT[W] = {"n": nW, "p50": float(np.percentile([x for _, x in items], 50)),
              "p90": float(np.percentile([x for _, x in items], 90))}
    for s in M:
        PCT.setdefault(s, {})
MKT = {W: CUT[W]["p50"] for W in LOOKS}


def gates(m, P):
    g = {
        "S1": (m["ma20"] > m["ma20_lag"] and m["ma20"] > m["ma50"] and m["ma50"] > m["ma50_lag"]
               and m["close"] > m["ma50"]),
        "S2": (P["hi_ago_min"] <= m["ago"] <= P["hi_ago_max"] and m["H"] >= P["near_record"] * m["rec"]),
        "S3": (1 - P["depth_max"]) * m["H"] <= m["close"] <= (1 - P["depth_min"]) * m["H"],
        "S4": m["ext"] >= P["ext_min"],
        "S5": (P["dist_lo"] <= m["close"] / m["ma20"] - 1 <= P["dist_hi"]
               and m["low_gap"] <= P["touch_tol"]),
    }
    return g


def mom_hits(s, P):
    return [W for W in LOOKS if W in PCT[s] and PCT[s][W] >= P["decile"] and M[s]["rets"][W] > 0]


def screen(P):
    out = {}
    for s, m in M.items():
        if all(gates(m, P).values()):
            hw = mom_hits(s, P)
            if hw:
                out[s] = hw
    return out


def lin(x, x0, x1):
    """0 at x0, 1 at x1, clipped (x0 > x1 allowed for a falling scale)."""
    if x is None:
        return 0.0
    t = (x - x0) / (x1 - x0)
    return max(0.0, min(1.0, t))


def subscores(m):
    dist = m["close"] / m["ma20"] - 1
    depth = 1 - m["close"] / m["H"]
    slope = m["ma20"] / m["ma20_lag"] - 1
    return {
        "vol": lin(m["vol_ratio"], 1.2, 0.6),        # pull-back volume vs the 20 days into the high
        "near": lin(abs(dist), 0.03, 0.0),          # |close / MA20 - 1|
        "slope": lin(slope, 0.0, 0.03),             # MA20 vs 5 sessions earlier
        "depth": lin(depth, 0.30, 0.15),            # <= 15% full marks, 30% none
        "hold": 0.5 * m["clv"] + 0.5 * (1.0 if m["close"] >= m["ma20"] else 0.0),
        "contr": lin(m["contr"], 1.3, 0.7),         # ATR5 / ATR20
    }


def mom_score(s):
    ws = {W: MOM_W[W] for W in LOOKS if W in PCT[s]}
    tot = sum(ws.values())
    return 100 * sum(PCT[s][W] * w for W, w in ws.items()) / tot


LIST = screen(P0)
print(f"listed: {len(LIST)}")

# funnel, gate by gate (setup first, then momentum)
fun = {"eligible": len(M)}
alive = set(M)
for k in ("S1", "S2", "S3", "S4", "S5"):
    alive = {s for s in alive if gates(M[s], P0)[k]}
    fun[k] = len(alive)
fun["setup"] = len(alive)
fun["momentum"] = len(LIST)
fun_mom_only = sum(1 for s in M if mom_hits(s, P0))
print("funnel:", fun, "| top-decile on any look-back (no setup):", fun_mom_only)

# one-gate near misses among momentum names — what the thresholds are cutting
near = []
for s, m in M.items():
    if s in LIST or not mom_hits(s, P0):
        continue
    g = gates(m, P0)
    failed = [k for k, ok in g.items() if not ok]
    if len(failed) == 1:
        k = failed[0]
        d20 = m["close"] / m["ma20"] - 1
        dd = m["close"] / m["H"] - 1
        if k == "S1":
            why = (f"MA20 {'↑' if m['ma20'] > m['ma20_lag'] else '↓'}（vs 5日前）；MA20 {'>' if m['ma20'] > m['ma50'] else '≤'} MA50；"
                   f"MA50 {'↑' if m['ma50'] > m['ma50_lag'] else '↓'}（vs 10日前）；收市 {'>' if m['close'] > m['ma50'] else '≤'} MA50")
        elif k == "S2":
            why = (f"高位喺 {m['ago']} 個交易日前（要 {P0['hi_ago_min']}–{P0['hi_ago_max']}）；"
                   f"高位係紀錄高嘅 {m['H'] / m['rec']:.0%}（要 ≥{P0['near_record']:.0%}）")
        elif k == "S3":
            why = f"距高位 {dd:+.1%}（要 −{P0['depth_min']:.0%} 至 −{P0['depth_max']:.0%}）"
        elif k == "S4":
            why = f"25 日內最多只係高過 MA20 {m['ext']:.1%}（要 ≥{P0['ext_min']:.0%}）"
        else:
            dist_ok = P0["dist_lo"] <= d20 <= P0["dist_hi"]
            why = (f"收市距 MA20 {d20:+.1%}（要 {P0['dist_lo']:+.0%} 至 {P0['dist_hi']:+.0%}）"
                   + ("" if dist_ok else "；") +
                   f"{'；' if dist_ok else ''}近 3 日最低價最近去到 MA20 {m['low_gap']:+.1%}（要 ≤+{P0['touch_tol']:.1%}）")
        near.append({"sym": s, "failed": k, "hits": len(mom_hits(s, P0)), "close": m["close"], "d20": d20,
                     "dd": dd, "ago": m["ago"], "low_gap": m["low_gap"], "why": why,
                     "touch_only": k == "S5" and P0["dist_lo"] <= d20 <= P0["dist_hi"],
                     "close_only": [d for d in CLOSE_ONLY.get(s, []) if d in IDX]})

# sensitivity: move each threshold one step either way, count churn
SENS = []
for key, alts in (("touch_tol", (0.0, 0.03)), ("dist_hi", (0.02, 0.05)), ("dist_lo", (-0.02, -0.05)),
                  ("ext_min", (0.06, 0.10)), ("depth_min", (0.02, 0.05)), ("depth_max", (0.25, 0.35)),
                  ("hi_ago_max", (20, 30)), ("near_record", (0.90, 0.98)), ("decile", (0.85, 0.95))):
    for a in alts:
        P = dict(P0, **{key: a})
        L2 = screen(P)
        SENS.append({"param": key, "base": P0[key], "alt": a, "n": len(L2),
                     "added": sorted(set(L2) - set(LIST)), "dropped": sorted(set(LIST) - set(L2))})

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
            # the mirror's copied days (close and volume carried from the day
            # before) were back-filled only for the names Yahoo covered then
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


def flags(s, m):
    out = []
    if m["big_up"] >= 0.15 and math.log1p(m["big_up"]) >= 0.5 * math.log1p(max(m["leg"], 1e-9)):
        out.append(("spike", f"升幅過半來自單日：{m['leg_from']} 起計升 {m['leg']*100:.0f}%，"
                             f"最大單日 +{m['big_up']*100:.1f}%"))
    if m["worst_pb"] <= -0.08:
        out.append(("gapdown", f"回調唔係有序回落：期內有一日跌 {m['worst_pb']*100:.1f}%"))
    if m["range10"] < 0.03 and m["big_up"] >= 0.15:
        out.append(("pinned", f"疑似釘價：10 日收市區間只有 {m['range10']*100:.1f}%，之前有單日 +{m['big_up']*100:.0f}%"))
    if m["close"] < m["ma20"] and m["vol"] > 1.5 * m["vol50"]:
        out.append(("heavy_break", f"今日放量（{m['vol']/m['vol50']:.1f}× 50日均量）收喺 20MA 下面"))
    if m["halted_days"]:
        out.append(("halted", f"序列有 {m['halted_days']} 日冇成交紀錄"))
    return out


rows = []
for s, hw in LIST.items():
    m = M[s]
    sub = subscores(m)
    ms = mom_score(s)
    pq = 100 * sum(PQ_W[k] * sub[k] for k in PQ_W)
    combo = 0.5 * ms + 0.5 * pq
    score = 0.4 * ms + 0.4 * pq + 0.2 * (len(hw) / 4 * 100)
    sec, sec_zh, src = sector(s)
    mi = info(s)
    mc = mcap(s)
    o, h, l, c, v = BARS[s]
    rows.append({
        "sym": s, "name": mi["name"], "exch": exch.get(norm(s), "—"),
        "sector": sec, "sector_zh": sec_zh, "sec_src": src, "industry": mi["industry"],
        "country": mi.get("country", ""), "sp500": mi.get("sp500", False),
        "mcap_b": round(mc / 1e9, 3), "cap": cap_bucket(mc),
        **{k: m[k] for k in ("close", "prev", "open", "high", "low", "vol", "vol50", "ma10", "ma20", "ma50",
                             "ma20_lag", "ma50_lag", "H", "hi_date", "ago", "rec", "ext", "ext_day",
                             "touch_dates", "low_gap", "leg", "leg_from", "big_up", "worst_pb",
                             "vol_ratio", "atr_pct", "contr", "clv", "range10", "dv20", "halted_days", "close_only")},
        "rets": {str(W): m["rets"][W] for W in LOOKS},
        "pct": {str(W): PCT[s].get(W) for W in LOOKS},
        "hits_w": hw, "hits": len(hw),
        "sub": sub, "mom": ms, "pq": pq, "combo": combo, "score": score,
        "flags": flags(s, m), "xchk": xcheck(s),
        "spark": {"dates": CAL[-60:], "close": [round(x, 4) for x in c[-60:]],
                  "ma20": [round(x, 4) for x in sma(c, 20)[-60:]]},
    })
rows.sort(key=lambda r: -r["score"])
for i, r in enumerate(rows, 1):
    r["rank"] = i
pages = {}
for W in LOOKS:
    pr = sorted((r for r in rows if W in r["hits_w"]), key=lambda r: -r["combo"])
    pages[str(W)] = [r["sym"] for r in pr]
    print(f"page {LOOK_LABEL[W]}: {len(pr)}")

# every eligible name's setup result, so a later layer can say why a stock is
# not listed without re-running the screen
GATES = {}
for s, m in M.items():
    g = gates(m, P0)
    GATES[s] = {"fail": [k for k, ok in g.items() if not ok], "hits": len(mom_hits(s, P0)),
                "d20": round(m["close"] / m["ma20"] - 1, 4), "dd": round(m["close"] / m["H"] - 1, 4),
                "ret63": None if m["rets"][63] is None else round(m["rets"][63], 4)}

out = {"meta": {"last_date": LAST, "cal_first": CAL[0], "n_days": len(CAL), "yahoo_file": os.path.basename(YAHOO),
                "bars_last_day": per_day[LAST], "universe": counts, "eligible": len(M),
                "funnel": fun, "momentum_any": fun_mom_only, "cutoffs": {str(W): CUT[W] for W in LOOKS},
                "params": P0, "mom_w": {str(k): v for k, v in MOM_W.items()}, "pq_w": PQ_W,
                "snap_dates": SNAP_DATES, "series": SERIES, "holes": HOLES, "supp_added": SUPP_ADDED,
                "close_only_symbols": len(CLOSE_ONLY), "late_nasdaq_start": LATE, "breadth": BREADTH},
       "rows": rows, "pages": pages, "near_miss": near, "sensitivity": SENS, "gates": GATES}
json.dump(out, open(OUT_JSON if os.path.isabs(OUT_JSON) else f"{W_}/{OUT_JSON}", "w"), ensure_ascii=False)
print("wrote", OUT_JSON, "| rows", len(rows), "| near misses", len(near))

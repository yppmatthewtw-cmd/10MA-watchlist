#!/usr/bin/env python3
"""10MA R8 screener: R5/R6 rules with four data-defect fixes from the critical
review of R7 (none of them changes the user's stated rules):

1. Copied days do not make bottoms. The mirror had no snapshot on four days
   (2026-03-18, 08-11, 08-12, 08-26) and every ticker's close AND volume was
   forward-filled, so a "bottom" could land on a price that never traded.
   Bottom detection now runs on the real-close subsequence (a bottom cannot be
   dated on a copied day and its ±3-day comparators are real closes); the 45 /
   25-day windows and 守底 stay in trading days, because the market was open on
   those days — only the observation is missing. The copied days are detected
   from the data (>98% of tickers unchanged in close AND volume), not hard-coded.
2. Partial-volume days do not feed the volume metrics. 2026-02-25 and 08-27
   were snapped minutes after the close (universe-median volume 55-61% of
   normal); together with the copied days they are skipped in 量比 and in the
   VCP volume ratio.
3. Universe = common stock. Closed-end funds, royalty/mineral trusts,
   preferreds, depositary shares and notes cannot break out and were reaching
   the small-cap pages; they are excluded up front (REITs and BDC/MLP operating
   businesses stay).
4. S&P 500 rows carry their GICS sector as the displayed sector (Nasdaq's
   taxonomy put TMO/A in 工業 and ACN in 非必需消費); other rows keep Nasdaq's.

R6 description follows unchanged:

Reads data/series3.pkl (history rebuilt from the GitHub mirror plus the day
appended by scripts/extend_series.py) and prefers the fresh market caps in
data/mcap_latest.json for bucketing, falling back to the mirror metadata.

R5 description follows unchanged:

the R1/R2 10MA pipeline with each timeframe split into
three market-cap sub-pages — a = 大型 (>= $10B), b = 中型 ($2-10B),
c = 小型 (< $2B) — each taking its own top 50.

PAGE 2a/b/c use the 5-day MA over a 5-trading-day window; PAGES 3/4/5 (a/b/c)
use the 10-day MA over 10 / 21 / 42-trading-day windows. Bottoms, higher-lows,
VCP and the 7 certainty metrics are unchanged. Tickers whose market cap is
absent from the source metadata (mostly closed-end funds) cannot be bucketed;
they are counted and reported rather than dropped silently.

確定性 (certainty, 0-100) components and weights:
  s_break 25%  breakout of the intermediate high between the last two bottoms
               (1.0 if the post-bottom high exceeds it; otherwise 0.6 x progress)
  s_retr  10%  current recovery of the decline leg into the last bottom, capped at 100%
  s_time  15%  trading days the last bottom has held, full marks at 15 obs;
               x0.25 if any later close undercut the bottom
  s_dv    15%  down-day volume / up-day volume over the last 15 obs (percentile, lower better)
  s_contr 10%  depth of last decline leg / depth of first leg in the 45-obs window
               (percentile, lower better)
  s_rs    10%  21-obs return minus the eligible-universe median (percentile)
  s_ma    15%  0.4 x (close > MA20) + 0.3 x (MA20 > MA50) + 0.3 x (MA50 rising over 10 obs)

Each of the 12 sub-pages ranks by 綜合 = 0.5 x VCP + 0.5 x 確定性 (top 50 by
unrounded value) within its own cap bucket.
Page 1 = union of the 12 lists, ranked by
爆發潛力 = 0.4 x VCP + 0.4 x 確定性 + 0.2 x (qualifying frames / 4 x 100).
"""
import csv, io, json, math, os, pickle, re, statistics, subprocess

SCRATCH = os.environ.get("WORK_DIR", "./data")
ZREPO = os.environ.get("TICKERS_REPO", "/home/user/zyhe16/top-us-stock-tickers")
MC = os.environ.get("CHRONICLE_REPO", "/home/user/klaywang24/market-chronicle")
IRA = os.environ.get("OPENSTOCK_REPO", "/home/user/irachex/open-stock-data")

d = pickle.load(open(f"{SCRATCH}/{os.environ.get('SERIES', 'series3.pkl')}", "rb"))
CAL, SER = d["cal"], d["series"]
LAST_DATE = CAL[-1]

def norm(sym):
    return sym.replace("/", ".").strip().upper()

meta = {}
blob = subprocess.run(["git", "-C", ZREPO, "show", "HEAD:data/v2/tickers.csv"],
                      capture_output=True, text=True).stdout
for row in csv.DictReader(io.StringIO(blob.lstrip("﻿"))):
    s = row["symbol"].strip()
    meta[s] = {
        "name": re.sub(r"\s*\(Name to be changed[^)]*\)", "", row["name"]).split(" Common Stock")[0].split(" Ordinary Shares")[0].strip().rstrip(","),
        "sector": row["sector"].strip() or "—",
        "industry": row["industry"].strip() or "—",
        "country": row["country"].strip(),
        "sp500": row["is_sp500"].strip() == "True",
        "mcap": float(row["market_cap"] or 0),
    }

gics = {}
mcj = json.load(open(f"{MC}/data/sp500_constituents.json"))
for r in mcj["rows"]:
    gics[norm(r["ticker"])] = {"gsec": r["sector"], "gsub": r["sub"]}

exch = {}
for ex in ("NASDAQ", "NYSE", "AMEX"):
    with open(f"{IRA}/symbols/{ex}.csv", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            exch[norm(row["code"])] = ex

GICS_ZH = {
    "Information Technology": "科技", "Health Care": "醫療保健", "Financials": "金融",
    "Industrials": "工業", "Consumer Discretionary": "非必需消費", "Consumer Staples": "必需消費",
    "Energy": "能源", "Materials": "原材料", "Utilities": "公用事業", "Real Estate": "房地產",
    "Communication Services": "通訊服務",
}

import re as _re
# Preferreds, notes and rate-bearing instruments carry a coupon or the word in
# their name; funds carry Fund/Closed-End/Municipal; "Trust" and "Beneficial
# Interest" name both closed-end funds and operating REITs/banks, so those are
# only excluded when the industry is not an operating one. ADRs are common stock.
_PREF = _re.compile(r"\b(Preferred|Preference|Notes?|Debentures?|Subordinated)\b|\d+(\.\d+)?\s?%", _re.I)
_FUND = _re.compile(r"\b(Fund|ETF|ETN|Closed[- ]End|Municipal|Term Trust|Income Trust|Bond Trust|Royalty Trust|Mineral Trust)\b", _re.I)
_TRUSTY = _re.compile(r"\bTrust\b|Beneficial Interest", _re.I)
_OPERATING_IND = _re.compile(r"Bank|Savings|Real Estate|Building|Insurance|REIT|Hotel|Health|Pharma|Retail|Manufactur|Software|Oil|Gas|Electric|Restaurant", _re.I)

def is_common_stock(sym, name, industry):
    """Operating common stock (ADRs included): drop funds, closed-end trusts,
    royalty trusts, preferreds and notes. Banks, REITs and insurers named
    "Trust" stay; BDCs (ARCC, MAIN) and MLP units (CQP, EPD) stay."""
    name = name or ""; industry = industry or ""
    if "^" in sym:
        return False
    if industry.startswith("Trusts Except"):
        return False
    if _PREF.search(name) or _FUND.search(name):
        return False
    if _TRUSTY.search(name) and not _OPERATING_IND.search(industry):
        return False
    return True

# Days the mirror could not observe: detected, not assumed. A copied day has
# close AND volume unchanged for >98% of tickers; a partial-volume day has a
# universe-median volume below 70% of its own trailing 20-day median.
_N = len(CAL)
_cur = [s for s, (fi, cs, vs, ff) in SER.items() if fi + len(cs) == _N]
SYN_DAYS, PARTIAL_VOL_DAYS = set(), set()
for _k in range(1, _N):
    _same = _tot = 0; _ratios = []
    for _s in _cur:
        _fi, _cs, _vs, _ff = SER[_s]; _j = _k - _fi
        if _j >= 1:
            _tot += 1
            if _cs[_j] == _cs[_j - 1] and _vs[_j] == _vs[_j - 1]: _same += 1
        if _j >= 21 and _vs[_j] > 0:
            _m = statistics.median(_vs[_j - 20:_j])
            if _m > 0: _ratios.append(_vs[_j] / _m)
    if _tot and _same / _tot > 0.98: SYN_DAYS.add(_k)
    if _ratios and statistics.median(_ratios) < 0.7: PARTIAL_VOL_DAYS.add(_k)
BAD_VOL_DAYS = SYN_DAYS | PARTIAL_VOL_DAYS
print("copied days:", [CAL[k] for k in sorted(SYN_DAYS)],
      "| partial-volume days:", [CAL[k] for k in sorted(PARTIAL_VOL_DAYS)])

ZH_SECTOR = {
    "Technology": "科技", "Consumer Discretionary": "非必需消費", "Health Care": "醫療保健",
    "Finance": "金融", "Industrials": "工業", "Consumer Staples": "必需消費",
    "Energy": "能源", "Real Estate": "房地產", "Utilities": "公用事業",
    "Basic Materials": "原材料", "Telecommunications": "電訊", "Miscellaneous": "其他", "—": "—",
}

def sma_series(cs, L):
    # summed per window with fsum rather than carried as a running total: the
    # running total drifts by an ULP or two, which is enough to make a flat MA
    # compare as rising and let a stock through the "MA rose each of the last
    # 3 days" rule it does not meet
    out = [None] * len(cs)
    for i in range(L - 1, len(cs)):
        out[i] = math.fsum(cs[i - L + 1:i + 1]) / L
    return out

def find_bottoms(cs, real=None):
    """Bottoms on the real-day subsequence; indices are mapped back to `cs`.

    `real` is the list of indices in cs that are genuine closes. With it, the
    ±3-day window and the i-3 / i+3 comparators step over copied days instead
    of treating a copied price as a traded one."""
    if real is None:
        real = list(range(len(cs)))
    sub = [cs[j] for j in real]
    n = len(sub); raw = []
    for i in range(3, n - 3):
        w = sub[i - 3:i + 4]
        if sub[i] == min(w) and sub[i - 3] > sub[i] and sub[i + 3] > sub[i]:
            raw.append((real[i], sub[i]))
    dedup = []
    for i, c in raw:
        if dedup and i - dedup[-1][0] <= 3:
            if c < dedup[-1][1]: dedup[-1] = (i, c)
        else:
            dedup.append((i, c))
    return dedup

def higher_lows(bots, n, look=45, recent=25):
    # windows are trading days (the market was open on the copied days; only
    # the snapshot is missing), so they stay in full calendar index
    inw = [(i, c) for i, c in bots if i >= n - look]
    if len(inw) < 2: return None
    for a, b in zip(inw, inw[1:]):
        if b[1] <= a[1]: return None
    if inw[-1][0] < n - recent: return None
    return inw

def ma_uptrend(ma, W):
    n = len(ma)
    if n < W + 1 or ma[-1] is None or ma[-1 - W] is None: return None
    if not ma[-1] > ma[-1 - W]: return None
    if not (ma[-1] > ma[-2] > ma[-3]): return None
    diffs = [1 if ma[-k] > ma[-k - 1] else 0 for k in range(1, W + 1)]
    if sum(diffs) / W < 0.70: return None
    return (ma[-1] / ma[-1 - W] - 1) * 100

# ---------------- eligibility + VCP raw components (identical to R2) ----------------
PAGES = {2: (5, 5, "1星期"), 3: (10, 10, "2星期"), 4: (10, 21, "1個月"), 5: (10, 42, "2個月")}
elig = {}
stats_counts = {"total": len(SER), "current": 0, "hist": 0, "price": 0, "liq": 0}
for sym, (fi, cs, vs, ff) in SER.items():
    if fi + len(cs) != len(CAL):
        continue
    stats_counts["current"] += 1
    if len(cs) < 90: continue
    stats_counts["hist"] += 1
    if cs[-1] < 2.0: continue
    stats_counts["price"] += 1
    _m = meta.get(sym) or meta.get(norm(sym)) or {}
    if not is_common_stock(sym, _m.get("name", sym), _m.get("industry", "")):
        stats_counts["not_common"] = stats_counts.get("not_common", 0) + 1
        continue
    dv = [c * v for c, v in zip(cs[-20:], vs[-20:])]
    if statistics.median(dv) < 1_000_000: continue
    stats_counts["liq"] += 1

    rets = [cs[i] / cs[i - 1] - 1 for i in range(1, len(cs))]
    s_rec = statistics.pstdev(rets[-10:])
    s_pri = statistics.pstdev(rets[-40:-10])
    if s_pri <= 1e-9: continue  # degenerate flat series; never fires on current data
    cr = s_rec / s_pri
    t10 = (max(cs[-10:]) - min(cs[-10:])) / cs[-1]
    # volume windows skip copied / partial-volume days (mean of the real ones)
    _good = [j for j in range(len(cs)) if (fi + j) not in BAD_VOL_DAYS]
    _rec = [vs[j] for j in _good if j >= len(cs) - 10]
    _pri = [vs[j] for j in _good if len(cs) - 40 <= j < len(cs) - 10]
    v_rec = sum(_rec) / len(_rec) if _rec else 0.0
    v_pri = sum(_pri) / len(_pri) if _pri else 0.0
    vr = v_rec / v_pri if v_pri > 0 else 1.0
    blocks = [cs[-45:-30], cs[-30:-15], cs[-15:]]
    rng = [(max(b) - min(b)) / (sum(b) / len(b)) for b in blocks]
    pc = rng[2] / rng[0] if rng[0] > 1e-9 else 1.0
    elig[sym] = {"cr": cr, "t10": t10, "vr": vr, "pc": pc}

def pct_ranks(vals):
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    r = [0.0] * len(vals)
    for rank, i in enumerate(order):
        r[i] = rank / (len(vals) - 1) if len(vals) > 1 else 0.5
    return r

syms = list(elig)
for comp in ("cr", "t10", "vr", "pc"):
    pr = pct_ranks([elig[s][comp] for s in syms])
    for s, p in zip(syms, pr): elig[s]["pr_" + comp] = p
for s in syms:
    e = elig[s]
    e["vcp_raw"] = 100 * (0.35 * (1 - e["pr_cr"]) + 0.25 * (1 - e["pr_t10"])
                          + 0.20 * (1 - e["pr_vr"]) + 0.20 * (1 - e["pr_pc"]))
    e["vcp"] = round(e["vcp_raw"], 1)

# ---------------- universe-wide certainty inputs ----------------
mkt_rets = {}
for s in syms:
    cs = SER[s][1]
    mkt_rets[s] = cs[-1] / cs[-22] - 1
mkt_med = statistics.median(mkt_rets.values())

univ = {}
for s in syms:
    fi, cs, vs, ff = SER[s]
    # down-day vs up-day volume over last 15 obs
    dn, up = [], []
    for i in range(len(cs) - 15, len(cs)):
        if (fi + i) in BAD_VOL_DAYS: continue      # no real volume that day
        if cs[i] > cs[i - 1]: up.append(vs[i])
        elif cs[i] < cs[i - 1]: dn.append(vs[i])
    dv_ratio = (sum(dn) / len(dn)) / (sum(up) / len(up)) if dn and up and sum(up) > 0 else 1.0
    # MA structure
    ma20 = sma_series(cs, 20); ma50 = sma_series(cs, 50)
    f_c20 = cs[-1] > ma20[-1]
    f_2050 = ma20[-1] > ma50[-1] if ma50[-1] else False
    f_50up = (ma50[-1] > ma50[-11]) if (ma50[-1] and ma50[-11]) else False
    s_ma = 0.4 * f_c20 + 0.3 * f_2050 + 0.3 * f_50up
    univ[s] = {"rs21": mkt_rets[s] - mkt_med, "dv_ratio": dv_ratio,
               "s_ma": s_ma, "ma_flags": [bool(f_c20), bool(f_2050), bool(f_50up)]}

pr_rs = pct_ranks([univ[s]["rs21"] for s in syms])
pr_dv = pct_ranks([univ[s]["dv_ratio"] for s in syms])
for s, a, b in zip(syms, pr_rs, pr_dv):
    univ[s]["s_rs"] = a          # higher RS -> higher percentile -> better
    univ[s]["s_dv"] = 1 - b      # lower down/up volume ratio -> better

# ---------------- structure metrics for tickers with a higher-lows sequence ----------------
struct = {}
contr_vals = {}
for s in syms:
    fi, cs, vs, ff = SER[s]
    n = len(cs)
    real = [j for j in range(n) if (fi + j) not in SYN_DAYS]
    bots = find_bottoms(cs, real)
    hl = higher_lows(bots, n)
    if hl is None: continue
    bP, pP = hl[-2]
    bL, pL = hl[-1]
    H_mid = max(cs[bP:bL])                      # intermediate high between last two bottoms
    post_high = max(cs[bL + 1:])                # bottoms exist only at i <= n-4
    C = cs[-1]
    broke = post_high > H_mid
    progress = (C - pL) / (H_mid - pL) if H_mid > pL else 1.0
    s_break = 1.0 if broke else 0.6 * max(0.0, min(1.0, progress))
    retrace = progress
    s_retr = max(0.0, min(1.0, retrace))
    d_held = (n - 1) - bL                          # trading days since the bottom
    undercut = min(cs[bL + 1:]) < pL * 0.999
    s_time = min(1.0, d_held / 15) * (0.25 if undercut else 1.0)
    # depth contraction across the window's legs: first leg's high = 10 obs before first bottom
    depths = []
    prev_i = None
    for k, (bi, bp) in enumerate(hl):
        if k == 0:
            hi = max(cs[max(0, bi - 10):bi]) if bi > 0 else bp
        else:
            hi = max(cs[prev_i:bi])
        if hi > bp:
            depths.append((hi - bp) / hi)
        prev_i = bi
    contr = depths[-1] / depths[0] if len(depths) >= 2 and depths[0] > 1e-4 else 1.0
    contr_vals[s] = contr
    struct[s] = {"bP": bP, "pP": pP, "bL": bL, "pL": pL, "H_mid": H_mid,
                 "post_high": post_high, "broke": broke, "retrace": retrace,
                 "d_held": d_held, "undercut": undercut, "contr": contr,
                 "s_break": s_break, "s_retr": s_retr, "s_time": s_time,
                 "hl": hl, "bots": bots}

c_syms = list(contr_vals)
pr_contr = pct_ranks([contr_vals[s] for s in c_syms])
for s, p in zip(c_syms, pr_contr):
    struct[s]["s_contr"] = 1 - p                # lower contraction ratio -> better

for s in struct:
    st = struct[s]; u = univ[s]
    cert_raw = 100 * (0.25 * st["s_break"] + 0.10 * st["s_retr"] + 0.15 * st["s_time"]
                      + 0.15 * u["s_dv"] + 0.10 * st["s_contr"]
                      + 0.10 * u["s_rs"] + 0.15 * u["s_ma"])
    st["cert_raw"] = cert_raw
    st["cert"] = round(cert_raw, 1)
    st["combo_raw"] = 0.5 * elig[s]["vcp_raw"] + 0.5 * cert_raw
    st["combo"] = round(st["combo_raw"], 1)

# ---------------- per-page qualification (identical rules to R2) ----------------
qual = {p: {} for p in PAGES}
for s in struct:
    fi, cs, vs, ff = SER[s]
    ma5 = sma_series(cs, 5); ma10 = sma_series(cs, 10)
    for p, (L, W, _) in PAGES.items():
        ma = ma5 if L == 5 else ma10
        slope = ma_uptrend(ma, W)
        if slope is None: continue
        qual[p][s] = {"slope": slope, "ma": ma[-1], "L": L, "W": W}

hits = {s: sum(1 for p in PAGES if s in qual[p]) for s in struct}

# ---------------- market-cap buckets (R5) ----------------
# 大型 >= $10B · 中型 $2-10B · 小型 < $2B; source metadata lacks a market cap for
# ~6% of the eligible universe (mostly closed-end funds) -> bucket "x", excluded
# from the three cap sub-pages and reported in the counts instead.
CAP_CUTS = (10e9, 2e9)
CAP_LABEL = {"a": "大型", "b": "中型", "c": "小型", "x": "未分類"}

MCAP_LATEST = {}
_mc_path = f"{SCRATCH}/mcap_latest.json"
if os.path.exists(_mc_path):
    MCAP_LATEST = json.load(open(_mc_path))

def cap_of(sym):
    # the snapshot's market cap moves with the latest close, so it beats the
    # mirror metadata; the mirror value stays as the fallback
    v = MCAP_LATEST.get(sym)
    if v:
        return float(v)
    m = meta.get(sym) or meta.get(norm(sym)) or {}
    return m.get("mcap", 0.0) or 0.0

def cap_bucket(sym):
    v = cap_of(sym)
    if v <= 0: return "x"
    if v >= CAP_CUTS[0]: return "a"
    if v >= CAP_CUTS[1]: return "b"
    return "c"

def row(sym, q):
    fi, cs, vs, ff = SER[sym]
    m = meta.get(sym) or meta.get(norm(sym)) or {}
    g = gics.get(norm(sym), {})
    st = struct[sym]; u = univ[sym]
    n = len(cs)
    off = n - 60
    spark_b = [(i - off, round(c, 4)) for i, c in st["bots"] if i >= off]
    return {
        "sym": sym, "name": m.get("name", sym), "exch": exch.get(norm(sym), "—"),
        "sector": (g["gsec"] if (m.get("sp500") and g.get("gsec") in GICS_ZH) else m.get("sector", "—")),
        "sector_zh": (GICS_ZH[g["gsec"]] if (m.get("sp500") and g.get("gsec") in GICS_ZH)
                      else ZH_SECTOR.get(m.get("sector", "—"), m.get("sector", "—"))),
        "sec_src": ("GICS" if (m.get("sp500") and g.get("gsec") in GICS_ZH) else "Nasdaq"),
        "industry": m.get("industry", "—"),
        "gsec": g.get("gsec"), "gsub": g.get("gsub"), "sp500": m.get("sp500", False),
        "close": round(cs[-1], 2), "ma": round(q["ma"], 2), "below_ma": cs[-1] < q["ma"],
        "slope": round(q["slope"], 2), "L": q["L"], "W": q["W"],
        "vcp": elig[sym]["vcp"], "_vcpr": elig[sym]["vcp_raw"],
        "cert": st["cert"], "_certr": st["cert_raw"],
        "combo": st["combo"], "_combor": st["combo_raw"],
        "cert_c": {
            "broke": st["broke"], "H_mid": round(st["H_mid"], 2),
            "post_high": round(st["post_high"], 2),
            "retrace_pct": round(st["retrace"] * 100, 1),
            "d_held": st["d_held"], "undercut": st["undercut"],
            "dv_ratio": round(u["dv_ratio"], 2),
            "contr": round(st["contr"], 2),
            "rs21_pct": round(u["rs21"] * 100, 1),
            "ma_flags": u["ma_flags"],
            "s": {k: round(v, 3) for k, v in (
                ("break", st["s_break"]), ("retr", st["s_retr"]), ("time", st["s_time"]),
                ("dv", u["s_dv"]), ("contr", st["s_contr"]), ("rs", u["s_rs"]), ("ma", u["s_ma"]))},
        },
        "hits": hits[sym],
        "mcap": round(cap_of(sym) / 1e9, 3),
        "cap": cap_bucket(sym),
        "hl": [[CAL[fi + i], round(c, 4)] for i, c in st["hl"]],
        "spark": {"closes": [round(c, 4) for c in cs[-60:]],
                  "ma": [round(x, 4) if x else None for x in (sma_series(cs, q["L"]))[-60:]],
                  "dates": CAL[fi + n - 60: fi + n],
                  "bots": spark_b},
    }

cap_counts = {"a": 0, "b": 0, "c": 0, "x": 0}
for s in syms:
    cap_counts[cap_bucket(s)] += 1

out = {"meta": {"last_date": LAST_DATE, "cal_first": CAL[0], "cal_last": CAL[-1],
                "n_days": len(CAL), "counts": stats_counts, "eligible": len(syms),
                "mkt_med_21_pct": round(mkt_med * 100, 2),
                "cap_cuts_b": [CAP_CUTS[0] / 1e9, CAP_CUTS[1] / 1e9],
                "copied_days": [CAL[k] for k in sorted(SYN_DAYS)],
                "partial_volume_days": [CAL[k] for k in sorted(PARTIAL_VOL_DAYS)],
                "cap_counts": cap_counts},
       "pages": {}}

for p, (L, W, label) in PAGES.items():
    rows_all = [row(s, q) for s, q in qual[p].items()]
    rows_all.sort(key=lambda r: -r["_combor"])
    n_x = sum(1 for r in rows_all if r["cap"] == "x")
    for b in ("a", "b", "c"):
        sub = [r for r in rows_all if r["cap"] == b]
        pid = f"{p}{b}"
        out["pages"][pid] = {"L": L, "W": W, "label": label, "cap": b,
                             "cap_label": CAP_LABEL[b],
                             "qualified": len(sub), "rows": sub[:50]}
        print(f"P{pid} ({label} · {CAP_LABEL[b]}): qualified {len(sub)} -> listed {len(sub[:50])}")
    print(f"   P{p} total qualified {len(rows_all)}; 未分類（無市值資料，不入分頁）{n_x}")

SUBS = [f"{p}{b}" for p in PAGES for b in ("a", "b", "c")]
listed = {}
for pid in SUBS:
    for i, r in enumerate(out["pages"][pid]["rows"], 1):
        listed.setdefault(r["sym"], dict(r, ranks={}))["ranks"][pid] = i
p1 = []
for s, r in listed.items():
    score_raw = 0.4 * r["_vcpr"] + 0.4 * r["_certr"] + 0.2 * (hits[s] / 4 * 100)
    r["score"] = round(score_raw, 1)
    r["_scorer"] = score_raw
    p1.append(r)
p1.sort(key=lambda r: -r["_scorer"])
for r in p1:
    del r["_scorer"]
for pid in SUBS:
    for rr in out["pages"][pid]["rows"]:
        rr.pop("_vcpr", None); rr.pop("_certr", None); rr.pop("_combor", None)
for r in p1:
    r.pop("_vcpr", None); r.pop("_certr", None); r.pop("_combor", None)
out["page1"] = p1
by_cap = {b: sum(1 for r in p1 if r["cap"] == b) for b in ("a", "b", "c")}
print(f"P1 summary: {len(p1)} distinct tickers (大型 {by_cap['a']} · 中型 {by_cap['b']} · 小型 {by_cap['c']})")
OUT_JSON = os.environ.get("OUT_JSON", "screen_results8.json")
json.dump(out, open(f"{SCRATCH}/{OUT_JSON}", "w"), ensure_ascii=False)
print("counts:", stats_counts, "eligible:", len(syms), "with structure:", len(struct),
      "| eligible cap split:", cap_counts)

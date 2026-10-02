"""Macro-regime study: which past US episodes look like 2026-09/10 (oil shock,
Fed re-tightening, 10-year above 5%, index near a record), what led and lagged
then, and where the four forces (liquidity, politics, technology, shocks) stand.

Writes data/macro_regimes.json for scripts/macro_charts.py and
scripts/build_macro_xlsx.py. Run: python3 scripts/macro_regimes.py"""
import json, math, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import macro_data as D, macro_events as E

REPO = D.REPO
# BLS CPI-U all items, 12-month change, for the months after the Shiller mirror stops (2023-09)
CPI_YOY_RECENT = {"2023-10": 3.2, "2023-11": 3.1, "2023-12": 3.4,
                  "2024-01": 3.1, "2024-02": 3.2, "2024-03": 3.5, "2024-04": 3.4, "2024-05": 3.3, "2024-06": 3.0,
                  "2024-07": 2.9, "2024-08": 2.5, "2024-09": 2.4, "2024-10": 2.6, "2024-11": 2.7, "2024-12": 2.9,
                  "2025-01": 3.0, "2025-02": 2.8, "2025-03": 2.4, "2025-04": 2.3, "2025-05": 2.4, "2025-06": 2.7,
                  "2025-07": 2.7, "2025-08": 2.9, "2025-09": 3.0, "2025-10": 3.0, "2025-11": 2.7, "2025-12": 2.7,
                  "2026-01": 2.4, "2026-02": 2.4, "2026-03": 3.3, "2026-04": 3.8, "2026-05": 4.2, "2026-06": 3.5,
                  "2026-07": 3.4, "2026-08": 3.4, "2026-09": 3.4, "2026-10": 3.4}   # 09/10 = last print carried
NOW = pd.Timestamp("2026-10-31")

# ---- survivors baskets for the pre-ETF episodes -------------------------------------------------
SECTOR_OF = {
 "能源": "XOM CVX COP OXY SLB HAL APA HES EOG DVN VLO HP",
 "原材料": "DD AA NUE IP WY CLF PPG VMC FMC FCX",
 "黃金股": "NEM HL AEM ASA RGLD KGC",
 "工業": "CAT DE GE HON MMM BA LMT GD NOC RTX EMR ETN PH ITW DOV GWW CMI PCAR TXT",
 "運輸": "UNP CSX NSC FDX UPS R JBHT LUV ALK DAL UAL",
 "非必需消費": "F GM HD MCD DIS NKE TGT LOW GPS WHR TJX JWN M BBY KSS DRI MAR HAS MAT HOG GPC VFC",
 "房屋建築": "PHM LEN DHI KBH TOL NVR",
 "必需消費": "KO PEP PG CL MO GIS K HSY KMB CPB SYY WBA CAG HRL SJM CLX KR ADM TSN WMT",
 "醫療保健": "JNJ MRK PFE ABT LLY BMY BAX BDX MDT AMGN HUM UNH CI SYK TMO BSX GILD BIIB REGN",
 "科技": "IBM HPQ TXN INTC MSFT AAPL ORCL ADBE CSCO AMD MU ADI AMAT TER KLAC LRCX MSI QCOM NVDA ADP GLW XRX NTAP",
 "金融": "JPM BAC C WFC AXP USB PNC TRV AIG MMC AFL BK STT SCHW MS GS BRK-B MET PRU ALL CB PGR L CINF FITB KEY RF HBAN CMA MTB NTRS COF",
 "公用事業": "AEP DUK SO ED D EXC XEL PEG ETR PCG EIX NEE PPL DTE CMS AEE WEC ES FE NI CNP",
 "電訊／媒體": "T VZ CMCSA NYT OMC",
 "房地產": "SPG WELL PSA BXP EQR VTR O FRT AVB PLD",
}
SECTOR_OF = {k: v.split() for k, v in SECTOR_OF.items()}
# ETF / index proxies for the post-1998 episodes: (label, symbol, first month usable)
ETF_GROUPS = [("能源 XLE", "XLE"), ("油服 ^OSX", "^OSX"), ("原材料 XLB", "XLB"), ("黃金股 ^XAU", "^XAU"),
              ("工業 XLI", "XLI"), ("運輸 ^DJT", "^DJT"), ("非必需消費 XLY", "XLY"), ("房屋建築 ^HGX", "^HGX"),
              ("必需消費 XLP", "XLP"), ("醫療保健 XLV", "XLV"), ("科技 XLK", "XLK"), ("半導體 ^SOX", "^SOX"),
              ("金融 XLF", "XLF"), ("銀行 ^BKX", "^BKX"), ("公用事業 XLU", "XLU"), ("房地產 IYR", "IYR"),
              ("小型股 ^RUT", "^RUT"), ("納指 ^IXIC", "^IXIC"), ("價值 IWD", "IWD"), ("增長 IWF", "IWF"),
              ("長債 TLT", "TLT"), ("黃金 GLD", "GLD"), ("標普 500 ^GSPC", "^GSPC")]
BASKET_ORDER = ["能源", "黃金股", "原材料", "工業", "運輸", "非必需消費", "房屋建築", "必需消費", "醫療保健",
                "科技", "金融", "公用事業", "電訊／媒體", "房地產"]

def pm(s):  # 'YYYY-MM' -> month-end Timestamp
    return pd.Period(s, "M").to_timestamp("M")

def ret(series, a, b):
    s = series.dropna()
    s = s[(s.index >= a - pd.offsets.MonthEnd(1)) & (s.index <= b)]
    if len(s) < 2 or s.index[0] > a or s.index[-1] < b - pd.offsets.MonthEnd(1):
        return None
    return float(s.iloc[-1] / s.iloc[0] - 1)

def main():
    sh, oil, y10, gold, vix = D.shiller(), D.oil(), D.ten_year(), D.gold(), D.vix()
    adj, close = D.yahoo_monthly()
    idx = pd.date_range("1954-01-31", NOW, freq="ME")
    F = pd.DataFrame(index=idx)
    sp = close["^GSPC"].reindex(idx)
    sp = sp.fillna(sh["sp"].reindex(idx))                      # Yahoo month-end close, Shiller average as a fallback
    for m, (v, src) in D.PATCH.get("sp", {}).items():
        if pd.isna(sp.get(pm(m), np.nan)): sp.loc[pm(m)] = v
    F["sp"] = sp
    # CPI index extended with the published 12-month changes
    cpi = sh["cpi"].reindex(idx).copy()
    for m in sorted(CPI_YOY_RECENT):
        t = pm(m)
        if t in cpi.index and pd.isna(cpi.loc[t]):
            cpi.loc[t] = cpi.loc[t - pd.offsets.MonthEnd(12)] * (1 + CPI_YOY_RECENT[m] / 100)
    F["cpi"] = cpi
    F["cpi_yoy"] = cpi.pct_change(12) * 100
    F["cpi_src"] = ["BLS 補" if m.strftime("%Y-%m") in CPI_YOY_RECENT else "Shiller" for m in idx]
    w = oil["wti"].reindex(idx)
    for m, (v, src) in D.PATCH["wti"].items(): w.loc[pm(m)] = v
    F["wti"] = w; F["oil_src"] = oil["oil_src"].reindex(idx).fillna("patch")
    F["brent"] = oil["brent"].reindex(idx)
    t10 = y10.reindex(idx)
    tnx = close["^TNX"].reindex(idx) if "^TNX" in close else pd.Series(index=idx, dtype=float)
    t10 = t10.fillna(tnx)                                       # Yahoo ^TNX for the latest months
    for m, (v, src) in D.PATCH["y10"].items():
        if pd.isna(t10.loc[pm(m)]): t10.loc[pm(m)] = v
    F["y10"] = t10
    F["irx"] = close["^IRX"].reindex(idx)                       # 13-week bill: policy-rate proxy from 1960
    F["gold"] = gold.reindex(idx)
    for m, (v, src) in D.PATCH["gold"].items():
        if pd.isna(F.loc[pm(m), "gold"]): F.loc[pm(m), "gold"] = v
    F["vix"] = vix.reindex(idx)
    for m, (v, src) in D.PATCH["vix"].items():
        if pd.isna(F.loc[pm(m), "vix"]): F.loc[pm(m), "vix"] = v
    F["ixic"] = close["^IXIC"].reindex(idx) if "^IXIC" in close else np.nan
    F["dxy"] = close["DX-Y.NYB"].reindex(idx) if "DX-Y.NYB" in close else np.nan
    # derived
    F["sp_real"] = F["sp"] / F["cpi"] * F["cpi"].dropna().iloc[-1]
    F["oil_real"] = F["wti"] / F["cpi"] * F["cpi"].dropna().iloc[-1]
    F["oil_12m"] = np.log(F["wti"] / F["wti"].shift(12)) * 100
    F["irx_3m"] = F["irx"] - F["irx"].shift(3)
    F["irx_12m"] = F["irx"] - F["irx"].shift(12)
    F["y10_12m"] = F["y10"] - F["y10"].shift(12)
    F["slope"] = F["y10"] - F["irx"]
    F["real_rate"] = F["irx"] - F["cpi_yoy"]
    F["sp_12m"] = np.log(F["sp"] / F["sp"].shift(12)) * 100
    F["sp_dd"] = (F["sp"] / F["sp"].rolling(24, min_periods=6).max() - 1) * 100
    F["nq_rel_12m"] = np.log((F["ixic"] / F["sp"]) / (F["ixic"] / F["sp"]).shift(12)) * 100
    F["fwd6"] = (F["sp"].shift(-6) / F["sp"] - 1) * 100
    F["fwd12"] = (F["sp"].shift(-12) / F["sp"] - 1) * 100
    F["fwd24"] = (F["sp"].shift(-24) / F["sp"] - 1) * 100
    F["maxdd24"] = [((F["sp"].iloc[i + 1:i + 25].min() / F["sp"].iloc[i] - 1) * 100) if i + 24 < len(F) else np.nan for i in range(len(F))]
    F["maxdd12"] = [((F["sp"].iloc[i + 1:i + 13].min() / F["sp"].iloc[i] - 1) * 100) if i + 12 < len(F) else np.nan for i in range(len(F))]

    # ---- similarity: z-scored distance to the latest month on the regime features ----------------
    feats = ["oil_12m", "cpi_yoy", "irx_3m", "irx_12m", "y10_12m", "slope", "real_rate", "sp_12m", "sp_dd"]
    weights = {"oil_12m": 1.5, "cpi_yoy": 1.0, "irx_3m": 1.5, "irx_12m": 0.5, "y10_12m": 1.0, "slope": 0.75,
               "real_rate": 0.75, "sp_12m": 1.0, "sp_dd": 1.0}
    G = F.loc["1962-01-31":, feats].dropna()
    now_row = G.iloc[-1]; now_m = G.index[-1]
    Z = (G - G.mean()) / G.std()
    zn = Z.iloc[-1]
    wv = np.array([weights[f] for f in feats])
    dist = np.sqrt((((Z - zn) ** 2) * wv).sum(axis=1) / wv.sum())
    S = pd.DataFrame({"dist": dist, "fwd6": F["fwd6"].reindex(G.index), "fwd12": F["fwd12"].reindex(G.index),
                      "maxdd12": F["maxdd12"].reindex(G.index), "fwd24": F["fwd24"].reindex(G.index), "maxdd24": F["maxdd24"].reindex(G.index)})
    S = S[S.index < now_m - pd.offsets.MonthEnd(24)]
    top, used = [], []
    for t, r in S.sort_values("dist").iterrows():
        if any(abs((t - u).days) < 540 for u in used): continue
        used.append(t); top.append(t)
        if len(top) == 12: break
    sim_rows = [dict(month=t.strftime("%Y-%m"), dist=round(float(S.loc[t, "dist"]), 3),
                     **{f: round(float(G.loc[t, f]), 2) for f in feats},
                     fwd6=None if pd.isna(S.loc[t, "fwd6"]) else round(float(S.loc[t, "fwd6"]), 1),
                     fwd12=None if pd.isna(S.loc[t, "fwd12"]) else round(float(S.loc[t, "fwd12"]), 1),
                     maxdd12=None if pd.isna(S.loc[t, "maxdd12"]) else round(float(S.loc[t, "maxdd12"]), 1),
                     fwd24=None if pd.isna(S.loc[t, "fwd24"]) else round(float(S.loc[t, "fwd24"]), 1),
                     maxdd24=None if pd.isna(S.loc[t, "maxdd24"]) else round(float(S.loc[t, "maxdd24"]), 1)) for t in top]
    base_fwd12 = F.loc["1962-01-31":"2025-09-30", "fwd12"].dropna()
    sim = dict(now_month=now_m.strftime("%Y-%m"), features=feats, weights=weights,
               now={f: round(float(now_row[f]), 2) for f in feats}, top=sim_rows,
               base=dict(fwd12_median=round(float(base_fwd12.median()), 1), fwd12_pos=round(float((base_fwd12 > 0).mean() * 100), 1),
                         fwd6_median=round(float(F.loc["1962-01-31":"2026-03-31", "fwd6"].dropna().median()), 1),
                         maxdd12_median=round(float(F.loc["1962-01-31":"2025-09-30", "maxdd12"].dropna().median()), 1),
                         fwd24_median=round(float(F.loc["1962-01-31":"2024-09-30", "fwd24"].dropna().median()), 1),
                         maxdd24_median=round(float(F.loc["1962-01-31":"2024-09-30", "maxdd24"].dropna().median()), 1)),
               series={t.strftime("%Y-%m"): round(float(v), 3) for t, v in dist.items()})

    # ---- episodes ------------------------------------------------------------------------------
    def path(series, anchor, pre=12, post=24, rebase=True):
        a = pm(anchor); out = {}
        for k in range(-pre, post + 1):
            t = a + pd.offsets.MonthEnd(k)
            v = series.get(t, np.nan)
            if rebase:
                b = series.get(a, np.nan); v = (v / b - 1) * 100 if not (pd.isna(v) or pd.isna(b)) else np.nan
            out[k] = None if pd.isna(v) else round(float(v), 2)
        return out
    episodes = []
    for ep in E.EPISODES:
        a, (s0, s1) = pm(ep["anchor"]), (pm(ep["span"][0]), pm(ep["span"][1]))
        row = dict(ep)
        row["stats"] = {f: (None if pd.isna(F.loc[a, f]) else round(float(F.loc[a, f]), 2)) for f in
                        ["wti", "oil_12m", "cpi_yoy", "irx", "irx_3m", "irx_12m", "y10", "y10_12m", "slope", "real_rate", "sp_12m", "sp_dd", "vix"]}
        row["stats"]["dist"] = round(float(dist.get(a, np.nan)), 3) if a in dist.index else None
        row["paths"] = {"sp": path(F["sp"], ep["anchor"]), "wti": path(F["wti"], ep["anchor"]),
                        "irx": path(F["irx"], ep["anchor"], rebase=False), "y10": path(F["y10"], ep["anchor"], rebase=False),
                        "cpi_yoy": path(F["cpi_yoy"], ep["anchor"], rebase=False)}
        row["span_ret"] = {"sp": ret(F["sp"], s0, s1), "wti": ret(F["wti"], s0, s1), "gold": ret(F["gold"], s0, s1)}
        row["after12"] = {"sp": ret(F["sp"], a, a + pd.offsets.MonthEnd(12)), "wti": ret(F["wti"], a, a + pd.offsets.MonthEnd(12)),
                          "gold": ret(F["gold"], a, a + pd.offsets.MonthEnd(12))}
        row["maxdd12"] = None if pd.isna(F.loc[a, "maxdd12"]) else round(float(F.loc[a, "maxdd12"]), 1)
        # groups: ETFs/indices where they exist, survivors baskets otherwise (always computed for comparison)
        groups = []
        spw, spa = ret(adj["^GSPC"], s0, s1), ret(adj["^GSPC"], a, a + pd.offsets.MonthEnd(12))
        for label, sym in ETF_GROUPS:
            if sym not in adj: continue
            rw, ra = ret(adj[sym], s0, s1), ret(adj[sym], a, a + pd.offsets.MonthEnd(12))
            if rw is None and ra is None: continue
            groups.append(dict(group=label, sym=sym, kind="ETF/指數", n=1, win=rw, after=ra,
                               win_x=None if rw is None or spw is None else rw - spw, after_x=None if ra is None or spa is None else ra - spa))
        for sec in BASKET_ORDER:
            rs, ras = [], []
            for s in SECTOR_OF[sec]:
                if s not in adj: continue
                rw = ret(adj[s], s0, s1); ra = ret(adj[s], a, a + pd.offsets.MonthEnd(12))
                if rw is not None: rs.append(rw)
                if ra is not None: ras.append(ra)
            if len(rs) >= 3:
                mw, ma = float(np.mean(rs)), (float(np.mean(ras)) if ras else None)
                groups.append(dict(group=f"{sec}（{len(rs)} 隻等權）", sym=None, kind="長壽股籃", n=len(rs), win=mw, after=ma,
                                   win_x=None if spw is None else mw - spw, after_x=None if ma is None or spa is None else ma - spa,
                                   members=[s for s in SECTOR_OF[sec] if s in adj and ret(adj[s], s0, s1) is not None]))
        row["groups"] = groups
        row["sp_tr"] = {"win": spw, "after": spa}
        episodes.append(row)

    # ---- four forces: computed stats per cycle ----------------------------------------------------
    def spret(a, b):
        return ret(F["sp"], pm(a), pm(b)) if b else None
    forces = {}
    forces["liquidity"] = []
    for s0, s1, r0, r1, lab in E.HIKE_CYCLES:
        end = s1 or NOW.strftime("%Y-%m")
        a = pm(s0); e = pm(end)
        forces["liquidity"].append(dict(start=s0, end=s1, ff_from=r0, ff_to=r1, label=lab,
            sp_during=spret(s0, end), sp_after12=ret(F["sp"], e, e + pd.offsets.MonthEnd(12)) if s1 else None,
            sp_after_first12=ret(F["sp"], a, a + pd.offsets.MonthEnd(12)), maxdd_after_first=None if pd.isna(F.loc[a, "maxdd12"]) else round(float(F.loc[a, "maxdd12"]), 1),
            months=int((e.year - a.year) * 12 + e.month - a.month),
            maxdd_after=None if (not s1 or pd.isna(F.loc[e, "maxdd12"])) else round(float(F.loc[e, "maxdd12"]), 1),
            oil_during=ret(F["wti"], a, e), cpi_start=None if pd.isna(F.loc[a, "cpi_yoy"]) else round(float(F.loc[a, "cpi_yoy"]), 1),
            cpi_end=None if pd.isna(F.loc[e, "cpi_yoy"]) else round(float(F.loc[e, "cpi_yoy"]), 1),
            recession_after=next((p for p, t in E.RECESSIONS if pm(p) >= e and (pm(p) - e).days < 800), None)))
    forces["politics"] = []
    for y in E.MIDTERM_YEARS:
        if y > 2026: continue
        s0, s1 = pm(f"{y}-01"), min(pm(f"{y}-12"), NOW)
        seg = F.loc[s0 - pd.offsets.MonthEnd(1):s1, "sp"].dropna()
        if len(seg) < 6: continue
        peak_before_low = seg.cummax(); dd = (seg / peak_before_low - 1) * 100
        low_t = dd.idxmin()
        pres = [p for p in E.PRESIDENTS if pm(p[0]) <= s0][-1]
        forces["politics"].append(dict(year=y, president=pres[1], party=pres[2],
            maxdd=round(float(dd.min()), 1), low_month=low_t.strftime("%Y-%m"),
            year_ret=ret(F["sp"], s0, s1), from_low_12=ret(F["sp"], low_t, low_t + pd.offsets.MonthEnd(12)), partial=s1 < pm(f"{y}-12"),
            oil_12m=None if pd.isna(F.loc[s1, "oil_12m"]) else round(float(F.loc[s1, "oil_12m"]), 1),
            hiking=any(pm(h[0]) <= s1 and (h[1] is None or pm(h[1]) >= s0) for h in E.HIKE_CYCLES)))
    forces["tech"] = []
    for s0, s1, lab, lead in E.TECH_WAVES:
        end = s1 or NOW.strftime("%Y-%m")
        nq = ret(F["ixic"], pm(s0), pm(end)) if pm(s0) >= pm("1971-02") else None
        forces["tech"].append(dict(start=s0, end=s1, label=lab, leaders=lead, sp=spret(s0, end), nasdaq=nq,
                                   bust=next((b for b in E.TECH_BUSTS if pm(b[0]) >= pm(end) - pd.offsets.MonthEnd(1) and (pm(b[0]) - pm(end)).days < 400), None)))
    forces["tech_busts"] = [dict(start=b0, end=b1, sp=spret(b0, b1), nasdaq=ret(F["ixic"], pm(b0), pm(b1)) if pm(b0) >= pm("1971-02") else None) for b0, b1 in E.TECH_BUSTS]
    forces["shocks"] = []
    for m, lab, typ in E.SHOCKS:
        t = pm(m)
        seg = F.loc[t:t + pd.offsets.MonthEnd(6), "sp"].dropna()
        pre = F["sp"].get(t - pd.offsets.MonthEnd(1), np.nan)
        forces["shocks"].append(dict(month=m, label=lab, type=typ,
            dd3=None if (seg.empty or pd.isna(pre)) else round(float(seg.iloc[:4].min() / pre - 1) * 100, 1),
            r12=ret(F["sp"], t, t + pd.offsets.MonthEnd(12)), oil6=ret(F["wti"], t - pd.offsets.MonthEnd(1), t + pd.offsets.MonthEnd(6)),
            low_month=None if seg.empty else (seg.idxmin().strftime("%Y-%m"))))

    rel = F["ixic"] / F["sp"]
    forces["tech_extra"] = dict(
        nq_1999_06_to_2000_03=ret(F["ixic"], pm("1999-06"), pm("2000-03")), sp_1999_06_to_2000_03=ret(F["sp"], pm("1999-06"), pm("2000-03")),
        rel_1991_01_to_2000_03=float(rel.loc[pm("2000-03")] / rel.loc[pm("1991-01")]), rel_1995_01_to_2000_03=float(rel.loc[pm("2000-03")] / rel.loc[pm("1995-01")]),
        rel_2022_10_to_now=float(rel.dropna().iloc[-1] / rel.loc[pm("2022-10")]), nq_2022_10_to_now=ret(F["ixic"], pm("2022-10"), F["ixic"].dropna().index[-1]),
        months_ai=int((NOW.year - 2022) * 12 + NOW.month - 11))
    sup = []
    for m, lab, typ in E.SHOCKS:
        if "油震" not in typ: continue
        t = pm(m); w = F["wti"].loc[t:t + pd.offsets.MonthEnd(24)]; sp_ = F["sp"].loc[t:t + pd.offsets.MonthEnd(24)]
        if w.dropna().empty: continue
        # peak = first month reaching 95% of the 24-month maximum (the pre-1986 anchor path creeps up for years after a shock)
        pk = w[w >= 0.95 * w.max()].index[0]
        lo = sp_.loc[:pk + pd.offsets.MonthEnd(12)].idxmin() if not sp_.empty else None
        sup.append(dict(month=m, label=lab, oil_peak=pk.strftime("%Y-%m"), months_to_peak=int((pk.year - t.year) * 12 + pk.month - t.month),
                        oil_gain=float(w.max() / F["wti"].get(t - pd.offsets.MonthEnd(1), np.nan) - 1), sp_low=None if lo is None else lo.strftime("%Y-%m"),
                        low_vs_peak=None if lo is None else int((lo.year - pk.year) * 12 + lo.month - pk.month),
                        sp_dd=None if lo is None else float(sp_.loc[lo] / F["sp"].get(t - pd.offsets.MonthEnd(1), np.nan) - 1),
                        fed_hiking_after_peak=any(pm(h[0]) <= pk and (h[1] is None or pm(h[1]) > pk) for h in E.HIKE_CYCLES)))
    forces["supply_shocks"] = sup

    # ---- bear markets (monthly closes, >=20%) for the chart ------------------------------------
    bears, peak_t, peak_v, in_bear = [], None, -1, False
    s = F["sp"].dropna()
    run_max = s.cummax()
    i = 0
    while i < len(s):
        t = s.index[i]
        if s.iloc[i] >= run_max.iloc[i] and not in_bear:
            peak_t, peak_v = t, s.iloc[i]
        dd = s.iloc[i] / peak_v - 1
        if not in_bear and dd <= -0.20:
            in_bear = True; start = peak_t
        if in_bear and s.iloc[i] >= peak_v:
            seg = s.loc[start:t]; low = seg.idxmin()
            bears.append(dict(peak=start.strftime("%Y-%m"), trough=low.strftime("%Y-%m"), recovered=t.strftime("%Y-%m"),
                              dd=round(float(seg.min() / peak_v - 1) * 100, 1)))
            in_bear = False; peak_t, peak_v = t, s.iloc[i]
        i += 1

    now = {k: (None if pd.isna(F.loc[now_m, k]) else round(float(F.loc[now_m, k]), 2)) for k in F.columns if pd.api.types.is_numeric_dtype(F[k])}
    out = dict(now_month=now_m.strftime("%Y-%m"), now=now, similarity=sim, episodes=episodes, forces=forces, bears=bears,
               frame={c: [None if pd.isna(v) else round(float(v), 3) for v in F[c]] for c in
                      ["sp", "sp_real", "cpi_yoy", "wti", "oil_real", "y10", "irx", "gold", "vix", "ixic", "sp_dd", "dxy"]},
               months=[t.strftime("%Y-%m") for t in F.index],
               yahoo_symbols=sorted(adj.columns.tolist()), yahoo_first={s: adj[s].dropna().index[0].strftime("%Y-%m") for s in adj.columns if adj[s].notna().any()},
               patches={k: {m: v for m, v in d.items()} for k, d in D.PATCH.items()}, cpi_recent=CPI_YOY_RECENT)
    json.dump(out, open(f"{REPO}/data/macro_regimes.json", "w"), ensure_ascii=False, indent=0, default=float)
    print("now", now_m.date(), {f: round(float(now_row[f]), 2) for f in feats})
    print("top matches:", [(r["month"], r["dist"], r["fwd12"]) for r in sim_rows])
    for ep in episodes:
        print(ep["key"], ep["anchor"], "dist", ep["stats"]["dist"], "sp span", None if ep["span_ret"]["sp"] is None else round(ep["span_ret"]["sp"] * 100, 1),
              "after12", None if ep["after12"]["sp"] is None else round(ep["after12"]["sp"] * 100, 1), "groups", len(ep["groups"]))
    print("bears", len(bears), bears[-3:])

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Review layer for the hot-money pull-back screen (R23 onward).

Measures what the rules cannot see and writes it for the workbook: the
two-source price checks, a forward test of the previous revision's list (R22's
momentum-pullback names from their close to this one, against the universe
median), the previous revision's names under the new gates, the same rules on
the previous close, the pool of names at a rising-20MA pull-back that fail the
hot-money / 10MA / volatility gates, co-movement clusters, threshold survival,
and the flags that need outside research (sourced in RESEARCH_JSON). Every
number quoted in a finding is computed here, not typed in.

Env: WORK_DIR, SCREEN_JSON, PREVDAY_JSON, PREV_SCREEN (previous revision; old
rules), PREV_REVIEW, RESEARCH_JSON, YAHOO, SUPP, SNAP_DATES, OUT_REVIEW, REV,
PREV_REV, FINDINGS_MODULE.
"""
import csv, gzip, importlib, json, math, os, statistics

import numpy as np

W = os.environ.get("WORK_DIR", "./data")
ld = lambda k, d: json.load(open(f"{W}/{os.environ.get(k, d)}"))
S = ld("SCREEN_JSON", "screen_hm23.json")
PD = ld("PREVDAY_JSON", "screen_hm23_prevday.json")
PREV = ld("PREV_SCREEN", "screen_mp22.json")
PREV_RV = ld("PREV_REVIEW", "review_mp22.json")
RES = ld("RESEARCH_JSON", "research_hm23.json")
YAHOO = os.environ["YAHOO"]
SNAP_DATES = [d for d in os.environ.get("SNAP_DATES", "").split(",") if d]
OUT = os.environ.get("OUT_REVIEW", "review_hm23.json")
REV = os.environ.get("REV", "R23.00")
PREV_REV = os.environ.get("PREV_REV", "R22")

rows = S["rows"]; meta = S["meta"]; LAST = meta["last_date"]; P = meta["params"]
T1 = [r for r in rows if r["tier"] == 1]
RANK = {r["sym"]: r["rank"] for r in rows}
TIER = {r["sym"]: r["tier"] for r in rows}
BY = {r["sym"]: r for r in rows}
G = S["gates"]
GK = ("C1a", "C1b", "C2", "C3", "C4")
GZH = {"C1a": "C1a 事件日", "C1b": "C1b 熱錢", "C2": "C2 曾有10MA上升", "C3": "C3 回落20MA", "C4": "C4 波幅減低"}
pct = lambda x, d=1: f"{x * 100:+.{d}f}%"


def why_not(sym, gates=G):
    g = gates.get(sym)
    if not g:
        return "唔喺股票池（未夠 90 個上市交易日、收市 <$2、成交額不足或者已停止交易）"
    if not g["fail"]:
        return "全部通過"
    return "；".join(f"{GZH[k]}：{g['why'][k]}" for k in g["fail"])


# ---------------- closes: Yahoo + post-close snapshots ----------------
PREV_DATE = PREV["meta"]["last_date"]
Y = {}
with gzip.open(YAHOO, "rt") as f:
    for r in csv.DictReader(f):
        if r["date"] >= PREV_DATE:
            Y.setdefault(r["symbol"], {})[r["date"]] = float(r["close"])
snap = {}
for d in SNAP_DATES:
    m = {}
    for r in csv.DictReader(open(f"{W}/snapshots/{d}.csv", encoding="utf-8")):
        try:
            m[r["symbol"].strip()] = (float(r["lastsale"].strip("$ ").replace(",", "")), float(r["netchange"]))
        except ValueError:
            pass
    snap[d] = m
DAYS = sorted({d for m in Y.values() for d in m if d <= LAST})


def agree(pairs):
    d = [abs(a / b - 1) for a, b in pairs if b > 0]
    return len(d), (sum(x <= 0.005 for x in d) / len(d) if d else 0.0)


checks = []
AUD = meta.get("snap_audit", {})
for fname in sorted(AUD):
    a = AUD[fname]
    if a.get("action") == "dropped":
        checks.append((f"快照 {fname}", f"檔名係 {fname}，但入面係 {a['holds']} 嘅收市（吻合 {a['match']:.1%}，同 {fname} 只有 {a['own_match']:.1%}）：{a['holds']} 已有自己嘅快照，呢個檔棄用"))
    elif a.get("action") == "relabelled":
        checks.append((f"快照 {fname}", f"檔名係 {fname}，但入面係 {a['holds']} 嘅收市（吻合 {a['match']:.1%}，同 {fname} 只有 {a['own_match']:.1%}）：當 {a['holds']} 快照用；Nasdaq API 到美東早上五點都仲未轉日"))
for d in sorted(set(meta["snap_dates"])):
    fname = next((f for f, a in AUD.items() if a["holds"] == d and a.get("action") != "dropped"), d)
    sm = snap.get(fname) or {}
    if d not in DAYS or not sm:
        continue
    ys = {s: Y[s][d] for s in Y if d in Y[s]}
    n1, a1 = agree([(ys[s], sm[s][0]) for s in ys if s in sm])
    checks.append((f"{d} 收市", f"Yahoo 對 Nasdaq 收市後快照（檔 {fname}）：{n1:,} 隻，{a1:.1%} 喺 0.5% 之內"))
    k = DAYS.index(d)
    if k >= 1:
        pdv = DAYS[k - 1]
        n2, a2 = agree([(Y[s][pdv], sm[s][0] - sm[s][1]) for s in Y if pdv in Y[s] and s in sm])
        checks.append((f"{pdv} 收市", f"Yahoo 對 {d} 快照「收市 − 升跌」反推嘅前收：{n2:,} 隻，{a2:.1%} 喺 0.5% 之內"))
if LAST not in meta["snap_dates"]:
    checks.append((f"{LAST} 收市", f"冇官方快照（Nasdaq API 未轉日）；Yahoo 日線齊全（{meta['bars_last_day']:,} 隻），只得一個來源"))
if meta.get("listing_source") != "series":
    checks.append(("Nasdaq 序列", "R1–R22 用嚟做第二來源同上市日期嘅序列檔（data/series*.pkl，gitignore）喺 10-01 容器重設後消失；"
                               f"上市日期改由 data/nasdaq_listing_dates.json（R21／R22 審計所存，{len(json.load(open(f'{W}/nasdaq_listing_dates.json'))['dates'])} 隻）提供，"
                               f"另加 SPAC 空殼期偵測（今次捉到 {len(meta.get('shell_detected', {}))} 隻）；兩源核對只剩收市後快照"))
if T1:
    worst = max(T1, key=lambda r: r["xchk"]["max_abs_pct"])
    checks.append(("名單逐隻", f"{len(rows)} 隻（兩個梯隊）對快照日嘅最大差 {max(r['xchk']['max_abs_pct'] for r in rows):.3f}%；第一梯隊最大 {worst['xchk']['max_abs_pct']:.3f}%（{worst['sym']}）"))

# ---------------- forward test of the previous revision ----------------
fwd_days = [d for d in DAYS if PREV_DATE < d <= LAST]
u = [G[s]["close"] / Y[s][PREV_DATE] - 1 for s in G if PREV_DATE in Y.get(s, {})]
mkt_med = statistics.median(u)
prev_flags, FK = {}, {}
for r in PREV["rows"]:
    prev_flags[r["sym"]] = [t for _, t in r["flags"]]
    FK[r["sym"]] = {k for k, _ in r["flags"]}
for s, fl in (PREV_RV.get("extra_flags") or {}).items():
    prev_flags.setdefault(s, []).extend(t for _, t in fl)
    FK.setdefault(s, set()).update(k for k, _ in fl)


def state(sym):
    g = G.get(sym)
    if sym in BY:
        return f"符合新條件（第 {TIER[sym]} 梯隊）"
    if not g:
        return "跌出股票池"
    if g["below50"]:
        return "跌穿 MA50"
    if g["d20"] > P["dist_hi"]:
        return "已反彈離開 MA20"
    if g["d20"] < P["dist_lo"]:
        return "跌穿 MA20 超過 3%"
    return "仍喺 MA20 附近"


frows = []
for r in PREV["rows"]:
    s = r["sym"]
    c1 = (G.get(s) or {}).get("close") or Y.get(s, {}).get(LAST)
    ret = c1 / r["close"] - 1 if c1 else None
    frows.append({"prev_rank": r["rank"], "sym": s, "c0": r["close"], "c1": c1, "ret": ret,
                  "d20": (G.get(s) or {}).get("d20"), "state": state(s), "rank": RANK.get(s),
                  "new_fail": "、".join(GZH[k] for k in (G.get(s) or {}).get("fail", [])) if G.get(s) else "唔喺股票池",
                  "flags": "；".join(prev_flags.get(s, [])), "below_ma20_then": r["close"] < r["ma20"],
                  "score": r["score"], "fk": sorted(FK.get(s, []))})
fr = [x for x in frows if x["ret"] is not None]
med = lambda xs: statistics.median(xs) if xs else float("nan")


def grp(pred):
    xs = [x["ret"] for x in fr if pred(x)]
    return len(xs), med(xs), sum(v > 0 for v in xs)


def spearman(a, b):
    ra = np.argsort(np.argsort(a)); rb = np.argsort(np.argsort(b))
    return float(np.corrcoef(ra, rb)[0, 1])


n_all, m_all, up_all = grp(lambda x: True)
n_top, m_top, up_top = grp(lambda x: x["prev_rank"] <= 10)
n_bot, m_bot, up_bot = grp(lambda x: x["prev_rank"] > 10)
n_ab, m_ab, _ = grp(lambda x: not x["below_ma20_then"])
n_be, m_be, _ = grp(lambda x: x["below_ma20_then"])
n_fl, m_fl, _ = grp(lambda x: bool(x["fk"]))
n_nf, m_nf, _ = grp(lambda x: not x["fk"])
rho = spearman([x["score"] for x in fr], [x["ret"] for x in fr])
states = {}
for x in frows:
    states[x["state"]] = states.get(x["state"], 0) + 1
best = max(fr, key=lambda x: x["ret"]); worst_f = min(fr, key=lambda x: x["ret"])
forward = {
    "from": PREV_DATE, "n_days": len(fwd_days), "mkt_med": mkt_med,
    "summary": [
        ("整體", f"{PREV_REV} {n_all} 隻由 {PREV_DATE} 收市到 {LAST} 收市（{len(fwd_days)} 個交易日）中位數 {pct(m_all, 2)}，"
                 f"{up_all} 隻升；同期全體合資格股票中位數 {pct(mkt_med, 2)}。最好 {best['sym']} {pct(best['ret'])}，最差 {worst_f['sym']} {pct(worst_f['ret'])}。"),
        ("排名有冇用", f"前 10 名中位數 {pct(m_top, 2)}（{up_top}/{n_top} 升），其餘 {pct(m_bot, 2)}（{up_bot}/{n_bot} 升）；"
                     f"爆發潛力分數同期間回報嘅排名相關 {rho:+.2f}。{len(fwd_days)} 日樣本，唔可以當證明。"),
        ("收市喺 MA20 上定下", f"{PREV_DATE} 收市企喺 MA20 上面嘅 {n_ab} 隻中位數 {pct(m_ab, 2)}；收喺 MA20 下面嘅 {n_be} 隻 {pct(m_be, 2)}。"),
        ("審視標記", f"有標記嘅 {n_fl} 隻中位數 {pct(m_fl, 2)}，冇標記嘅 {n_nf} 隻 {pct(m_nf, 2)}。"),
        ("而家狀態", "；".join(f"{k} {v} 隻" for k, v in sorted(states.items(), key=lambda kv: -kv[1]))),
    ],
    "rows": sorted(frows, key=lambda x: x["prev_rank"]),
    "stats": {"m_all": m_all, "mkt_med": mkt_med, "m_top": m_top, "m_bot": m_bot, "m_ab": m_ab, "m_be": m_be,
              "n_ab": n_ab, "n_be": n_be, "m_fl": m_fl, "m_nf": m_nf, "rho": rho, "up_all": up_all, "states": states},
}

# ---------------- previous revision (old rules) under the new gates ----------------
prev_rank = {r["sym"]: r["rank"] for r in PREV["rows"]}
vs_prev = []
both = [s for s in BY if s in prev_rank]
for s in sorted(both, key=lambda s: RANK[s]):
    vs_prev.append({"kind": "兩版都上榜", "sym": s, "prev_rank": prev_rank[s], "rank": RANK[s], "why": f"第 {TIER[s]} 梯隊"})
for s in sorted((s for s in BY if s not in prev_rank), key=lambda s: RANK[s]):
    g = PREV["gates"].get(s)
    vs_prev.append({"kind": "新上榜", "sym": s, "prev_rank": None, "rank": RANK[s],
                    "why": f"第 {TIER[s]} 梯隊；{PREV_REV} 舊規則：" + ("、".join(g["fail"]) + " 唔過" if g and g["fail"] else ("動能未入頭 10%" if g else "唔喺股票池"))})
fail_count = {}
for s in sorted((s for s in prev_rank if s not in BY), key=lambda s: prev_rank[s]):
    vs_prev.append({"kind": "跌出", "sym": s, "prev_rank": prev_rank[s], "rank": None, "why": why_not(s)})
    for k in (G.get(s) or {}).get("fail", []):
        fail_count[k] = fail_count.get(k, 0) + 1

# ---------------- same rules on the previous close ----------------
pd_rows = {r["sym"]: r for r in PD["rows"]}
pd_t1 = {s for s, r in pd_rows.items() if r["tier"] == 1}
now, before = set(BY), set(pd_rows)
now1 = {r["sym"] for r in T1}
vs_prevday = []
for s in sorted(now & before, key=lambda s: RANK[s]):
    vs_prevday.append({"kind": "兩日都上榜", "sym": s, "prev_rank": pd_rows[s]["rank"], "rank": RANK[s],
                       "why": f"梯隊 {pd_rows[s]['tier']} → {TIER[s]}"})
for s in sorted(now - before, key=lambda s: RANK[s]):
    vs_prevday.append({"kind": "今日新上榜", "sym": s, "prev_rank": None, "rank": RANK[s], "why": f"第 {TIER[s]} 梯隊；上日：" + why_not(s, PD["gates"])})
for s in sorted(before - now, key=lambda s: pd_rows[s]["rank"]):
    vs_prevday.append({"kind": "今日跌出", "sym": s, "prev_rank": pd_rows[s]["rank"], "rank": None, "why": "今日：" + why_not(s)})

# ---------------- the pool at a rising-20MA pull-back ----------------
c3_pool = []
for s, g in G.items():
    if "C3" in g["fail"]:
        continue
    c3_pool.append({"sym": s, "tier": TIER.get(s), "fail": g["fail"], "why": g["why"], "d20": g["d20"], "dd": g["dd"],
                    "close": g["close"], "dv_ratio": g["dv_ratio"], "c20": g["c20"], "cleg": g["cleg"], "ev_vol": g["ev_vol"]})
c3_pool.sort(key=lambda x: (x["tier"] or 9, len(x["fail"]), x["sym"]))
pool_fail = {}
for x in c3_pool:
    for k in x["fail"]:
        pool_fail[k] = pool_fail.get(k, 0) + 1

# ---------------- concentration and co-movement ----------------
sec = {}
for r in rows:
    sec[r["sector_zh"]] = sec.get(r["sector_zh"], 0) + 1


def daily(sym):
    return np.diff(np.log(BY[sym]["spark"]["close"]))[-21:]


def med_corr(group):
    cs = [np.corrcoef(daily(a), daily(b))[0, 1] for i, a in enumerate(group) for b in group[i + 1:]]
    return float(np.median(cs)) if cs else None


all_c = med_corr(list(BY)) if len(BY) >= 2 else None
clusters = {}
for a in BY:
    mates = [b for b in BY if b != a and np.corrcoef(daily(a), daily(b))[0, 1] >= 0.6]
    if len(mates) >= 2:
        clusters[a] = mates
top_cluster = max(clusters.items(), key=lambda kv: len(kv[1]), default=(None, []))
clu = sorted([top_cluster[0]] + top_cluster[1], key=lambda s: RANK[s]) if top_cluster[0] else []
c_clu = med_corr(clu) if clu else None
c_rest = med_corr([s for s in BY if s not in clu]) if clu and len(BY) - len(clu) >= 2 else None

# ---------------- flags ----------------
extra = {}
for s, fl in RES["flags"].items():
    if s in BY:
        extra.setdefault(s, []).extend([(k, t) for k, t in fl])
for r in rows:
    if r["dv20"] < 5e6:
        extra.setdefault(r["sym"], []).append(("liq", f"20 日成交額中位數只有 ${r['dv20'] / 1e6:.1f}M（股票池下限 $1M），入市出市都會有滑價"))
    if r["close"] < 2.5:
        extra.setdefault(r["sym"], []).append(("floor", f"收市 ${r['close']:.2f}，貼近股票池 $2 下限"))
if clu and len(clu) >= 3:
    for s in clu:
        extra.setdefault(s, []).append(("cluster", f"同名單入面 {'、'.join(x for x in clu if x != s)} 同向（21 日相關系數中位數 {c_clu:+.2f}"
                                                   + (f"，名單其餘 {c_rest:+.2f}" if c_rest is not None else "") + "）：當一個交易睇"))

survive = {r["sym"]: sum(1 for x in S["sensitivity"] if r["sym"] not in x["dropped"] and not str(x["param"]).startswith("全部")) for r in T1}
n_sens = sum(1 for x in S["sensitivity"] if not str(x["param"]).startswith("全部"))
robust = [r["sym"] for r in T1 if survive[r["sym"]] == n_sens]
PN = {"ev_ret": "事件日升幅", "ev_vol": "事件日量比", "hot_dv": "升浪成交額比", "ma10_rise": "MA10 10日升幅", "ma10_frac": "MA10 上升步比例",
      "ext_min": "高位時高過MA20", "depth_max": "最深回調", "dist_lo": "距MA20下限", "dist_hi": "距MA20上限", "touch_tol": "觸及容差",
      "c20": "ATR5/ATR20 上限", "cleg": "ATR5/升浪ATR 上限", "hi_ago_max": "高位最遠日數"}
br = {b["date"]: b for b in meta["breadth"]}
list_move = statistics.median(r["close"] / r["prev"] - 1 for r in rows) if rows else float("nan")
unresearched = [s for s in BY if s not in RES["research"] and s not in RES["carried"]]
needs_count = {}
for r in rows:
    for k in r["needs"]:
        needs_count[k] = needs_count.get(k, 0) + 1

STATS = {"forward": forward["stats"], "robust": robust, "clu": clu, "c_clu": c_clu, "c_rest": c_rest, "all_c": all_c,
         "list_move": list_move, "sec": sec, "both_prev": both, "n_new": len(now - set(prev_rank)), "n_out": len(set(prev_rank) - now),
         "pd_both": len(now & before), "pd_n": len(before), "pd_t1": len(pd_t1), "now_t1": len(now1), "t1_both": len(now1 & pd_t1),
         "unresearched": unresearched, "pool_n": len(c3_pool), "pool_fail": pool_fail, "needs_count": needs_count,
         "prev_fail_count": fail_count, "n_sens": n_sens}

# ---------------- findings (text per revision; numbers from above) ----------------
F = importlib.import_module(os.environ.get("FINDINGS_MODULE", "findings_hm23"))
findings, notes = F.build(dict(globals()))

market = [(a, b) for a, b in RES["market"]]
market.append(("大市闊度", "合資格股票每日中位數："
               + "；".join(f"{b['date'][5:]} {pct(b['med'], 2)}（{b['up']:.0%} 上升）" for b in meta["breadth"][-4:])))

json.dump({"extra_flags": extra, "near_miss_detail": S["near_miss"], "vs_prev": vs_prev, "vs_prevday": vs_prevday,
           "prevday_date": PD["meta"]["last_date"], "forward": forward, "c3_pool": c3_pool, "findings": findings,
           "xchk_summary": checks, "market": market, "breadth": meta["breadth"], "notes": notes,
           "survive": survive, "n_sens": n_sens,
           "flag_action": {"deal": "保留喺名單但標橙底；併購目標跟收購方走，唔係呢個條件想捉嘅股票（待你決定要唔要剔走）",
                           "event": "保留、標橙底；要當事件交易睇", "offering": "保留、標橙底；留意配售價",
                           "heavy_break": "保留、標橙底；睇之後幾日企唔企得返 MA20", "liq": "保留、標橙底；落單注意滑價",
                           "floor": "保留、標橙底", "cluster": "保留、標橙底；當一個交易睇", "gapdown": "保留、標橙底；回調入面有急跌日",
                           "pinned": "保留、標橙底；要查併購", "data": "保留；數據同媒體有出入，見催化劑頁"},
           "stats": STATS},
          open(f"{W}/{OUT}", "w"), ensure_ascii=False, indent=1, default=str)
print("wrote", OUT, "| findings", len(findings), "| flags on", len(extra), "names | tier1", len(T1), "| prev-day tier1 overlap",
      len(now1 & pd_t1), "| forward median", round(m_all * 100, 2), "vs", round(mkt_med * 100, 2), "| pool", len(c3_pool))

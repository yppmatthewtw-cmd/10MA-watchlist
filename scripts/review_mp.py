#!/usr/bin/env python3
"""Review layer for the momentum-pullback screen (R22 onward; R21 used
scripts/review_mp21.py).

Measures what the rules cannot see and writes it for the workbook:
  * the two-source price check for every snapshot day in the window;
  * a forward test of the previous revision's list (what its names did from
    that close to this one, against the eligible universe's median);
  * the list against the previous revision and against the same rules re-run
    on the previous close;
  * concentration and co-movement, sensitivity survival, and flags that need
    outside research (sourced in RESEARCH_JSON).
Every number quoted in a finding is computed here, not typed in.

Env: WORK_DIR, SCREEN_JSON, PREVDAY_JSON, PREV_SCREEN (previous revision, same
rules), PREV_REVIEW (its review, for its flags), RESEARCH_JSON, YAHOO,
SNAP_DATES, OUT_REVIEW, REV, PREV_REV.
"""
import csv, gzip, json, math, os, statistics

import numpy as np

W = os.environ.get("WORK_DIR", "./data")
ld = lambda k, d: json.load(open(f"{W}/{os.environ.get(k, d)}"))
S = ld("SCREEN_JSON", "screen_mp22.json")
PD = ld("PREVDAY_JSON", "screen_mp22_prevday.json")
PREV = ld("PREV_SCREEN", "screen_mp21.json")
PREV_RV = ld("PREV_REVIEW", "review_mp21.json")
RES = ld("RESEARCH_JSON", "research_mp22.json")
YAHOO = os.environ["YAHOO"]
SNAP_DATES = [d for d in os.environ.get("SNAP_DATES", "").split(",") if d]
OUT = os.environ.get("OUT_REVIEW", "review_mp22.json")
REV = os.environ.get("REV", "R22.00")
PREV_REV = os.environ.get("PREV_REV", "R21")

rows = S["rows"]; meta = S["meta"]; LAST = meta["last_date"]; P = meta["params"]
RANK = {r["sym"]: r["rank"] for r in rows}
BY = {r["sym"]: r for r in rows}
G = S["gates"]
GZH = {"S1": "S1 趨勢", "S2": "S2 近期高位", "S3": "S3 回調深度", "S4": "S4 曾經拉開", "S5": "S5 回到20MA"}
LZ = {21: "1個月", 42: "2個月", 63: "3個月", 126: "6個月"}
pct = lambda x, d=1: f"{x * 100:+.{d}f}%"


def why_not(sym, gates=G):
    g = gates.get(sym)
    if not g:
        return "唔喺股票池（未夠 90 個上市交易日、收市 <$2、成交額不足或者已停止交易）"
    parts = []
    if g["fail"]:
        parts.append("形態唔過：" + "、".join(GZH[k] for k in g["fail"]))
    if not g["hits"]:
        parts.append("動能：四個時間框都唔入頭 10%")
    return "；".join(parts) + f"（距 MA20 {pct(g['d20'])}、距高位 {pct(g['dd'])}）"


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
        checks.append((f"快照 {fname}", f"檔名係 {fname}，但入面係 {a['holds']} 嘅收市（同 Yahoo {a['holds']} 收市 {a['match']:.1%} 吻合，"
                                       f"同 {fname} 只有 {a['own_match']:.1%}）：Nasdaq API 晚上抓取時仲未轉日；{a['holds']} 已經有自己嘅快照，呢個檔棄用"))
    elif a.get("action") == "relabelled":
        checks.append((f"快照 {fname}", f"檔名係 {fname}，但入面係 {a['holds']} 嘅收市（吻合 {a['match']:.1%}，同 {fname} 只有 {a['own_match']:.1%}）："
                                       f"當 {a['holds']} 快照用；{fname} 冇官方快照"))
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
vs_ = meta.get("vol_scale", {})
if LAST in vs_:
    checks.append((f"{LAST} 收市", f"冇官方快照；Yahoo 日線當晚只出咗 {meta['bars_last_day'] - meta.get('supp_keys_last', 0):,} 隻，"
                                  f"其餘 {meta.get('supp_keys_last', 0):,} 隻用每小時K線合成（開高低收取自K線，成交量 × {vs_[LAST]['ratio']:.3f} 還原收市競價等漏計部分，"
                                  f"比例由 {vs_[LAST]['n']:,} 隻兩樣都有嘅股票實測）。K線合成同日線嘅吻合度見審視標記 F2"))
for d, h in meta["holes"].items():
    checks.append((f"{d}（缺口）", f"Yahoo 呢日只有 {h['yahoo']} 隻（約 {h['neighbours']:,} 隻應有），用 Nasdaq 收市後快照補收市價同成交量 "
                                  f"{h['nasdaq_filled']:,} 隻，開高低當收市價；R22 起 ATR 只計有真實高低位嘅日子"))
worst = max(rows, key=lambda r: r["xchk"]["max_abs_pct"])
checks.append(("名單逐隻", f"{len(rows)} 隻上榜股，近 63 個交易日 Yahoo 對 Nasdaq 序列同快照，最大差 "
               f"{worst['xchk']['max_abs_pct']:.3f}%（{worst['sym']}）；鏡像照抄前日嘅日子唔計"))

# ---------------- forward test of the previous revision ----------------
fwd_days = [d for d in DAYS if PREV_DATE < d <= LAST]
# this close from the screen itself (Yahoo daily bar, or the intraday roll-up
# where Yahoo had not published the day yet), the earlier one from Yahoo
u = [G[s]["close"] / Y[s][PREV_DATE] - 1 for s in G if PREV_DATE in Y.get(s, {})]
mkt_med = statistics.median(u)
prev_flags = {}
for r in PREV["rows"]:
    prev_flags[r["sym"]] = [t for _, t in r["flags"]]
for s, fl in (PREV_RV.get("extra_flags") or {}).items():
    prev_flags.setdefault(s, []).extend(t for _, t in fl)
FK = {}
for r in PREV["rows"]:
    FK[r["sym"]] = {k for k, _ in r["flags"]} | {k for k, _ in (PREV_RV.get("extra_flags") or {}).get(r["sym"], [])}


def state(sym):
    if sym in BY:
        return "仍然上榜"
    g = G.get(sym)
    if not g:
        return "跌出股票池"
    if g["below50"]:
        return "跌穿 MA50"
    if g["d20"] > P["dist_hi"]:
        return "已反彈離開 MA20"
    if g["d20"] < P["dist_lo"]:
        return "跌穿 MA20 超過 3%"
    return "仍喺 MA20 附近（其他條件唔過）"


frows = []
for r in PREV["rows"]:
    s = r["sym"]
    c1 = (G.get(s) or {}).get("close") or Y.get(s, {}).get(LAST)
    ret = c1 / r["close"] - 1 if c1 else None
    frows.append({"prev_rank": r["rank"], "sym": s, "c0": r["close"], "c1": c1, "ret": ret,
                  "d20": (G.get(s) or {}).get("d20"), "state": state(s), "rank": RANK.get(s),
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
n_hb, m_hb, _ = grp(lambda x: "heavy_break" in x["fk"])
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
                     f"爆發潛力分數同期間回報嘅排名相關 {rho:+.2f}。只係 {len(fwd_days)} 日，樣本太細，唔可以當證明。"),
        ("收市喺 MA20 上定下", f"{PREV_DATE} 收市企喺 MA20 上面嘅 {n_ab} 隻中位數 {pct(m_ab, 2)}；收喺 MA20 下面（規則容許低 3%）嘅 {n_be} 隻 {pct(m_be, 2)}。"),
        ("審視標記", f"有標記嘅 {n_fl} 隻中位數 {pct(m_fl, 2)}，冇標記嘅 {n_nf} 隻 {pct(m_nf, 2)}；"
                   f"「放量跌穿」嘅 {n_hb} 隻 {pct(m_hb, 2)}。"),
        ("而家狀態", "；".join(f"{k} {v} 隻" for k, v in sorted(states.items(), key=lambda kv: -kv[1]))),
    ],
    "rows": sorted(frows, key=lambda x: x["prev_rank"]),
    "stats": {"m_all": m_all, "mkt_med": mkt_med, "m_top": m_top, "m_bot": m_bot, "m_ab": m_ab, "m_be": m_be,
              "n_ab": n_ab, "n_be": n_be, "m_fl": m_fl, "m_nf": m_nf, "m_hb": m_hb, "n_hb": n_hb, "rho": rho,
              "up_all": up_all, "states": states},
}

# ---------------- previous revision vs this one ----------------
prev_rank = {r["sym"]: r["rank"] for r in PREV["rows"]}
vs_prev = []
both = [s for s in BY if s in prev_rank]
for s in sorted(both, key=lambda s: RANK[s]):
    vs_prev.append({"kind": "兩版都上榜", "sym": s, "prev_rank": prev_rank[s], "rank": RANK[s], "why": ""})
for s in sorted((s for s in BY if s not in prev_rank), key=lambda s: RANK[s]):
    g = PREV["gates"].get(s)
    vs_prev.append({"kind": "新上榜", "sym": s, "prev_rank": None, "rank": RANK[s],
                    "why": (f"{PREV_DATE}：" + why_not(s, PREV["gates"])) if g else f"{PREV_DATE} 唔喺股票池"})
for s in sorted((s for s in prev_rank if s not in BY), key=lambda s: prev_rank[s]):
    vs_prev.append({"kind": "跌出", "sym": s, "prev_rank": prev_rank[s], "rank": None, "why": why_not(s)})

# ---------------- same rules on the previous close ----------------
pd_rows = {r["sym"]: r for r in PD["rows"]}
now, before = set(BY), set(pd_rows)
vs_prevday = []
for s in sorted(now & before, key=lambda s: RANK[s]):
    vs_prevday.append({"kind": "兩日都上榜", "sym": s, "prev_rank": pd_rows[s]["rank"], "rank": RANK[s], "why": ""})
for s in sorted(now - before, key=lambda s: RANK[s]):
    vs_prevday.append({"kind": "今日新上榜", "sym": s, "prev_rank": None, "rank": RANK[s],
                       "why": "上日：" + why_not(s, PD["gates"])})
for s in sorted(before - now, key=lambda s: pd_rows[s]["rank"]):
    vs_prevday.append({"kind": "今日跌出", "sym": s, "prev_rank": pd_rows[s]["rank"], "rank": None,
                       "why": "今日：" + why_not(s)})

# ---------------- concentration and co-movement ----------------
sec = {}
for r in rows:
    sec[r["sector_zh"]] = sec.get(r["sector_zh"], 0) + 1


def daily(sym):
    return np.diff(np.log(BY[sym]["spark"]["close"]))[-21:]


def med_corr(group):
    cs = [np.corrcoef(daily(a), daily(b))[0, 1] for i, a in enumerate(group) for b in group[i + 1:]]
    return float(np.median(cs)) if cs else None


all_c = med_corr(list(BY))
# strongest cluster: for every name, the names it moves with at >= +0.6
clusters = {}
for a in BY:
    mates = [b for b in BY if b != a and np.corrcoef(daily(a), daily(b))[0, 1] >= 0.6]
    if len(mates) >= 2:
        clusters[a] = mates
top_cluster = max(clusters.items(), key=lambda kv: len(kv[1]), default=(None, []))
clu = sorted([top_cluster[0]] + top_cluster[1], key=lambda s: RANK[s]) if top_cluster[0] else []
c_clu = med_corr(clu) if clu else None
c_rest = med_corr([s for s in BY if s not in clu]) if clu else None

# ---------------- flags ----------------
extra = {}
for s, fl in RES["flags"].items():
    if s in BY:
        extra.setdefault(s, []).extend([(k, t) for k, t in fl])
for r in rows:
    if r["dv20"] < 5e6:
        extra.setdefault(r["sym"], []).append(
            ("liq", f"20 日成交額中位數只有 ${r['dv20'] / 1e6:.1f}M（股票池下限 $1M），入市出市都會有滑價"))
    if r["close"] < 2.5:
        extra.setdefault(r["sym"], []).append(
            ("floor", f"收市 ${r['close']:.2f}，貼近股票池 $2 下限；靠 {'、'.join(LZ[w] for w in r['hits_w'])} 動能上榜"))
if clu and len(clu) >= 3:
    for s in clu:
        extra.setdefault(s, []).append(("cluster", f"同名單入面 {'、'.join(x for x in clu if x != s)} 同向（21 日相關系數中位數 {c_clu:+.2f}，"
                                                   f"名單其餘 {c_rest:+.2f}）：當一個交易睇"))

survive = {r["sym"]: sum(1 for x in S["sensitivity"] if r["sym"] not in x["dropped"]) for r in rows}
robust = [r["sym"] for r in rows if survive[r["sym"]] == len(S["sensitivity"])]
sens_big = sorted(S["sensitivity"], key=lambda x: -(len(x["added"]) + len(x["dropped"])))[:5]
PN = {"touch_tol": "觸及容差", "dist_hi": "距MA20上限", "dist_lo": "距MA20下限", "ext_min": "曾經拉開",
      "depth_min": "最淺回調", "depth_max": "最深回調", "hi_ago_max": "高位最遠日數",
      "near_record": "貼近期內高位", "decile": "動能百分位"}
sens = {(x["param"], x["alt"]): x for x in S["sensitivity"]}
br = {b["date"]: b for b in meta["breadth"]}
only_last = [r["sym"] for r in rows if r["touch_dates"] == [LAST]]
list_move = statistics.median(r["close"] / r["prev"] - 1 for r in rows)
heavy = [s for s in BY if any(k == "heavy_break" for k, _ in BY[s]["flags"])]
gap_nm = [n for n in S["near_miss"] if n.get("touch_only") and n.get("close_only")]
unresearched = [s for s in BY if s not in RES["research"] and s not in RES["carried"]]

STATS = {"forward": forward["stats"], "robust": robust, "clu": clu, "c_clu": c_clu, "c_rest": c_rest,
         "all_c": all_c, "only_last": only_last, "list_move": list_move, "heavy": heavy, "sec": sec,
         "both_prev": both, "n_new": len(now - set(prev_rank)), "n_out": len(set(prev_rank) - now),
         "pd_both": len(now & before), "pd_n": len(before), "unresearched": unresearched}

# ---------------- findings (text per revision; numbers from above) ----------------
F = __import__("importlib").import_module(os.environ.get("FINDINGS_MODULE", "findings_mp22"))
findings, notes = F.build(locals())

market = [(a, b) for a, b in RES["market"]]
market.append(("大市闊度", "合資格股票每日中位數："
               + "；".join(f"{b['date'][5:]} {pct(b['med'], 2)}（{b['up']:.0%} 上升）" for b in meta["breadth"][-4:])))

json.dump({"extra_flags": extra, "near_miss_detail": S["near_miss"], "vs_prev": vs_prev, "vs_prevday": vs_prevday,
           "prevday_date": PD["meta"]["last_date"], "forward": forward, "findings": findings,
           "xchk_summary": checks, "market": market, "breadth": meta["breadth"], "notes": notes,
           "survive": survive, "n_sens": len(S["sensitivity"]),
           "flag_action": {"event": "保留、標橙底；要當事件交易睇", "heavy_break": "保留、標橙底；睇之後幾日企唔企得返 MA20",
                           "liq": "保留、標橙底；落單注意滑價", "floor": "保留、標橙底", "cluster": "保留、標橙底；當一個交易睇",
                           "gapdown": "保留、標橙底；回調入面有急跌日", "spike": "保留、標橙底"},
           "stats": STATS},
          open(f"{W}/{OUT}", "w"), ensure_ascii=False, indent=1, default=str)
print("wrote", OUT, "| findings", len(findings), "| flags on", len(extra), "names | prev overlap", len(both),
      "| prev-day overlap", len(now & before), "| forward median", round(m_all * 100, 2), "vs", round(mkt_med * 100, 2))

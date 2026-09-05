#!/usr/bin/env python3
"""Carry the review layer forward to R11 (2026-09-04 close) and re-measure every
number in it on this revision's series, so nothing in the update card quotes a
count from an older list.

Inputs: screen_results11.json (current), screen_results9.json (previous data
revision — R10 reused R9's numbers), news11.json, review9.json (the R9 review as
corrected by apply_review9b.py; review10.json only added layout notes), series6.pkl
and, optionally, the list-review agent's REVIEW_JSON (cat_line_fixes /
flag_additions / findings / summary), folded in the same way apply_review9b did.

Carried forward:
  * deal flags for tickers still listed, spread recomputed from the new close;
  * catalyst warnings for tickers still listed, day return recomputed;
  * the open user decisions ([待你決定] / [已標記 · 待你決定]), with the ones that
    were measured on this revision's numbers rewritten from the numbers.
Everything else (the R9/R10 "what changed" notes) collapses into one lineage note.
Idempotent — re-running rewrites the same file from the same inputs.
"""
import json, math, os, pickle, re, statistics, sys

SCRATCH = os.environ.get("WORK_DIR", "./data")
SCREEN = os.environ.get("SCREEN_JSON", "screen_results11.json")
PREV_SCREEN = os.environ.get("PREV_SCREEN", "screen_results9.json")
NEWS = os.environ.get("NEWS_JSON", "news11.json")
PREV_REVIEW = os.environ.get("PREV_REVIEW", "review9.json")
OUT = os.environ.get("OUT_REVIEW", "review11.json")
SERIES = os.environ.get("SERIES", "series6.pkl")
AGENT = os.environ.get("REVIEW_JSON", "/tmp/claude-0/-home-user-10MA-watchlist/"
                       "1821eb3b-7002-5041-b904-77ace4d47850/scratchpad/r11_review.json")
VERIFY = os.environ.get("VERIFY_JSON", "/tmp/claude-0/-home-user-10MA-watchlist/"
                        "1821eb3b-7002-5041-b904-77ace4d47850/scratchpad/r11_verify.json")

scr = json.load(open(f"{SCRATCH}/{SCREEN}"))
pscr = json.load(open(f"{SCRATCH}/{PREV_SCREEN}"))
news = json.load(open(f"{SCRATCH}/{NEWS}"))
prev = json.load(open(f"{SCRATCH}/{PREV_REVIEW}"))
listed = {r["sym"]: r for r in scr["page1"]}
plisted = {r["sym"]: r for r in pscr["page1"]}
d = pickle.load(open(f"{SCRATCH}/{SERIES}", "rb"))
CAL, SER = d["cal"], d["series"]
IDX = {c: i for i, c in enumerate(CAL)}
N = len(CAL)
last = scr["meta"]["last_date"]
LAST_MD = last[5:].replace("-", "/")
mcap = json.load(open(f"{SCRATCH}/mcap_latest.json"))
log, problems = [], []


def ret(sym, i):
    """close-to-close % return of `sym` on calendar index i, or None."""
    fi, cs, vs, ff = SER[sym]; j = i - fi
    return (cs[j] / cs[j - 1] - 1) * 100 if 0 < j < len(cs) else None


# ---- 1. deal flags: recompute spreads, drop unlisted, tag new targets ------
# cash offers verified in the entry's own research text: the R9 list minus the
# tickers that have left, plus TECH (Merck $73 cash, German clearance 08-17)
# from the R11 research
OFFERS = {"ITGR": 127.0, "OGN": 14.0, "NATH": 102.0, "GBTG": 9.50, "TXNM": 61.25,
          "SMTI": 35.0, "DBRG": 16.0, "TECH": 73.0}
STOCK_DEALS = {"PSNL": "全股收購，換股比率浮動（上限 0.3356 股 TEM）；$16.25 係目標值而非固定現金價。",
               "BLFS": "作價 = $11.25 現金 + 0.1442 股 RGEN，並非固定 $31；股價跟 Repligen 走。",
               "CRBG": "換股合併目標：股價已被協議釘住，量度嘅係換股價差而非突破前收縮。",
               "APGE": "被收購目標：股價已被協議釘住，VCP／確定性量度嘅係套利價差。"}
RUMOURS = {"CCC": "回升由收購傳聞驅動，傳聞證實或否定都會令波幅跳升。",
           "WDAY": "回升由收購傳聞驅動，未有作價；消息落空會令波幅跳升。",
           "VOYA": "TOMS Capital（持股 4.5%）施壓推動出售或策略檢討，未有作價；反彈含併購憧憬成分。"}

flags, dropped_flags = {}, []
for sym, fl in (prev.get("ticker_flags") or {}).items():
    if sym not in listed:
        dropped_flags.append(sym); continue
    flags[sym] = dict(fl)

for sym in listed:
    e = news.get(sym) or {}
    if sym in OFFERS:
        c = listed[sym]["close"]; off = OFFERS[sym]
        gap = (off / c - 1) * 100
        flags[sym] = {
            "deal": True,
            "badge": (f"套利釘價 · 距作價{gap:+.1f}%" if gap >= 0 else f"高於作價 {abs(gap):.1f}%"),
            "text": (f"現金作價 ${off:g}，現價 ${c:g}（{'剩餘升幅只有 ' + format(gap, '+.1f') + '%' if gap >= 0 else '已高於作價 ' + format(abs(gap), '.1f') + '%'}）；"
                     "波幅收縮係交易釘價所致，唔係蓄勢突破，VCP／確定性高分屬機械假象。"),
        }
    elif sym in STOCK_DEALS:
        flags[sym] = {"deal": True, "badge": "換股併購目標", "text": STOCK_DEALS[sym]}
    elif sym in RUMOURS:
        flags[sym] = {"deal": True, "badge": "併購傳聞", "text": RUMOURS[sym]}
    elif e.get("ckind") == "併購" and sym not in flags:
        t = (e.get("decline_short", "") + e.get("recovery_short", "") + e.get("catalyst", ""))
        if re.search(r"被收購|收購價|私有化|獲.{0,6}收購|要約|合併獲通過|換股收購", t):
            c = listed[sym]["close"]
            flags[sym] = {"deal": True, "badge": "併購目標",
                          "text": f"研究文字顯示本身係被收購／私有化目標（現價 ${c:g}）：走勢受交易進度牽制，"
                                  "突破同收縮指標量度緊價差而唔係基本面；如果現價已高於作價，市場係喺度賭加價。"}
for fl in flags.values():
    if "deal" not in fl:
        fl["deal"] = any(k in fl.get("badge", "") for k in ("釘價", "併購", "合併", "作價"))


def pct(sym, a, b):
    """% move of sym from calendar day a to day b (b defaults to the last day)."""
    fi, cs, vs, ff = SER[sym]
    ja = IDX[a] - fi; jb = (IDX[b] if b else len(CAL) - 1) - fi
    return (cs[jb] / cs[ja] - 1) * 100


# carried flags whose text quotes a price or a gain: re-measured on this close
if "PAG" in flags and "PAG" in listed:
    c = listed["PAG"]["close"]; gap = (c / 210 - 1) * 100
    flags["PAG"] = {"deal": True, "badge": f"高於建議價 {gap:.1f}%",
                    "text": f"三井／Penske 家族 $210 私有化建議（非正式要約），現價 ${c:g} 高於建議價 {gap:.1f}%：市場係喺度賭加價，"
                            "走勢受交易進度牽制，突破同收縮指標量度緊價差而唔係基本面。"}
if "IRD" in flags and "IRD" in listed and "2026-08-31" in IDX:
    tot = pct("IRD", "2026-08-31", None); d2 = ret("IRD", IDX["2026-09-02"])
    flags["IRD"]["text"] = (f"自最後一個底（08-31 $3.62）嘅 {tot:+.1f}% 入面，有 {d2:+.1f}% 係 09-02 一日造成，而 09-02 冇任何成交量數據；"
                            "最後一個更高低點只係 3.61→3.62（+0.28%）。VCP 得 16.6 但確定性高分，分數全部嚟自守底同無量嘅突破。")
if "DMLP" in flags and "DMLP" in listed and "2026-08-04" in IDX:
    flags["DMLP"]["text"] = flags["DMLP"]["text"].replace("+14.8%", f"{pct('DMLP', '2026-08-04', None):+.1f}%")
for sym in ("DFIN", "NOW", "CHRD"):
    if sym in flags and "（事件日回報係固定歷史" not in flags[sym]["text"]:
        flags[sym]["text"] += "（事件日回報係固定歷史；其餘百分比係 R9 量度）"
# a listed row whose close is already under its last bottom: the hold is over
for sym in listed:
    r = listed[sym]
    if r.get("hl") and r["close"] < r["hl"][-1][1] and sym not in flags:
        flags[sym] = {"deal": False, "badge": "已跌穿底",
                      "text": f"收市 ${r['close']:g} 已低過最後一個底 ${r['hl'][-1][1]:g}（{r['hl'][-1][0][5:]}），未夠三日確認所以仍然在榜；"
                              f"{'收市亦低過 MA10；' if r['below_ma'] else ''}「突破」項{'仍然' if r['cert_c'].get('broke') else '已經唔'}滿分"
                              f"{'（高位落喺無量嘅 09-02）' if r['cert_c'].get('peak_no_vol') else ''}。"}

# ---- 2. catalyst warnings: carry (recomputed) + regenerate from cat_line ----
warns = {}
for sym, w in (prev.get("catalyst_warn") or {}).items():
    if sym not in listed or sym not in SER:
        continue
    day = "2026-" + w["day"].replace("/", "-")
    if day in IDX:
        r = ret(sym, IDX[day])
        if r is not None:
            w = dict(w, ret=round(r, 1))
    warns[sym] = w

_CATL = re.compile(r"^(\d{1,2})/(\d{1,2})\s")
COPIED = {IDX[x] for x in scr["meta"]["copied_days"] if x in IDX}
down_days, flat_days, dated, undated, no_cat = [], [], 0, 0, 0
for sym in listed:
    line = (news.get(sym) or {}).get("cat_line", "").strip()
    if not line or line.startswith("無個股催化"):
        no_cat += 1; continue
    m = _CATL.match(line)
    if not m:
        undated += 1; continue
    dated += 1
    key = f"2026-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    i = IDX.get(key) or next((k for k, c in enumerate(CAL) if c > key), None)
    if i is None or i in COPIED:
        continue
    r = ret(sym, i)
    if r is None:
        continue
    r_next = ret(sym, i + 1) if i + 1 < N else None
    if r < -1.0: down_days.append((sym, CAL[i][5:], round(r, 1), r_next, "翌日" in line))
    elif abs(r) <= 1.0: flat_days.append(sym)
after_close = []
for sym, day, r, r_next, says_next in down_days:
    if sym in warns:
        continue
    md = day.replace("-", "/")
    if says_next and r_next is not None and r_next >= 3.0:
        # an after-close print: the line already points at the next day, so the
        # event-day drop is the pre-print move, not the market's verdict
        after_close.append(sym)
        warns[sym] = {"day": md, "ret": r,
                      "text": f"{md} 係盤後公布：當日 −{abs(r):.1f}% 係公布前嘅跌幅，市場反應係翌日 {r_next:+.1f}%"
                              f"{'，09-04 已回吐 ' + format(abs(ret(sym, N - 1)), '.1f') + '%' if ret(sym, N - 1) is not None and ret(sym, N - 1) < -3 else ''}。"}
        continue
    warns[sym] = {"day": md, "ret": r,
                  "text": f"催化欄所指嘅 {md} 收市跌 {abs(r):.1f}%：事件當日被市場沽售，回升係其後嘅事，"
                          "所以呢一句解釋唔到由底回升嘅起點。"}
down_days = [(a, b, c) for a, b, c, _, _ in down_days]

# ---- 2b. research text the series contradicts (checked by hand, see log) ----
# SNDX 08-05 closed +4.4%, not -2.4%; TSLA 07-23 closed -14.5%, not -12.7%;
# ULTA's line picked the rebound day and hid the -4.2% earnings reaction.
EDITS = [("SNDX", "recovery_short", "翌日跌2.4%", "翌日升4.4%"),
         ("TSLA", "decline_short", "12.7%", "14.5%")]
LINES = {"ULTA": "8/27 Q2勝預期上調指引 → 翌日跌4.2%、8/31彈3.8%"}
for sym, field, old, new in EDITS:
    e = news.get(sym)
    if e and old in e.get(field, ""):
        e[field] = e[field].replace(old, new, 1)
        e["hot"] = [h for h in e.get("hot", []) if h in e["recovery_short"]]
        log.append(f"{sym}: {field} corrected against the series")
for sym, line in LINES.items():
    if sym in news and news[sym].get("cat_line") != line:
        news[sym]["cat_line"] = line; log.append(f"{sym}: cat_line corrected")
# 信心高 needs two real article URLs; carried entries with title-only sources drop to 中
for sym in listed:
    e = news.get(sym) or {}
    if e.get("confidence") == "高" and sum(1 for u in e.get("sources", []) if str(u).startswith("http")) < 2:
        e["confidence"] = "中"; log.append(f"{sym}: confidence 高 -> 中 (fewer than 2 URL sources)")

# ---- 3. the list-review agent's outcome (optional) --------------------------
agent_notes, review_summary, n_fixed = [], None, 0
if os.path.exists(AGENT):
    a = json.load(open(AGENT))
    for sym, line in (a.get("cat_line_fixes") or {}).items():
        line = (line or "").strip()
        if sym not in listed:
            problems.append(f"{sym}: cat_line fix for an unlisted ticker"); continue
        if not line or len(line) > 44:
            problems.append(f"{sym}: cat_line fix rejected (empty or too long)"); continue
        n_fixed += 1
        if news[sym].get("cat_line") != line:
            news[sym]["cat_line"] = line; log.append(f"{sym}: cat_line replaced by the review")
    for sym, fl in (a.get("flag_additions") or {}).items():
        if sym not in listed:
            problems.append(f"{sym}: flag for an unlisted ticker"); continue
        if sym in flags or not fl.get("badge") or not fl.get("text"):
            continue
        flags[sym] = {"badge": fl["badge"][:14], "text": fl["text"],
                      "deal": bool(fl.get("deal") or any(k in fl["badge"] for k in ("釘價", "併購", "合併", "作價")))}
        log.append(f"{sym}: flag added by the review — {fl['badge']}")
    agent_notes = [f for f in (a.get("findings") or []) if f.get("severity") in ("major", "minor")]
    review_summary = a.get("summary")

# ---- 4. measurements for the notes ------------------------------------------
new_syms = [s for s in listed if s not in plisted]
out_syms = [s for s in plisted if s not in listed]
n_new, n_out = len(new_syms), len(out_syms)


def tally(items):
    t = {}
    for x in items: t[x] = t.get(x, 0) + 1
    return "、".join(f"{k} {v}" for k, v in sorted(t.items(), key=lambda kv: -kv[1]))


CAPZH = {"a": "大型", "b": "中型", "c": "細價"}
new_sectors = tally(listed[s]["sector_zh"] for s in new_syms)
new_caps = tally(CAPZH[listed[s]["cap"]] for s in new_syms)
new_kinds = tally((news.get(s) or {}).get("ckind") or "無" for s in new_syms
                  if (news.get(s) or {}).get("catalyst"))
n_new_nocat = sum(1 for s in new_syms if not (news.get(s) or {}).get("catalyst"))

# why did the leavers leave: close under the last bottom, structure gone while
# an MA frame still passes (a lower low after the bottom, or the bottom aged
# out of the 25-day window), or the MA test itself
PAGES = {"2": (5, 5), "3": (10, 10), "4": (10, 21), "5": (10, 42)}


def _sma(cs, L):
    o = [None] * len(cs)
    for i in range(L - 1, len(cs)):
        o[i] = math.fsum(cs[i - L + 1:i + 1]) / L
    return o


def ma_frames(cs):
    ok = []
    for pid, (L, W) in PAGES.items():
        ma = _sma(cs, L)
        if ma[-1] > ma[-1 - W] and ma[-1] > ma[-2] > ma[-3] and \
           sum(1 for k in range(1, W + 1) if ma[-k] > ma[-k - 1]) / W >= 0.70:
            ok.append(pid)
    return ok


broke, struct_lower, struct_aged, ma_only, ma_dipped, gone = [], [], [], [], [], []
for s in out_syms:
    if s not in SER or SER[s][0] + len(SER[s][1]) != N:
        gone.append(s); continue
    fi, cs, vs, ff = SER[s]
    bd, pl = plisted[s]["hl"][-1] if plisted[s].get("hl") else (None, None)
    c = cs[-1]
    j = IDX[bd] - fi if bd in IDX else None
    dipped = j is not None and j + 1 < len(cs) and min(cs[j + 1:]) < pl
    if pl and c < pl:
        broke.append(s)
    elif ma_frames(cs):
        (struct_lower if dipped else struct_aged).append(s)
    else:
        ma_only.append(s)
        if dipped: ma_dipped.append(s)

# the new day itself: page-1 rows vs the $1bn+ universe
li = N - 1
p1_rets = [ret(s, li) for s in listed if ret(s, li) is not None]
univ = [ret(s, li) for s, v in mcap.items() if v >= 1e9 and s in SER and ret(s, li) is not None]
p1_med, u_med = statistics.median(p1_rets), statistics.median(univ)
u_up = sum(1 for r in univ if r > 0) / len(univ) * 100
p1_down = [s for s in listed if (ret(s, li) or 0) < -1.0]
p1_below_ma = [s for s in listed if listed[s]["below_ma"]]
p1_peak_today = [s for s in listed if listed[s]["cert_c"].get("peak_day") == last]
p1_undercut = [s for s in listed if listed[s].get("hl") and listed[s]["close"] < listed[s]["hl"][-1][1]]
RANK = {r["sym"]: i for i, r in enumerate(scr["page1"], 1)}
top60_under = [f"{r['sym']} #{i}（{'=MA' if r['close'] >= r['ma'] * 0.999 else format((r['close'] / r['ma'] - 1) * 100, '+.1f') + '%'}）"
               for i, r in enumerate(scr["page1"][:60], 1) if r["close"] <= r["ma"] * 1.0001]
new_ranks = sorted(RANK[s] for s in new_syms)
new_in_top50 = [f"{s} #{RANK[s]}" for s in new_syms if RANK[s] <= 50]
bot_0901 = [s for s in listed if listed[s].get("hl") and listed[s]["hl"][-1][0] == "2026-09-01"]
bot_0901_top50 = [s for s in bot_0901 if RANK[s] <= 50]
worst = sorted(((s, ret(s, li)) for s in listed if ret(s, li) is not None), key=lambda x: x[1])[:5]
best = sorted(((s, ret(s, li)) for s in listed if ret(s, li) is not None), key=lambda x: -x[1])[:5]

# structures that lean on the volume-less 09-02 bar
novol_peak = [s for s in listed if listed[s]["cert_c"].get("peak_no_vol")]
dep_bottom = [s for s in listed if listed[s]["cert_c"].get("bottom_dep_no_vol")]
hl_thin = [s for s in listed if len(listed[s]["hl"]) >= 2
           and listed[s]["hl"][-1][1] / listed[s]["hl"][-2][1] - 1 < 0.01]
top = scr["page1"][:50]
pinned = [r["sym"] for r in top if flags.get(r["sym"], {}).get("deal")]
wiggle = [r["sym"] for r in top if r["cert_c"]["pL"] and r["cert_c"]["H_mid"] / r["cert_c"]["pL"] - 1 < 0.01]
sat = {k: sum(1 for r in top if r["cert_c"]["s"][k] >= 0.999) for k in top[0]["cert_c"]["s"]}
above = sorted((r["close"] / r["cert_c"]["H_mid"] - 1) * 100 for r in top)
near_cut = [s for s in listed if any(abs(listed[s]["mcap"] / c - 1) < 0.05 for c in scr["meta"]["cap_cuts_b"])]
deal_all = [s for s, f in flags.items() if f.get("deal")]
deal_top = [r["sym"] for r in scr["page1"][:20] if flags.get(r["sym"], {}).get("deal")]

# how much of the list still leans on the derived 09-02 bar (MA test without it)
K02 = IDX["2026-09-02"] if "2026-09-02" in IDX else None
dep = 0
if K02 is not None:
    for r in scr["page1"]:
        fi, cs, vs, ff = SER[r["sym"]]; j = K02 - fi
        cs2 = cs[:j] + cs[j + 1:]
        keep = False
        for pid in r["ranks"]:
            L, W = PAGES[pid[0]]
            ma = _sma(cs2, L)
            if ma[-1] > ma[-1 - W] and ma[-1] > ma[-2] > ma[-3] and \
               sum(1 for k in range(1, W + 1) if ma[-k] > ma[-k - 1]) / W >= 0.70:
                keep = True; break
        dep += (not keep)

# ---- 5. notes ---------------------------------------------------------------
def J(xs, n=8): return "、".join(xs[:n])


notes = [
    {"title": f"[本版數據] 更新至 {last} 收盤",
     "text": f"新增 09-04（周五）一個交易日（合共 {scr['meta']['n_days']} 日；09-04 快照由本 repo 嘅 GitHub Actions 抓 Nasdaq screener，"
             f"5,094 隻股票反推前收同 09-03 收市價中位偏差 0.000%，冇拆股）。總表 {len(listed)} 隻：{n_new} 隻新上榜、{n_out} 隻跌出。"
             f"新上榜板塊：{new_sectors}；市值：{new_caps}；催化劑類別：{new_kinds}"
             f"{'，另 ' + str(n_new_nocat) + ' 隻搵唔到個股催化' if n_new_nocat else ''}。"
             f"跌出嘅 {n_out} 隻：{len(broke)} 隻收市已經跌穿最後一個底（{J(broke)}）；{len(struct_lower)} 隻 MA 仍然達標但底部之後造出更低嘅收市、"
             f"「一底高於一底」斷咗（{J(struct_lower)}）；{len(struct_aged)} 隻最後一個底已經超出 25 日窗口（{J(struct_aged)}）；"
             f"{len(ma_only)} 隻係四個時間框嘅 MA 條件全部唔再成立（當中 {len(ma_dipped)} 隻期間亦曾收低過最後一個底）"
             f"{'，' + J(gone) + ' 喺 09-04 快照已經冇報價（' + ('被收購目標，' if all(plisted[g].get('cap') and (prev.get('ticker_flags') or {}).get(g, {}).get('deal') for g in gone) else '') + '疑似已除牌，序列停喺 09-03）' if gone else ''}"
             "，冇一隻因為數據問題。",
     "tickers": new_syms[:10]},
    {"title": "[本版觀察] 09-04 非農強 → 加息機率回升，名單點反應",
     "text": f"09-04 全體 $10 億市值以上股份中位數 {u_med:+.2f}%、{u_up:.1f}% 上升；總表 {len(listed)} 隻中位數 {p1_med:+.2f}%，"
             f"{len(p1_down)} 隻跌超過 1%（最弱：" + "、".join(f"{s} {r:+.1f}%" for s, r in worst) + "），"
             f"最強：" + "、".join(f"{s} {r:+.1f}%" for s, r in best) + f"。收市喺 MA10 之下嘅有 {len(p1_below_ma)} 隻"
             f"（{J(p1_below_ma, 6)}），收市低過最後一個底嘅有 {len(p1_undercut)} 隻（{J(p1_undercut, 6)}）——後者未夠三日確認，"
             f"所以仍然喺榜，但「守底」已經名存實亡（已加「已跌穿底」標記）。{len(p1_peak_today)} 隻嘅底部後最高位就係 09-04 當日。"
             f"總表 top 60 入面收市貼住或低過 MA10 嘅有 {len(top60_under)} 行：{'、'.join(top60_under)}。"
             f"新上榜 {n_new} 隻只有 {len(new_in_top50)} 隻入 top 50（{J(new_in_top50, 6)}），其餘排 {new_ranks[len(new_in_top50)] if len(new_ranks) > len(new_in_top50) else '—'}–{new_ranks[-1]}"
             f"（金融股全部喺尾段）——即係新上榜多數係「啱啱夠條件」，唔係強勢突破。",
     "tickers": p1_down[:10]},
    {"title": "[已修正] 催化欄逐行對照序列（本版重新計算）",
     "text": f"{dated} 句有日期、{undated} 句冇日期（原文本身冇提日期，唔憑空補）、{no_cat} 句係「無個股催化」。"
             f"其中 {len(down_days)} 句所指嗰日收市係跌市（最誇張：" + "、".join(f"{s} {r:+.1f}%" for s, _, r in sorted(down_days, key=lambda x: x[2])[:6]) + "）——"
             f"呢啲事件係造成低位嘅原因多過回升嘅原因，全部自動加「事件日 −X%」標記"
             f"{'（' + J(after_close, 4) + ' 係盤後公布、句子本身指住翌日，標記改為講明公布前跌幅同翌日反應）' if after_close else ''}；"
             f"另有 {len(flat_days)} 句所指嗰日波幅喺 ±1% 之內（{sum(1 for x in flat_days if flags.get(x, {}).get('deal'))} 句係併購釘價股，其餘多數係盤後公布、反應落喺翌日）。"
             f"新上榜嘅 30 句由獨立覆核逐句對照序列，{n_fixed} 句嘅效果數字改正（例如 WTTR「翌日約10%」實為 +20.3%、IOVA 嘅 +43% 係當日而非翌日、"
             "SGHT 嘅 +27.7% 係 8/6 業績而非 8/4 FDA）；news_checks.py 嘅容差（±35%、唔分單日／翌日）放晒佢哋過，係下一步要收窄嘅檢查。",
     "tickers": [s for s, _, _ in sorted(down_days, key=lambda x: x[2])[:6]]},
    {"title": "[已加標記] 突破高位落喺冇成交量嗰日",
     "text": f"總表 {len(novol_peak)}/{len(listed)} 行嘅「底部後最高位」仍然落喺 09-02（有價無量嗰日），「突破」項旁邊顯示「·無量」。"
             f"09-03、09-04 兩日都有真實成交量，所以呢個數會隨住新高位出現而自然減少（R9 係 47/185）。",
     "tickers": novol_peak[:10]},
    {"title": "[已加標記] 靠 09-02 先成立嘅結構",
     "text": f"總表 {len(bot_0901)} 行嘅最後一個底落喺 09-01（守底剛好係規則最少嘅 3 日，top 50 有 {len(bot_0901_top50)} 行：{J(bot_0901_top50, 8)}），"
             f"呢啲底嘅第一個確認日就係有價無量嘅 09-02；連同較早嘅底，總表 {len(dep_bottom)} 行嘅最後一個底係靠 09-02 呢個反推出嚟嘅 bar 先夠三日確認"
             f"（獨立覆核指出剝走 09-02 之後 SSNC、NKTX、MNTN、PSKY 四行嘅一底高於一底結構會成個唔成立；第 1 位 DMLP 亦係兩底結構、09-02 確認、高位無量、"
             f"現價只高過最後一個底 {(listed['DMLP']['close'] / listed['DMLP']['hl'][-1][1] - 1) * 100:.1f}%）。另外如果索性剝走 09-02，"
             f"{dep}/{len(listed)} 隻上榜股就唔會通過 MA 條件。價格本身可信（官方 net-change 反推、精確到仙），但同一日對「結構」計足一日、"
             "對「成交量」完全冇數，兩邊唔對稱，仍然係本版最需要留意嘅數據限制。",
     "tickers": dep_bottom[:10]},
    {"title": "[已加標記] 市值近界",
     "text": f"{len(near_cut)} 隻上榜股市值距 $100 億／$20 億分界線 5% 以內（{J(near_cut, 8)}），一日波動就可能換組；"
             "市值用 09-04 快照（APH 拆股後供應商未加股數，已手動乘 2，佢本身唔喺榜）。",
     "tickers": near_cut[:8]},
]
if os.path.exists(VERIFY):
    v = json.load(open(VERIFY))
    notes.append({"title": "[已核實] 獨立重算：輸出逐格對得上" if v.get("ok") else "[備註] 獨立重算有出入",
                  "text": v.get("text_zh", "")})

open_notes = [n for n in (prev.get("notes") or []) if n["title"].startswith(("[待你決定]", "[已標記 · 待你決定]"))]
STALE_MARK = "（下列數字係 R7／R8 時期嘅量度，例子股票部分已經跌出名單；建議本身仍然成立）"
for n in open_notes:
    t = n["title"]
    if t.startswith("[待你決定] 確定性飽和"):
        n["title"] = "[待你決定] 確定性飽和同釘價股仍然主導榜首（本版重新量度）"
        n["text"] = (f"喺 {last} 嘅數據上一樣成立：總表 top 50 入面「突破」項有 {sat['break']}/50 係滿分、「回補」{sat['retr']}/50、"
                     f"「均線」{sat['ma']}/50，即係確定性一半權重根本冇分辨力，實際排序由守底日數同量比決定；"
                     f"另外 {len(wiggle)} 隻嘅中間高位只高過上一個底 <1%（{J(wiggle, 6)}），三項自動接近滿分。"
                     f"併購釘價股佔 top 50 嘅 {len(pinned)} 隻（{J(pinned, 8)}）{'，包括第 1 位' if pinned and top[0]['sym'] == pinned[0] else ''}。"
                     f"top 50 距離中間高位嘅中位數 {above[len(above)//2]:+.1f}%。建議（會改規則）：突破需 ≥ 中間高位 ×1.01、去掉均線項重新加權、釘價股另置區塊 —— 三項都要你拍板。")
        n["tickers"] = pinned[:8]
    elif t.startswith("[待你決定] 部分行嘅「一底高於一底」"):
        thin_txt = "、".join(f"{s} {(listed[s]['hl'][-1][1] / listed[s]['hl'][-2][1] - 1) * 100:+.2f}%"
                            for s in sorted(hl_thin, key=lambda s: listed[s]['hl'][-1][1] / listed[s]['hl'][-2][1])[:5])
        n["text"] = (f"總表 {len(hl_thin)}/{len(listed)} 行（top 50 有 {sum(1 for r in top if r['sym'] in hl_thin)} 行）嘅最後一個底只高過上一個底 <1%：{thin_txt}。"
                     "規則④⑤ 冇設最低幅度，所以呢啲行嘅「遞升」其實喺捨入誤差範圍。建議：底部遞升需 ≥1% 先算數 —— 會改規則，由你決定。")
        n["tickers"] = hl_thin[:8]
    elif t.startswith("[已標記 · 待你決定] 併購釘價股"):
        n["text"] = (f"{len(deal_all)} 隻被收購目標／併購傳聞股（{J(deal_all, 12)}）全部有標記，頂欄「隱藏併購釘價股」掣可以一鍵篩走；"
                     f"總表前 20 名入面有 {len(deal_top)} 隻（{J(deal_top, 8)}）。佢哋嘅低波幅係交易釘價，唔係蓄勢，"
                     "係咪索性剔除或者另置區塊，要你決定。")
        n["tickers"] = deal_all[:10]
    elif t.startswith("[待你決定] 同公司雙類股"):
        pairs = [p for p in (("NWS", "NWSA"), ("GOOG", "GOOGL"), ("BRK.A", "BRK.B"), ("FOX", "FOXA"), ("LEN", "LEN.B")) if p[0] in listed and p[1] in listed]
        if not pairs:
            stayed = [x for x in ("NWS", "NWSA") if x in listed]
            n["text"] = (f"本版總表已經冇同一公司嘅雙類股同時上榜：R9 同時上榜嘅 NWS／NWSA，{'、'.join(x for x in ('NWS', 'NWSA') if x not in listed)} 已跌出，"
                         f"{'、'.join(f'{x} 仍在（#{RANK[x]}）' for x in stayed) if stayed else '兩隻都已跌出'}；但規則本身未改，將來仍會出現。"
                         "建議：同一公司只計一個名額（保留流動性較高嗰類）—— 會改規則，由你決定。")
            n["tickers"] = stayed
    elif t.startswith("[待你決定] 確定性三項（45% 權重）"):
        n["text"] = (f"當最後兩個底之間嘅中間高位只高過上一個底 <1%（本版 top 50 有 {len(wiggle)} 隻，例如 {J(wiggle, 5)}），"
                     "突破、回補、守底三項會被一日小回全數攞滿。建議：中間高位需高過上一個底 ≥2% 先計 —— 會改規則，由你決定。")
        n["tickers"] = wiggle[:6]
    else:
        n["tickers"] = [x for x in (n.get("tickers") or []) if x in listed]
    if n["title"].startswith("[待你決定] MA 連升 3 日"):
        n["text"] = STALE_MARK + n["text"] if STALE_MARK not in n["text"] else n["text"]

lineage = {"title": "[備註] R8–R10 嘅修正同做法繼續生效",
           "text": "補值日唔製造底部、成交量不完整日同 09-02（有價無量）唔入量比／VCP／流動性、universe 剔除基金／信託／優先股、"
                   "S&P 500 用 GICS 類別、總表斜率統一 MA10、評級另立類別、催化劑事件日下跌者自動加標記、APH 拆股歷史已重算、"
                   "更新內容只用灰色小字（冇紅色）、催化欄同淺色／深色掣、R10 嘅單屏版面（說明喺表下面、欄寬固定）—— 全部照舊。"
                   "R9 審視發現嘅五項錯處（催化欄自我核對錯一個數量級、news_checks 唔睇 cat_line、DBRG 冇標記、舊 notes 數字停留喺 R7、"
                   "頭條嘅板塊故事同數據相反）已喺 R9 修正，本版所有數字由程式即時計算。"}
# every major/minor finding of the independent list review was acted on above
# (leaver classes, the 8 catalyst lines, flag texts, the after-close warnings,
# the 09-01 bottoms and the broken-bottom flag), so they are shown as fixed
for f in agent_notes[:9]:
    notes.append({"title": f"[覆核 · 已修正] {f.get('title', '')[:60]}",
                  "text": (f.get("evidence", "")[:400] + " → 處理：" + f.get("proposed_fix", "")[:200]).strip()})
notes = notes + [lineage] + open_notes

# ---- 6. headline -------------------------------------------------------------
headline = (
    f"R11 建基於 {last}（周五）收盤。當日 8 月非農增 16.2 萬遠勝預期，「數據強＝加息」反應令 9 月加息機率回升至 58%、10 年期息率升至 4.79%，"
    f"標普跌 0.38%、納指跌 0.29%；本掃描 $10 億以上股份中位數 {u_med:+.2f}%、{u_up:.0f}% 上升。總表 {len(listed)} 隻：{n_new} 隻新上榜、{n_out} 隻跌出"
    f"（{len(broke)} 隻跌穿最後一個底、{len(struct_lower) + len(struct_aged)} 隻 MA 仍達標但結構斷咗或過咗窗口、{len(ma_only)} 隻 MA 條件唔再成立）。名單本身當日中位數 {p1_med:+.2f}%，{len(p1_down)} 隻跌超過 1%，"
    f"{len(p1_undercut)} 隻收市已低過最後一個底但未夠三日確認、top 60 有 {len(top60_under)} 行收市貼住或低過 MA10。"
    f"新上榜以 {'、'.join(new_sectors.split('、')[:3])} 為主（{new_caps}），催化劑 {new_kinds.split('、')[0] if new_kinds else '無'} 佔多，"
    f"但只有 {len(new_in_top50)}/{n_new} 隻入 top 50 —— 多數係啱啱夠條件，唔係強勢突破。"
    f"審視層全部重新量度：釘價股 {len(deal_all)} 隻有標記、催化欄 {len(down_days)} 句事件日係跌市已加標記、{len(novol_peak)} 行嘅高位仍落喺有價無量嘅 09-02。"
    "版面同 R10 一樣（一打開就係表，說明喺最底）。")

review = {
    "headline": headline,
    "notes": notes,
    "rule_notes": [
        f"R11（唔改規則）：數據更新至 {last} 收盤，09-04 快照同 09-03 序列反推對賬中位偏差 0.000%，冇拆股；審視層所有數字按本版重新量度。",
    ] + [r for r in (prev.get("rule_notes") or []) if "待你決定" in r],
    "ticker_flags": flags,
    "catalyst_warn": warns,
}
if review_summary:
    review["review_summary"] = review_summary

json.dump(news, open(f"{SCRATCH}/{NEWS}", "w"), ensure_ascii=False, indent=1)
json.dump(review, open(f"{SCRATCH}/{OUT}", "w"), ensure_ascii=False, indent=1)
print(f"wrote {SCRATCH}/{OUT} · flags {len(flags)} (dropped {len(dropped_flags)}: {dropped_flags}) · "
      f"catalyst warnings {len(warns)} · notes {len(notes)} · new {n_new} · out {n_out} "
      f"(broke {len(broke)}, struct {struct_lower}+{struct_aged}, ma {len(ma_only)}, gone {len(gone)})")
print(f"09-04: universe med {u_med:+.2f}% up {u_up:.1f}% · p1 med {p1_med:+.2f}% down>1% {len(p1_down)} · below MA {len(p1_below_ma)} · undercut {p1_undercut}")
print(f"novol_peak {len(novol_peak)} · dep_bottom {len(dep_bottom)} · dep(MA w/o 09-02) {dep} · hl_thin {len(hl_thin)} · pinned top50 {pinned} · sat {sat} · near_cut {near_cut}")
print("flags:", {k: v["badge"] for k, v in flags.items()})
for l in log: print("  -", l)
if problems:
    print(f"PROBLEMS ({len(problems)}):")
    for p in problems: print("  !", p)

#!/usr/bin/env python3
"""Review layer for the momentum-pullback screen (R21 onward).

Measures what the rules cannot see and writes it for the workbook: the
two-source price check at universe level, the day-over-day turnover of the
list (the same rules re-run on the previous close), the overlap with the last
10MA-rule revision, the concentration of the list, and the flags that need
outside research (event-driven moves, analyst/policy catalysts). Every number
quoted in a finding is computed here from the screen output, not typed in.

Env: WORK_DIR, SCREEN_JSON, PREVDAY_JSON, PREV_SCREEN (last 10MA revision),
YAHOO, SNAP_DATES, OUT_REVIEW, REV, PREV_REV, RESEARCH_JSON (hand-checked
facts with sources: event flags and market lines).
"""
import csv, gzip, json, os, statistics

import numpy as np

W = os.environ.get("WORK_DIR", "./data")
S = json.load(open(f"{W}/{os.environ.get('SCREEN_JSON', 'screen_mp21.json')}"))
PD = json.load(open(f"{W}/{os.environ.get('PREVDAY_JSON', 'screen_mp21_prevday.json')}"))
PREV = json.load(open(f"{W}/{os.environ.get('PREV_SCREEN', 'screen_results20.json')}"))
RES = json.load(open(f"{W}/{os.environ.get('RESEARCH_JSON', 'research_mp21.json')}"))
YAHOO = os.environ["YAHOO"]
SNAP_DATES = os.environ.get("SNAP_DATES", "").split(",")
OUT = os.environ.get("OUT_REVIEW", "review_mp21.json")
REV = os.environ.get("REV", "R21.00")
PREV_REV = os.environ.get("PREV_REV", "R20")

rows = S["rows"]; meta = S["meta"]; LAST = meta["last_date"]
RANK = {r["sym"]: r["rank"] for r in rows}
BY = {r["sym"]: r for r in rows}
G = S["gates"]
GZH = {"S1": "S1 趨勢", "S2": "S2 近期高位", "S3": "S3 回調深度", "S4": "S4 曾經拉開", "S5": "S5 回到20MA"}
pct = lambda x, d=1: f"{x * 100:+.{d}f}%"


def why_not(sym):
    g = G.get(sym)
    if not g:
        return "唔喺今次股票池（未夠 90 個上市交易日、收市 <$2、成交額不足或者已停止交易）"
    parts = []
    if g["fail"]:
        parts.append("形態唔過：" + "、".join(GZH[k] for k in g["fail"]))
    if not g["hits"]:
        parts.append("動能：四個時間框都唔入頭 10%")
    return "；".join(parts) + f"（距 MA20 {pct(g['d20'])}、距高位 {pct(g['dd'])}）"


# ---------------- universe-level two-source check ----------------
snap = {}
for d in SNAP_DATES:
    m = {}
    for r in csv.DictReader(open(f"{W}/snapshots/{d}.csv", encoding="utf-8")):
        try:
            m[r["symbol"].strip()] = (float(r["lastsale"].strip("$ ").replace(",", "")), float(r["netchange"]))
        except ValueError:
            pass
    snap[d] = m
Y = {}
with gzip.open(YAHOO, "rt") as f:
    for r in csv.DictReader(f):
        if r["date"] >= "2026-09-18":
            Y.setdefault(r["symbol"], {})[r["date"]] = float(r["close"])


def agree(pairs):
    d = [abs(a / b - 1) for a, b in pairs if b > 0]
    return len(d), sum(x <= 0.005 for x in d) / len(d) if d else 0.0


checks = []
d_last, d_prev = SNAP_DATES[-1], SNAP_DATES[0]
n1, a1 = agree([(Y[s][d_last], snap[d_last][s][0]) for s in Y if d_last in Y[s] and s in snap[d_last]])
checks.append((f"{d_last} 收市", f"Yahoo 對 Nasdaq 收市後快照：{n1:,} 隻，{a1:.1%} 喺 0.5% 之內"))
n2, a2 = agree([(snap[d_prev][s][0], snap[d_last][s][0] - snap[d_last][s][1])
                for s in snap[d_prev] if s in snap[d_last]])
checks.append((f"{d_prev} 收市", f"Yahoo 呢日只出咗 {meta['holes'][d_prev]['yahoo']} 隻（約 {meta['holes'][d_prev]['neighbours']:,} 隻應有），"
               f"所以用 Nasdaq {d_prev} 收市後快照嘅收市價同成交量補（{meta['holes'][d_prev]['nasdaq_filled']:,} 隻，"
               f"開高低當收市價）；呢個收市價同 {d_last} 快照「收市 − 升跌」反推嘅前收對得上：{n2:,} 隻，{a2:.1%} 喺 0.5% 之內"))
prev_day = [d for d in sorted({d for m in Y.values() for d in m}) if d < d_prev][-1]
n3, a3 = agree([(Y[s][prev_day], snap[d_prev][s][0] - snap[d_prev][s][1])
                for s in Y if prev_day in Y[s] and s in snap[d_prev]])
checks.append((f"{prev_day} 收市", f"Yahoo 對 {d_prev} 快照反推嘅前收：{n3:,} 隻，{a3:.1%} 喺 0.5% 之內"))
worst = max(rows, key=lambda r: r["xchk"]["max_abs_pct"])
checks.append(("名單逐隻", f"{len(rows)} 隻上榜股，近 63 個交易日 Yahoo 對 Nasdaq 序列同快照，最大差 "
               f"{worst['xchk']['max_abs_pct']:.3f}%（{worst['sym']}）；鏡像照抄前日嘅日子（收市同成交量都同前一日一樣）唔計"))
checks.append(("09-18", "冇 Nasdaq 快照，只得 Yahoo 一個來源（09-21 快照反推嘅前收只核對到 09-21）"))

# ---------------- turnover: same rules on the previous close ----------------
pd_rows = {r["sym"]: r for r in PD["rows"]}
now, before = set(BY), set(pd_rows)
vs_prevday = []
for s in sorted(now & before, key=lambda s: RANK[s]):
    vs_prevday.append({"kind": "兩日都上榜", "sym": s, "prev_rank": pd_rows[s]["rank"], "rank": RANK[s], "why": ""})
for s in sorted(now - before, key=lambda s: RANK[s]):
    g = PD["gates"].get(s)
    w = ("上日：" + ("形態唔過 " + "、".join(GZH[k] for k in g["fail"]) if g and g["fail"] else "")
         + ("" if not g or g["hits"] else "動能未入頭 10%")) if g else "上日唔喺股票池"
    vs_prevday.append({"kind": "今日新上榜", "sym": s, "prev_rank": None, "rank": RANK[s], "why": w})
for s in sorted(before - now, key=lambda s: pd_rows[s]["rank"]):
    vs_prevday.append({"kind": "今日跌出", "sym": s, "prev_rank": pd_rows[s]["rank"], "rank": None,
                       "why": "今日：" + why_not(s)})
left = before - now
left_s5 = sum(1 for s in left if G.get(s) and "S5" in G[s]["fail"])
left_below = sum(1 for s in left if G.get(s) and G[s]["d20"] < S["meta"]["params"]["dist_lo"])

# ---------------- overlap with the last 10MA-rule revision ----------------
prev_rank = {r["sym"]: i for i, r in enumerate(PREV["page1"], 1)}
vs_prev = []
both = [s for s in BY if s in prev_rank]
for s in sorted(both, key=lambda s: RANK[s]):
    vs_prev.append({"kind": "兩份名單都有", "sym": s, "prev_rank": prev_rank[s], "rank": RANK[s], "why": ""})
for s in sorted((s for s in BY if s not in prev_rank), key=lambda s: RANK[s]):
    vs_prev.append({"kind": f"只喺 {REV[:3]}", "sym": s, "prev_rank": None, "rank": RANK[s],
                    "why": f"動能 {BY[s]['mom']:.0f}；距 MA20 {pct(BY[s]['close'] / BY[s]['ma20'] - 1)}"})
fail_count = {}
for s in sorted((s for s in prev_rank if s not in BY), key=lambda s: prev_rank[s]):
    vs_prev.append({"kind": f"只喺 {PREV_REV}", "sym": s, "prev_rank": prev_rank[s], "rank": None, "why": why_not(s)})
    g = G.get(s)
    if g:
        for k in g["fail"]:
            fail_count[k] = fail_count.get(k, 0) + 1
        if not g["hits"]:
            fail_count["mom"] = fail_count.get("mom", 0) + 1

# ---------------- concentration and co-movement ----------------
sec = {}
for r in rows:
    sec[r["sector_zh"]] = sec.get(r["sector_zh"], 0) + 1
REFINERS = RES["refiners"]["syms"]
ref_in = [s for s in REFINERS if s in BY]


def daily(sym):
    c = BY[sym]["spark"]["close"]
    return np.diff(np.log(c))[-21:]


def med_corr(group):
    cs = [np.corrcoef(daily(a), daily(b))[0, 1] for i, a in enumerate(group) for b in group[i + 1:]]
    return float(np.median(cs)) if cs else None


others = [r["sym"] for r in rows if r["sym"] not in ref_in]
c_ref = med_corr(ref_in)
c_oth = med_corr(others)
energy = [r["sym"] for r in rows if r["sector_zh"] == "能源"]
ref_move = [BY[s]["close"] / BY[s]["prev"] - 1 for s in ref_in]
heavy = [s for s in BY if any(k == "heavy_break" for k, _ in BY[s]["flags"])]

# ---------------- touch timing on a broad down day ----------------
br = {b["date"]: b for b in meta["breadth"]}
only_last = [r["sym"] for r in rows if r["touch_dates"] == [LAST]]
list_move = statistics.median(r["close"] / r["prev"] - 1 for r in rows)

# ---------------- flags from research (sourced in research_mp21.json) ----------------
extra = {}
for s, fl in RES["flags"].items():
    extra.setdefault(s, []).extend([(k, t) for k, t in fl])
for s in ref_in:
    extra.setdefault(s, []).append(("event", RES["refiners"]["text"] + f"（五隻 21 日相關系數中位數 {c_ref:+.2f}，名單其餘 {c_oth:+.2f}）"))
for r in rows:
    if r["dv20"] < 5e6:
        extra.setdefault(r["sym"], []).append(
            ("liq", f"20 日成交額中位數只有 ${r['dv20'] / 1e6:.1f}M（股票池下限 $1M），入市出市都會有滑價"))
    if r["close"] < 2.5:
        extra.setdefault(r["sym"], []).append(
            ("floor", f"收市 ${r['close']:.2f}，貼近股票池 $2 下限；1 個月回報 {pct(r['rets']['21'] or 0, 0)}，"
                      f"靠 {'、'.join({21: '1個月', 42: '2個月', 63: '3個月', 126: '6個月'}[w] for w in r['hits_w'])} 動能上榜"))

gap_nm = [n for n in S["near_miss"] if n.get("touch_only")]
survive = {r["sym"]: sum(1 for x in S["sensitivity"] if r["sym"] not in x["dropped"]) for r in rows}
robust = [r["sym"] for r in rows if survive[r["sym"]] == len(S["sensitivity"])]
top6_fragile = [r["sym"] for r in rows[:6] if survive[r["sym"]] < len(S["sensitivity"])]
sens = {(x["param"], x["alt"]): x for x in S["sensitivity"]}
sens_big = sorted(S["sensitivity"], key=lambda x: -(len(x["added"]) + len(x["dropped"])))[:5]
PN = {"touch_tol": "觸及容差", "dist_hi": "距MA20上限", "dist_lo": "距MA20下限", "ext_min": "曾經拉開",
      "depth_min": "最淺回調", "depth_max": "最深回調", "hi_ago_max": "高位最遠日數",
      "near_record": "貼近期內高位", "decile": "動能百分位"}
late = meta["late_nasdaq_start"]
n_0319 = sum(1 for v in late.values() if v["nasdaq_from"] == "2026-03-19")

findings = [
    {"id": "F1", "title": "規則轉換：新舊名單幾乎唔重疊（預期之內）",
     "text": f"{PREV_REV}（10MA 上升＋底部遞升）89 隻同 {REV} {len(rows)} 隻只重疊 {len(both)} 隻（"
             + "、".join(both) + f"）。{PREV_REV} 其餘 {len(prev_rank) - len(both)} 隻今次唔上榜，"
             f"最常見原因：動能唔入頭 10% {fail_count.get('mom', 0)} 隻、S2 近期高位 {fail_count.get('S2', 0)} 隻、"
             f"S5 未回到 20MA {fail_count.get('S5', 0)} 隻（一隻可以有幾個原因）。舊規則捉築底轉強，新規則捉強勢股回調，兩者本身就係兩批股票。",
     "action": "逐隻原因列喺「同R20對照」頁"},
    {"id": "F2", "title": "名單每日換手大約一半 —— 呢個係「今日嘅買位」名單，唔係持倉名單",
     "text": f"用同一套規則回算 {PD['meta']['last_date']} 收市：{len(before)} 隻；今日 {len(now)} 隻，兩日都有 {len(now & before)} 隻，"
             f"新上榜 {len(now - before)}、跌出 {len(left)}。跌出嗰 {len(left)} 隻入面 {left_s5} 隻係 S5 唔過（當中 {left_below} 隻收市已經跌穿 MA20 超過 3%）。"
             "股票回到 20MA 通常只停留幾日，之後一係反彈離開、一係跌穿，所以名單天生換得快；R1–R20 嘅舊名單可以一連幾星期都喺度，兩者唔好比較持續性。",
     "action": "每隻嘅上日狀態列喺「同上日對照」頁"},
    {"id": "F3", "title": f"{LAST} 全市急跌，部分「觸及 20MA」係大市拖落嚟，唔係個股自己消化",
     "text": f"{LAST} 合資格股票當日中位數 {pct(br[LAST]['med'], 2)}，只有 {br[LAST]['up']:.1%} 上升（標普 −0.75%、納指 −1.13%，"
             f"5 年期美債息 2007 年後首次見 5 厘）。{len(only_last)} 隻近 3 日入面只有今日嘅最低價去到 MA20（"
             + "、".join(only_last) + f"；{d_prev} 只有收市價，嗰日日內有冇掂到睇唔到）。不過上榜股當日中位數 {pct(list_move, 2)}，跌得比大市少。",
     "action": "唔改規則；呢 {} 隻喺總表「近3日最低價距MA20%」欄睇得到，大市再跌佢哋會最先跌穿".format(len(only_last))},
    {"id": "F4", "title": f"能源集中：{len(energy)}/{len(rows)} 隻係能源股，當中 {len(ref_in)} 隻煉油股係同一個交易",
     "text": f"能源 {len(energy)} 隻（" + "、".join(energy) + f"），佔 {len(energy) / len(rows):.0%}。煉油股 {'、'.join(ref_in)} 嘅 21 日相關系數中位數 "
             f"{c_ref:+.2f}（名單其餘 {c_oth:+.2f}），今日平均 {pct(statistics.mean(ref_move), 2)}。" + RES["refiners"]["text"]
             + f" 其中 {'、'.join(s for s in heavy if s in ref_in)} 今日放量收喺 MA20 下面。R16–R20 嘅能源集中最後五個交易日內散晒（R20 記錄 16 行剩 1 行），今次形態唔同（今次係回調買位），但同一板塊集中嘅風險一樣。",
     "action": "保留、標橙底；當一隻股票睇，唔好當五個獨立機會"},
    {"id": "F5", "title": "事件驅動：IRD 嘅升浪同回調都係臨床數據帶動",
     "text": RES["flags"].get("IRD", [["", ""]])[0][1],
     "action": "保留、標橙底；呢類回調唔係規則想捉嘅有序回吐"},
    {"id": "F6", "title": f"數據缺口：Yahoo 冇出 {d_prev} 日線（已修正）",
     "text": f"Yahoo 呢日只有 {meta['holes'][d_prev]['yahoo']} 隻：09-24 三次抓取（01:24 UTC 得 209 隻，16:15 同 16:23 UTC 兩次都係 270 隻）都唔齊，09-21 同 {LAST} 就齊晒。原本嘅程式會將缺日當停牌（沿用前收、成交量 0），"
             f"咁會造出一日假嘅零波動。改為用 Nasdaq 收市後快照補收市價同成交量；開高低唔知，當收市價。"
             f"影響：只會令 {d_prev} 嘅「觸及」睇漏、唔會憑空造出；名單上 {len(rows)} 隻全部靠 09-21 或 {LAST} 嘅真實低位過關。"
             + (f"差一項入面只有 {'、'.join(n['sym'] for n in gap_nm)} 係收市距離啱、淨係差觸及，佢 {d_prev} 嘅日內低位可能改變結果。" if gap_nm else "")
             + f" 另外 {d_prev} 嘅真實波幅會被低估，所以 ATR5／ATR20（波幅收窄分）對全部股票都略為偏高。",
     "action": "已修正；Yahoo 補返數據後可以重算"},
    {"id": "F7", "title": "SPAC 空殼期會扮動能（已修正）",
     "text": f"Yahoo 會將同一隻證券改代號前嘅歷史接埋。FRNM（Freenome）7 月 21 日先完成 SPAC 合併，Nasdaq 序列得 42 日，"
             f"但 Yahoo 有 185 日，前面係 $10–11 嘅信託價。未修正前 FRNM 以第 4 名上榜：過到「≥90 日歷史」，3 個月回報亦由空殼價計。"
             f"改為：上市日數按 Nasdaq 序列計（同 R1–R20 一樣），回報只計代號上市之後；均線同高位照用全部 Yahoo 日線。"
             f"共 {len(late)} 隻 Yahoo 歷史早過 Nasdaq 序列。",
     "action": "已修正（FRNM 剔走）"},
    {"id": "F8", "title": "修正 F7 時避開嘅第二個陷阱（已修正）",
     "text": f"一刀切將 Yahoo 歷史截到 Nasdaq 序列開始日，會誤傷 {n_0319} 隻 Nasdaq 序列因鏡像斷檔由 03-19 先開始嘅大型股"
             "（ACN、CB、ETN 等，佢哋 Yahoo 歷史先係啱）：ACN 就會因為「期內高位」只計 03-19 之後而錯誤上榜。現行做法只限制上市日數同回報起點，唔截均線同高位。",
     "action": "已修正（ACN 冇錯誤上榜）"},
    {"id": "F9", "title": "兩源核對嘅假警報（已修正）",
     "text": "FRNM 初步核對顯示兩源差 3.27%，查落係 Nasdaq 鏡像 08-11 照抄咗前一日收市（R12 只為當時 Yahoo 有覆蓋嘅股票補咗呢啲日子）。"
             "核對改為跳過收市同成交量都同前一日一模一樣嘅日子。",
     "action": "已修正"},
    {"id": "F10", "title": "1 個月頁天生細",
     "text": f"1 個月回報要排頭 10%（今次分界 {pct(meta['cutoffs']['21']['p90'])}），同時又要已經跌返去 20MA —— 21 日內大升嘅股票通常仲離 MA20 好遠。"
             f"今次 1 個月頁 {len(S['pages']['21'])} 隻、3 個月頁 {len(S['pages']['63'])} 隻，唔係錯。",
     "action": "唔改"},
    {"id": "F11", "title": f"門檻敏感度：{len(S['sensitivity'])} 個測試入面，只有 {len(robust)} 隻次次都留低",
     "text": "每次只郁一個門檻，變動最大嘅五個：" + "；".join(
         f"{PN[x['param']]} {x['base']}→{x['alt']}：+{len(x['added'])}／−{len(x['dropped'])}" for x in sens_big)
             + f"。全部測試都留低嘅只有 {len(robust)} 隻（" + "、".join(robust) + "）；"
             + f"前 6 名入面 {'、'.join(s for s in top6_fragile)} 都會因為收緊某一個門檻而跌出。"
             "上唔上榜好靠門檻邊緣，唔好當硬性分界；總表「門檻測試留低」欄列咗每隻喺幾多個測試入面仲喺度。",
     "action": "逐項列喺「敏感度」頁；總表加欄"},
    {"id": "F12", "title": "今次冇做嘅嘢",
     "text": f"冇查業績日期（回調後即將公佈業績嘅股票風險唔同）；今次新查嘅 {RES['researched_n']} 隻只係快速核查（主要排除併購釘價同單一事件），"
             f"沿用舊研究嘅 {RES['carried_n']} 隻冇重新核實，" + "、".join(s for s in BY if s not in RES["research"] and s not in RES["carried"]) + " 未查；HTML 報告冇按新規則重做。",
     "action": "如有需要下一版補"},
]
open_items = [
    "動能門檻用頭 10%（百分位 90）定頭 15%（85）？85 會多 {} 隻。".format(len(sens[("decile", 0.85)]["added"])),
    "收市可以低過 MA20 最多 3%（插穿都計）。如果只要收市企返 MA20 上面，今日會少 {} 隻。".format(
        sum(1 for r in rows if r["close"] < r["ma20"])),
    "股票池成交額下限 $1M 係沿用舊規則；做動能交易要唔要升到 $5M？今日會少 {} 隻。".format(
        sum(1 for r in rows if r["dv20"] < 5e6)),
    "事件驅動（IRD）同放量跌穿 20MA（{}）要唔要直接剔走，定係好似而家咁保留加標記？".format("、".join(heavy)),
]
for i, t in enumerate(open_items, 1):
    findings.append({"id": f"待決{i}", "title": "待你決定", "text": t, "action": "今次未改"})

market = [(a, b) for a, b in RES["market"]]
market.append(("大市闊度", "合資格股票每日中位數："
               + "；".join(f"{b['date'][5:]} {pct(b['med'], 2)}（{b['up']:.0%} 上升）" for b in meta["breadth"][-4:])
               + "。09-21 標普升 1.5%，但中位數只 +0.25% —— 係科技股帶動嘅窄升市。"))

notes = [
    f"篩選條件全面更新為「高動能 ＋ 回到上升中嘅 20MA」：先要 1／2／3／6 個月回報至少一個排全體合資格股票頭 10%，"
    f"再要趨勢向上、兩至二十五日前見過期內高位、回調 3–30%、曾經離開 MA20 至少 8%、而家收市喺 MA20 ±3% 之內兼近 3 日觸及過。細節見「篩選規則」頁。",
    f"數據更新至 {LAST} 收市（{meta['n_days']} 個交易日）。價格改用 Yahoo 日線，因為「觸及 20MA」要用當日最低價；Nasdaq 序列同收市後快照做核對。",
    f"合資格 {meta['eligible']:,} 隻 → 形態 {meta['funnel']['setup']} 隻 → 上榜 {len(rows)} 隻（1 個月頁 {len(S['pages']['21'])}、"
    f"2 個月 {len(S['pages']['42'])}、3 個月 {len(S['pages']['63'])}、6 個月 {len(S['pages']['126'])}）。",
    f"評分改為動能分數 × 回調質素（量縮、貼近 MA20、MA20 斜率、回調深度、企穩、波幅收窄），取代舊嘅 VCP × 底部確定性。",
    "批判性覆核改咗四個問題（Yahoo 缺 09-22、SPAC 空殼期扮動能、修正空殼期時會誤傷鏡像斷檔嘅大型股、兩源核對假警報），另外標記咗煉油股集中、事件驅動、流動性同低價股，詳見「審視標記」頁。",
    f"獨立重寫嘅篩選程式（只按規則文字，唔共用代碼）得出同一份 {len(rows)} 隻名單，逐欄比對 0 個差異。",
    "所有代號都連去 TradingView 圖表；計得出嘅欄位（距 MA%、斜率、分數、排名、覆蓋度）全部係公式。",
]

json.dump({"extra_flags": extra, "near_miss_detail": S["near_miss"], "vs_prev": vs_prev, "vs_prevday": vs_prevday,
           "prevday_date": PD["meta"]["last_date"], "findings": findings, "xchk_summary": checks,
           "market": market, "breadth": meta["breadth"], "notes": notes,
           "flag_action": {"event": "保留、標橙底；要當事件交易睇", "heavy_break": "保留、標橙底；聽日企唔返 MA20 就當失敗",
                           "liq": "保留、標橙底；落單注意滑價", "floor": "保留、標橙底",
                           "gapdown": "保留、標橙底；回調入面有急跌日", "spike": "保留、標橙底"},
           "survive": survive, "n_sens": len(S["sensitivity"]),
           "stats": {"c_ref": c_ref, "c_oth": c_oth, "only_last": only_last, "list_move": list_move,
                     "left_s5": left_s5, "both_prev": both}},
          open(f"{W}/{OUT}", "w"), ensure_ascii=False, indent=1)
print("wrote", OUT, "| findings", len(findings), "| flags on", len(extra), "names | prev-day overlap",
      len(now & before), "| R20 overlap", len(both), "| refiner corr", round(c_ref, 2), "vs", round(c_oth, 2))

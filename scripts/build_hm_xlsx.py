#!/usr/bin/env python3
"""Build the hot-money pull-back watchlist (R23 onward) as an Excel workbook.

Every value the sheet can derive from other cells is a formula: the day's
move, the distances to MA20 / MA50 / the high, the MA20 slope, the ATR ratios,
every sub-score (from the measured inputs beside it), the four component
scores, the composite and the rank. The page sheets read the 總表 row by
reference, so there is one source per number. Measured inputs (closes, MAs,
volumes, the event day and its multiples, the 10MA session) are blue. Every
ticker cell links to its TradingView chart.
"""
import json, os
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.comments import Comment

W = os.environ.get("WORK_DIR", "./data")
SCREEN = os.environ.get("SCREEN_JSON", "screen_hm23.json")
REVIEW = os.environ.get("REVIEW_JSON", "review_hm23.json")
PREV_SCREEN = os.environ.get("PREV_SCREEN", "screen_mp22.json")
RESEARCH = os.environ.get("RESEARCH_JSON", "research_hm23.json")
NEWS = os.environ.get("NEWS_JSON", "news20.json")
OUT = os.environ["OUT_XLSX"]
REV = os.environ.get("REV", "R23.00")
PREV_REV = os.environ.get("PREV_REV", "R22")

scr = json.load(open(f"{W}/{SCREEN}"))
rev = json.load(open(f"{W}/{REVIEW}"))
prev = json.load(open(f"{W}/{PREV_SCREEN}"))
RESJ = json.load(open(f"{W}/{RESEARCH}"))
news = json.load(open(f"{W}/{NEWS}")) if os.path.exists(f"{W}/{NEWS}") else {}
rows = scr["rows"]
META = scr["meta"]
LAST = META["last_date"]
P = META["params"]; PL = META["params_loose"]
WT = META["weights"]

FONT = "Arial"
HDR_FILL = PatternFill("solid", fgColor="1F3864")
HDR_FONT = Font(name=FONT, bold=True, color="FFFFFF", size=10)
NEW_FILL = PatternFill("solid", fgColor="FFF2CC")
WARN_FILL = PatternFill("solid", fgColor="FCE4D6")
T2_FILL = PatternFill("solid", fgColor="F2F2F2")
THIN = Side(style="thin", color="BFBFBF")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
BASE = Font(name=FONT, size=10)
BOLD = Font(name=FONT, size=10, bold=True)
TITLE = Font(name=FONT, size=14, bold=True, color="1F3864")
INPUT = Font(name=FONT, size=10, color="0000FF")
LINK_FONT = Font(name=FONT, size=10, bold=True, color="0563C1", underline="single")
SRC_FONT = Font(name=FONT, size=9, color="0563C1", underline="single")
WRAP = Alignment(wrap_text=True, vertical="top")

PREV_ROWS = prev.get("rows") or prev["page1"]
PREV_RANK = {r["sym"]: r.get("rank", i) for i, r in enumerate(PREV_ROWS, 1)}
PREV_DATE = (prev.get("meta") or {}).get("last_date", "")
EXCH = {}
for r in rows:
    EXCH[r["sym"]] = r.get("exch") or "—"
for r in PREV_ROWS:
    EXCH.setdefault(r["sym"], r.get("exch") or "—")


def tv_url(sym):
    s2 = sym.replace("/", ".").lower()
    ex = EXCH.get(sym, "—")
    return (f"https://www.tradingview.com/chart/Q1c5VWwD/?symbol={ex.lower()}%3A{s2}" if ex and ex != "—"
            else f"https://www.tradingview.com/chart/Q1c5VWwD/?symbol={s2}")


def link_ticker(ws_, row_, col_, sym):
    c = ws_.cell(row=row_, column=col_, value=sym)
    c.hyperlink = tv_url(sym); c.font = LINK_FONT; c.border = BOX
    return c


def style_header(ws, headers, widths, row=1, freeze_at=None):
    for j, (h, wd) in enumerate(zip(headers, widths), 1):
        c = ws.cell(row=row, column=j, value=h)
        c.fill, c.font = HDR_FILL, HDR_FONT
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = BOX
        ws.column_dimensions[get_column_letter(j)].width = wd
    ws.row_dimensions[row].height = 42
    ws.freeze_panes = freeze_at or f"D{row + 1}"
    ws.auto_filter.ref = f"A{row}:{get_column_letter(len(headers))}{row}"


def put(ws, r, c, v, fmt=None, font=None, fill=None, align=None):
    cell = ws.cell(row=r, column=c, value=v)
    cell.font = font or BASE
    cell.border = BOX
    if fmt: cell.number_format = fmt
    if fill: cell.fill = fill
    if align: cell.alignment = align
    return cell


CAPZH = {"a": "大型", "b": "中型", "c": "小型", "x": "未分類"}
GZH = {"C1a": "C1a 事件日", "C1b": "C1b 熱錢", "C2": "C2 曾有10MA上升", "C3": "C3 回落20MA", "C4": "C4 波幅減低"}
PCT = "0.0%"; PCT2 = "0.00%"; PX = '$#,##0.00##'; SC = "0.0"
flags_by = {r["sym"]: list(r["flags"]) for r in rows}
for s, fl in (rev.get("extra_flags") or {}).items():
    flags_by.setdefault(s, []).extend(fl)

# ================================================================ 總表
wb = Workbook()
ws = wb.active
ws.title = "總表"
COLS = [
    ("tier", "梯隊", 5), ("rank", "排名", 5), ("sym", "代號", 8), ("name", "公司", 26), ("exch", "交易所", 7),
    ("sec", "板塊", 9), ("ind", "行業", 24), ("mcap", "市值(十億美元)", 9), ("cap", "市值組", 6),
    ("close", "收市價", 9), ("prev", "前收", 9), ("chg", "當日%", 7), ("high", "當日高", 9), ("low", "當日低", 9),
    ("ma10", "MA10", 9), ("ma20", "MA20", 9), ("d20", "距MA20%", 7), ("ma50", "MA50", 9),
    ("ma20l", "MA20（5日前）", 9), ("slope", "MA20 5日斜率%", 7),
    ("H", "63日最高收市", 9), ("hid", "高位日期", 10), ("ago", "高位至今（交易日）", 7), ("dd", "距高位%", 7),
    ("legf", "升浪起點", 10), ("legd", "升浪日數", 6), ("leg", "升浪幅度%", 7), ("ext", "高位時高過MA20%", 8), ("lowgap", "近3日最低價距MA20%", 8),
    ("evd", "事件日", 10), ("evr", "事件日升幅", 7), ("evg", "事件日跳空", 7), ("evv", "事件日量比（×50日均量）", 8), ("evn", "事件日數目", 6),
    ("legdv", "升浪成交額（日均）", 11), ("basedv", "升浪前60日成交額（日均）", 11), ("dvr", "升浪成交額比", 7),
    ("m10d", "10MA上升日期", 10), ("m10r", "MA10 10日升幅", 7), ("m10f", "MA10上升步比例", 7),
    ("volr", "回調量比", 7), ("atr5", "ATR5%", 7), ("atr20", "ATR20%", 7), ("atrleg", "升浪期ATR%", 7),
    ("c20", "ATR5/ATR20", 7), ("cleg", "ATR5/升浪ATR", 7),
    ("s_dv", "成交額分", 6), ("s_evol", "事件量分", 6), ("s_leg", "升浪分", 6),
    ("s_rise", "10MA升幅分", 6), ("s_frac", "10MA步分", 6),
    ("s_vol", "量縮", 6), ("s_near", "貼近MA20", 6), ("s_slope", "MA20斜率分", 6), ("s_depth", "回調深度分", 6), ("s_hold", "企穩", 6),
    ("s_c20", "短期收窄", 6), ("s_cleg", "對升浪收窄", 6),
    ("hot", "熱錢分數", 7), ("trend", "10MA分數", 7), ("pq", "回調質素", 7), ("vc", "波幅收窄", 7), ("score", "綜合分數", 8),
    ("needs", "唔過嘅條件（梯隊2）", 22), ("prevr", f"{PREV_REV} 排名", 7), ("surv", "門檻測試留低", 8), ("flag", "審視標記", 40), ("xchk", "兩源最大差%", 8),
]
C = {k: i for i, (k, _, _) in enumerate(COLS, 1)}
L = {k: get_column_letter(i) for k, i in C.items()}
style_header(ws, [h for _, h, _ in COLS], [w for _, _, w in COLS], freeze_at="D2")
N = len(rows); first, last_row = 2, N + 1
ROW_OF = {}
clip = lambda expr: f"=MAX(0,MIN(1,{expr}))"
for i, r in enumerate(rows):
    rw = i + 2; s = r["sym"]; ROW_OF[s] = rw
    f = lambda k: f"{L[k]}{rw}"
    fill = T2_FILL if r["tier"] == 2 else None
    put(ws, rw, C["tier"], r["tier"], "0", BOLD, fill)
    put(ws, rw, C["rank"], f"=COUNTIFS(${L['tier']}${first}:${L['tier']}${last_row},{f('tier')},${L['score']}${first}:${L['score']}${last_row},\">\"&{f('score')})+1", "0", fill=fill)
    link_ticker(ws, rw, C["sym"], s)
    put(ws, rw, C["name"], r["name"]); put(ws, rw, C["exch"], r["exch"]); put(ws, rw, C["sec"], r["sector_zh"]); put(ws, rw, C["ind"], r["industry"])
    put(ws, rw, C["mcap"], r["mcap_b"] or None, "0.00", INPUT); put(ws, rw, C["cap"], CAPZH[r["cap"]])
    put(ws, rw, C["close"], r["close"], PX, INPUT); put(ws, rw, C["prev"], r["prev"], PX, INPUT)
    put(ws, rw, C["chg"], f"={f('close')}/{f('prev')}-1", PCT2)
    put(ws, rw, C["high"], r["high"], PX, INPUT); put(ws, rw, C["low"], r["low"], PX, INPUT)
    put(ws, rw, C["ma10"], r["ma10_last"], PX, INPUT); put(ws, rw, C["ma20"], r["ma20"], PX, INPUT)
    put(ws, rw, C["d20"], f"={f('close')}/{f('ma20')}-1", PCT2)
    put(ws, rw, C["ma50"], r["ma50"], PX, INPUT); put(ws, rw, C["ma20l"], r["ma20_lag"], PX, INPUT)
    put(ws, rw, C["slope"], f"={f('ma20')}/{f('ma20l')}-1", PCT2)
    put(ws, rw, C["H"], r["H"], PX, INPUT); put(ws, rw, C["hid"], r["hi_date"]); put(ws, rw, C["ago"], r["ago"], "0", INPUT)
    put(ws, rw, C["dd"], f"={f('close')}/{f('H')}-1", PCT)
    put(ws, rw, C["legf"], r["leg_from"]); put(ws, rw, C["legd"], r["leg_days"], "0", INPUT); put(ws, rw, C["leg"], r["leg"], "0%", INPUT)
    put(ws, rw, C["ext"], r["ext"], PCT, INPUT); put(ws, rw, C["lowgap"], r["low_gap"], PCT2, INPUT)
    put(ws, rw, C["evd"], r["ev_date"]); put(ws, rw, C["evr"], r["ev_ret"], PCT, INPUT); put(ws, rw, C["evg"], r["ev_gap"], PCT, INPUT)
    put(ws, rw, C["evv"], r["ev_vol"], "0.0", INPUT); put(ws, rw, C["evn"], r["ev_count"], "0", INPUT)
    put(ws, rw, C["legdv"], r["leg_dv"], '$#,##0', INPUT); put(ws, rw, C["basedv"], r["base_dv"], '$#,##0', INPUT)
    put(ws, rw, C["dvr"], f"={f('legdv')}/{f('basedv')}", "0.00")
    put(ws, rw, C["m10d"], r["ma10_date"]); put(ws, rw, C["m10r"], r["ma10_rise"], PCT, INPUT); put(ws, rw, C["m10f"], r["ma10_frac"], "0%", INPUT)
    put(ws, rw, C["volr"], r["vol_ratio"], "0.00", INPUT)
    put(ws, rw, C["atr5"], r["atr5"], PCT2, INPUT); put(ws, rw, C["atr20"], r["atr20"], PCT2, INPUT); put(ws, rw, C["atrleg"], r["leg_atr"], PCT2, INPUT)
    put(ws, rw, C["c20"], f"={f('atr5')}/{f('atr20')}", "0.00"); put(ws, rw, C["cleg"], f"={f('atr5')}/{f('atrleg')}", "0.00")
    put(ws, rw, C["s_dv"], clip(f"({f('dvr')}-2)/4"), "0.00")
    put(ws, rw, C["s_evol"], clip(f"({f('evv')}-3)/7"), "0.00")
    put(ws, rw, C["s_leg"], clip(f"({f('leg')}-0.25)/0.75"), "0.00")
    put(ws, rw, C["s_rise"], clip(f"({f('m10r')}-0.05)/0.2"), "0.00")
    put(ws, rw, C["s_frac"], clip(f"({f('m10f')}-0.7)/0.3"), "0.00")
    put(ws, rw, C["s_vol"], clip(f"({f('volr')}-1.2)/(0.6-1.2)") if r["vol_ratio"] is not None else 0, "0.00")
    put(ws, rw, C["s_near"], clip(f"(ABS({f('d20')})-0.03)/(0-0.03)"), "0.00")
    put(ws, rw, C["s_slope"], clip(f"{f('slope')}/0.03"), "0.00")
    put(ws, rw, C["s_depth"], clip(f"(-{f('dd')}-0.3)/(0.15-0.3)"), "0.00")
    put(ws, rw, C["s_hold"], f"=0.5*IF({f('high')}>{f('low')},({f('close')}-{f('low')})/({f('high')}-{f('low')}),0.5)+0.5*({f('close')}>={f('ma20')})", "0.00")
    put(ws, rw, C["s_c20"], clip(f"({f('c20')}-0.9)/(0.5-0.9)"), "0.00")
    put(ws, rw, C["s_cleg"], clip(f"({f('cleg')}-0.7)/(0.3-0.7)"), "0.00")
    h = WT["hot"]; put(ws, rw, C["hot"], f"=100*({h['dv']}*{f('s_dv')}+{h['evol']}*{f('s_evol')}+{h['leg']}*{f('s_leg')})", SC)
    t = WT["trend"]; put(ws, rw, C["trend"], f"=100*({t['rise']}*{f('s_rise')}+{t['frac']}*{f('s_frac')})", SC)
    q = WT["pq"]; put(ws, rw, C["pq"], f"=100*({q['vol']}*{f('s_vol')}+{q['near']}*{f('s_near')}+{q['slope']}*{f('s_slope')}+{q['depth']}*{f('s_depth')}+{q['hold']}*{f('s_hold')})", SC)
    v = WT["vc"]; put(ws, rw, C["vc"], f"=100*({v['c20']}*{f('s_c20')}+{v['cleg']}*{f('s_cleg')})", SC)
    sw = WT["score"]; put(ws, rw, C["score"], f"={sw['hot']}*{f('hot')}+{sw['trend']}*{f('trend')}+{sw['pq']}*{f('pq')}+{sw['vc']}*{f('vc')}", SC, BOLD)
    put(ws, rw, C["needs"], "；".join(f"{GZH[k]}：{r['needs_why'][k]}" for k in r["needs"]), align=WRAP)
    put(ws, rw, C["prevr"], PREV_RANK.get(s), "0")
    put(ws, rw, C["surv"], f"{rev['survive'][s]}/{rev['n_sens']}" if s in (rev.get("survive") or {}) else "")
    fl = flags_by.get(s, [])
    put(ws, rw, C["flag"], "；".join(t_ for _, t_ in fl), align=WRAP)
    put(ws, rw, C["xchk"], r["xchk"]["max_abs_pct"] / 100, "0.000%", INPUT)
    if fl:
        ws.cell(row=rw, column=C["sym"]).fill = WARN_FILL; ws.cell(row=rw, column=C["flag"]).fill = WARN_FILL
    elif r["tier"] == 2:
        ws.cell(row=rw, column=C["sym"]).fill = T2_FILL
    if s not in PREV_RANK:
        ws.cell(row=rw, column=C["name"]).fill = NEW_FILL
    q_ = RESJ["research"].get(s)
    if q_:
        ws.cell(row=rw, column=C["evd"]).comment = Comment(q_[0], "watchlist")
ws.auto_filter.ref = f"A1:{get_column_letter(len(COLS))}{last_row}"

# ================================================================ 市值分頁
for b in ("a", "b", "c"):
    wsp = wb.create_sheet(f"{CAPZH[b]}股")
    head = ["梯隊", "頁內排名", "總表排名", "代號", "公司", "板塊", "收市價", "距MA20%", "距高位%", "事件日", "事件日升幅", "事件日量比",
            "升浪成交額比", "MA10 10日升幅", "ATR5/ATR20", "ATR5/升浪ATR", "熱錢分數", "10MA分數", "回調質素", "波幅收窄", "綜合分數", "唔過嘅條件（梯隊2）", "審視標記"]
    lim = {"a": "≥ $100 億", "b": "$20–100 億", "c": "< $20 億"}[b]
    wsp.cell(row=1, column=1, value=f"{CAPZH[b]}股（市值 {lim}）· 兩個梯隊 · 以綜合分數排序 · {LAST} 收市").font = TITLE
    style_header(wsp, head, [5, 6, 6, 8, 26, 9, 9, 7, 7, 10, 7, 7, 7, 7, 7, 7, 7, 7, 7, 7, 8, 30, 36], row=3, freeze_at="E4")
    syms = scr["pages"][b]
    top, bot = 4, 3 + len(syms)
    for i, s in enumerate(syms):
        rw = 4 + i; src = ROW_OF[s]
        ref = lambda k: f"='總表'!{L[k]}{src}"
        tier = rows[src - 2]["tier"]
        fill = T2_FILL if tier == 2 else None
        put(wsp, rw, 1, ref("tier"), "0", BOLD, fill)
        put(wsp, rw, 2, f"=COUNTIFS($A${top}:$A${bot},A{rw},$U${top}:$U${bot},\">\"&U{rw})+1", "0", fill=fill)
        put(wsp, rw, 3, ref("rank"), "0"); link_ticker(wsp, rw, 4, s)
        put(wsp, rw, 5, ref("name")); put(wsp, rw, 6, ref("sec")); put(wsp, rw, 7, ref("close"), PX)
        put(wsp, rw, 8, ref("d20"), PCT2); put(wsp, rw, 9, ref("dd"), PCT); put(wsp, rw, 10, ref("evd"))
        put(wsp, rw, 11, ref("evr"), PCT); put(wsp, rw, 12, ref("evv"), "0.0"); put(wsp, rw, 13, ref("dvr"), "0.00")
        put(wsp, rw, 14, ref("m10r"), PCT); put(wsp, rw, 15, ref("c20"), "0.00"); put(wsp, rw, 16, ref("cleg"), "0.00")
        put(wsp, rw, 17, ref("hot"), SC); put(wsp, rw, 18, ref("trend"), SC); put(wsp, rw, 19, ref("pq"), SC); put(wsp, rw, 20, ref("vc"), SC)
        put(wsp, rw, 21, ref("score"), SC, BOLD); put(wsp, rw, 22, ref("needs"), align=WRAP); put(wsp, rw, 23, ref("flag"), align=WRAP)
        if flags_by.get(s):
            wsp.cell(row=rw, column=4).fill = WARN_FILL
    if not syms:
        wsp.cell(row=4, column=1, value="本市值組冇股票符合")
    wsp.auto_filter.ref = f"A3:W{max(bot, 4)}"

# ================================================================ 篩選規則
wr = wb.create_sheet("篩選規則")
for col, wd in zip("ABCD", (16, 78, 16, 10)):
    wr.column_dimensions[col].width = wd
wr.cell(row=1, column=1, value=f"{REV} 篩選條件：有熱錢及消息驅動 ＋ 曾有 10MA 上升 ＋ 回落到 20MA ＋ 波幅減低").font = TITLE
fun = META["funnel"]; each = META["each_gate"]
lines = [
    ("說明", f"由 {REV} 起取代 R21–R22 嘅「回報排頭 10% 動能」條件。股票池、價格來源（Yahoo 日線、Nasdaq 快照核對）不變；"
             f"H = 近 63 日最高收市，升浪 = 由 H 前 63 日內最低收市升到 H。數據終點 {LAST}，{META['n_days']} 個交易日（{META['cal_first']} 起）。", "門檻", "通過數目"),
    ("股票池", "當日有成交、≥90 個交易日歷史（按 Nasdaq 上市日計，SPAC 空殼期唔計）、收市 ≥$2、普通股、20 日成交額中位數 ≥$1M", "同 R1–R22", fun["eligible"]),
    ("C1a 事件日（消息驅動）", f"高位前 {P['ev_look']} 日內（唔計高位之後）有一日：收市對收市 ≥{P['ev_ret']:+.0%}，或開市比前收跳空 ≥{P['ev_gap']:+.0%}；"
                          f"而且當日成交量 ≥{P['ev_vol']:.0f}× 之前 50 日平均。幾日都合格就取量比最大嗰日做「事件日」", f"單獨 {each['C1a']:,}", fun["C1a"]),
    ("C1b 熱錢", f"升浪期（至少高位前 {P['hot_min_leg']} 日）日均成交額 ≥ 升浪開始前 {P['hot_base']} 日日均嘅 {P['hot_dv']:.0f} 倍", f"單獨 {each['C1b']:,}", fun["C1b"]),
    ("C2 曾有 10MA 上升", f"近 {P['ma10_look']} 日內（唔計今日）有一日通過 R1–R20 嘅 10MA 測試：MA10 比 10 日前高 ≥{P['ma10_rise']:.0%}、最後三個 MA10 值遞升、"
                        f"10 步入面升 ≥{P['ma10_frac']:.0%}。幾日都合格取升幅最大嗰日", f"單獨 {each['C2']:,}", fun["C2"]),
    ("C3 回落到 20MA", f"MA20 高過 {P['ma20_slope_lag']} 日前；H 喺 {P['hi_ago_min']}–{P['hi_ago_max']} 日前；收市比 H 低 {P['depth_min']:.0%}–{P['depth_max']:.0%}；"
                      f"H 當日收市高過當日 MA20 ≥{P['ext_min']:.0%}；收市喺 MA20 {P['dist_lo']:+.0%} 至 {P['dist_hi']:+.0%}；近 {P['touch_days']} 日有一日最低價 ≤ MA20×{1 + P['touch_tol']:.3f}",
     f"單獨 {each['C3']:,}", fun["C3"]),
    ("C4 波幅減低", f"近 5 日平均真實波幅（佔前收 %）≤ {P['c20']}× 近 20 日平均，而且 ≤ {P['cleg']}× 升浪期平均。真實波幅只計有高低位嘅日子", f"單獨 {each['C4']:,}", fun["C4"]),
    ("第二梯隊", "每個門檻放寬一級（事件日 +6%／跳空 +5%／2× 量；熱錢 1.5×；MA10 升 3%、6 步；高位 40 日內；回調 ≤40%；高位時高過 MA20 6%；"
               "收市 ±5%、觸及 3%；ATR5/ATR20 ≤1.0、對升浪 ≤0.85）先合格嘅股票；總表「唔過嘅條件」欄列明每隻差邊項", "", META["n_tier2"]),
]
rr = 3
for a, b, c_, d in lines:
    put(wr, rr, 1, a, font=BOLD); put(wr, rr, 2, b, align=WRAP); put(wr, rr, 3, c_); put(wr, rr, 4, d, "#,##0")
    wr.row_dimensions[rr].height = 48 if len(str(b)) > 70 else 18
    rr += 1
rr += 1
put(wr, rr, 1, "評分（每項 0–1，線性、兩頭封頂）", font=BOLD); rr += 1
score_lines = [
    ("熱錢分數", "0.4 × 升浪成交額比（2×→0、6×→1）+ 0.3 × 事件日量比（3×→0、10×→1）+ 0.3 × 升浪幅度（25%→0、100%→1）"),
    ("10MA分數", "0.5 × MA10 10 日升幅（5%→0、25%→1）+ 0.5 × MA10 上升步比例（70%→0、100%→1）"),
    ("回調質素", "0.30 量縮（高位後日均量 ÷ 高位前 20 日：1.2→0、0.6→1）+ 0.25 貼近 MA20（|距 MA20|：3%→0、0%→1）+ 0.20 MA20 斜率（0→0、3%→1）"
               "+ 0.10 回調深度（30%→0、15%→1）+ 0.15 企穩（0.5 × 收市喺當日高低區間位置 + 0.5 × 收市 ≥ MA20）"),
    ("波幅收窄", "0.5 × ATR5/ATR20（0.9→0、0.5→1）+ 0.5 × ATR5/升浪 ATR（0.7→0、0.3→1）"),
    ("綜合分數", f"{WT['score']['hot']} × 熱錢 + {WT['score']['trend']} × 10MA + {WT['score']['pq']} × 回調質素 + {WT['score']['vc']} × 波幅收窄（每頁排名用；先分梯隊）"),
    ("欄位顏色", "藍字 = 量度值（輸入）；黑字 = 公式；灰底 = 第二梯隊；橙底 = 有審視標記；黃底公司名 = 上版冇"),
]
for a, b in score_lines:
    put(wr, rr, 1, a, font=BOLD); put(wr, rr, 2, b, align=WRAP); wr.row_dimensions[rr].height = 32 if len(b) > 70 else 18; rr += 1
rr += 1
put(wr, rr, 1, "同上一套條件嘅分別", font=BOLD)
put(wr, rr, 2, "R21–R22：1／2／3／6 個月回報排全體頭 10% ＋ 回到上升中嘅 20MA —— 捉慢慢升上去嘅強勢股。"
               f"{REV}：先要有一日放量大升嘅消息日、升浪期成交額係之前兩倍（熱錢）、而且試過通過舊嘅 10MA 上升測試，再回落到 20MA 兼波幅收窄。"
               "兩套條件捉嘅股票本身唔同（見「同R22對照」頁）。", align=WRAP)
wr.row_dimensions[rr].height = 60

# ================================================================ 敏感度
wsn = wb.create_sheet("敏感度")
wsn.cell(row=1, column=1, value="每次只郁一個門檻，睇第一梯隊點變（基準 = 本版門檻）；最後兩行係全部門檻同時放寬／收緊一級").font = TITLE
style_header(wsn, ["門檻", "基準", "改為", "名單數目", "變動", "新增／剔走嘅代號 →"], [16, 8, 8, 9, 8, 9], row=3, freeze_at="A4")
PNAME = {"ev_ret": "事件日升幅", "ev_vol": "事件日量比", "hot_dv": "升浪成交額比", "ma10_rise": "MA10 10日升幅", "ma10_frac": "MA10上升步比例",
         "ext_min": "高位時高過MA20", "depth_max": "最深回調", "dist_lo": "距MA20下限", "dist_hi": "距MA20上限", "touch_tol": "觸及容差",
         "c20": "ATR5/ATR20上限", "cleg": "ATR5/升浪ATR上限", "hi_ago_max": "高位最遠日數"}
rw = 4
for sct in scr["sensitivity"]:
    put(wsn, rw, 1, PNAME.get(sct["param"], sct["param"]))
    put(wsn, rw, 2, sct["base"]); put(wsn, rw, 3, sct["alt"]); put(wsn, rw, 4, sct["n"], "0")
    put(wsn, rw, 5, f"+{len(sct['added'])} / −{len(sct['dropped'])}")
    col = 6
    for s in sct["added"]:
        link_ticker(wsn, rw, col, s); wsn.cell(row=rw, column=col).fill = NEW_FILL; col += 1
    for s in sct["dropped"]:
        link_ticker(wsn, rw, col, s); wsn.cell(row=rw, column=col).fill = WARN_FILL; col += 1
    rw += 1
for j in range(6, 40):
    wsn.column_dimensions[get_column_letter(j)].width = 8
put(wsn, rw + 1, 1, "黃底 = 放寬後新增；橙底 = 收緊後剔走", font=BOLD)

# ================================================================ 差一項
wsm = wb.create_sheet("差一項")
wsm.cell(row=1, column=1, value="五項條件只差一項嘅股票（基準門檻）").font = TITLE
style_header(wsm, ["代號", "唔通過嘅一項", "收市價", "距MA20%", "距高位%", "高位至今", "說明"], [8, 16, 10, 9, 9, 8, 80], row=3, freeze_at="B4")
nm = sorted(rev.get("near_miss_detail") or scr["near_miss"], key=lambda x: (x["failed"], x["sym"]))
for i, x in enumerate(nm):
    rw = 4 + i
    link_ticker(wsm, rw, 1, x["sym"]); put(wsm, rw, 2, GZH.get(x["failed"], x["failed"]))
    put(wsm, rw, 3, x["close"], PX, INPUT); put(wsm, rw, 4, x["d20"], PCT2, INPUT); put(wsm, rw, 5, x["dd"], PCT, INPUT)
    put(wsm, rw, 6, x["ago"], "0", INPUT); put(wsm, rw, 7, x["why"], align=WRAP)

# ================================================================ 20MA回調池
wpl = wb.create_sheet("20MA回調池")
wpl.cell(row=1, column=1, value="而家處於「上升中 20MA 回調位」（通過 C3）嘅全部股票，同佢哋差邊項").font = TITLE
style_header(wpl, ["梯隊", "代號", "收市價", "距MA20%", "距高位%", "升浪成交額比", "事件日量比", "ATR5/ATR20", "ATR5/升浪ATR", "唔過嘅條件", "說明"],
             [5, 8, 10, 9, 9, 9, 9, 9, 9, 24, 90], row=3, freeze_at="C4")
for i, x in enumerate(rev.get("c3_pool") or []):
    rw = 4 + i
    put(wpl, rw, 1, x["tier"], "0", BOLD if x["tier"] else BASE); link_ticker(wpl, rw, 2, x["sym"])
    put(wpl, rw, 3, x["close"], PX, INPUT); put(wpl, rw, 4, x["d20"], PCT2, INPUT); put(wpl, rw, 5, x["dd"], PCT, INPUT)
    put(wpl, rw, 6, x["dv_ratio"], "0.00", INPUT); put(wpl, rw, 7, x["ev_vol"], "0.0", INPUT)
    put(wpl, rw, 8, x["c20"], "0.00", INPUT); put(wpl, rw, 9, x["cleg"], "0.00", INPUT)
    put(wpl, rw, 10, "、".join(GZH[k] for k in x["fail"]) or "全部通過", align=WRAP)
    put(wpl, rw, 11, "；".join(f"{GZH[k]}：{v}" for k, v in x["why"].items()), align=WRAP)
    if x["tier"] == 1:
        wpl.cell(row=rw, column=2).fill = NEW_FILL
    elif x["tier"] == 2:
        wpl.cell(row=rw, column=2).fill = T2_FILL

# ================================================================ 熱錢板塊
wsh = wb.create_sheet("熱錢板塊")
HOT = scr.get("hot") or []; SU = scr.get("sector_universe") or {}
tot_u = sum(SU.values()) or 1
wsh.cell(row=1, column=1, value=f"而家邊啲板塊有熱錢及消息驅動：通過 C1a（事件日）同 C1b（升浪熱錢）嘅全部 {len(HOT)} 隻，唔理有冇回落到 20MA").font = TITLE
style_header(wsh, ["板塊", "熱錢股數目", "佔熱錢股比例", "佔股票池比例", "集中度（倍）", "近 15 日有事件日", "仍高於 MA20 >3%", "貼近 MA20 ±3%", "跌穿 MA20 >3%", "曾有 10MA 上升"],
             [12, 9, 9, 9, 9, 10, 10, 10, 10, 10], row=3, freeze_at="B4")
by = {}
for h in HOT:
    by.setdefault(h["sector_zh"], []).append(h)
rw = 4
cut15 = scr["meta"]["last_date"]
for sec, xs in sorted(by.items(), key=lambda kv: -len(kv[1])):
    put(wsh, rw, 1, sec, font=BOLD); put(wsh, rw, 2, len(xs), "0")
    put(wsh, rw, 3, f"=B{rw}/{len(HOT)}", PCT); put(wsh, rw, 4, SU.get(sec, 0) / tot_u, PCT, INPUT)
    put(wsh, rw, 5, f"=C{rw}/D{rw}", "0.00")
    put(wsh, rw, 6, sum(1 for x in xs if x["ev_date"] >= scr["meta"]["recent_cut"]), "0")
    put(wsh, rw, 7, sum(1 for x in xs if x["d20"] > 0.03), "0"); put(wsh, rw, 8, sum(1 for x in xs if -0.03 <= x["d20"] <= 0.03), "0")
    put(wsh, rw, 9, sum(1 for x in xs if x["d20"] < -0.03), "0"); put(wsh, rw, 10, sum(1 for x in xs if x["ma10_ok"]), "0")
    rw += 1
rw += 1
put(wsh, rw, 1, "集中度 = 板塊佔熱錢股比例 ÷ 板塊佔股票池比例；>1 即熱錢喺呢個板塊比例偏高。「近 15 日有事件日」= 事件日喺 " + scr["meta"]["recent_cut"] + " 或之後", font=BOLD)
rw += 2
head = ["板塊", "代號", "公司", "行業", "市值組", "收市價", "事件日", "事件日升幅", "事件日跳空", "事件日量比", "升浪起點", "升浪幅度%", "升浪成交額比",
        "高位日期", "高位至今", "距高位%", "距MA20%", "狀態", "曾有10MA上升", "ATR5/ATR20", "ATR5/升浪ATR", "新條件唔過嘅"]
for j, (h_, wd) in enumerate(zip(head, [10, 8, 24, 26, 6, 9, 10, 8, 8, 8, 10, 8, 8, 10, 7, 8, 8, 10, 8, 8, 8, 30]), 1):
    c = wsh.cell(row=rw, column=j, value=h_); c.fill, c.font = HDR_FILL, HDR_FONT
    c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True); c.border = BOX
    wsh.column_dimensions[get_column_letter(j)].width = max(wsh.column_dimensions[get_column_letter(j)].width or 0, wd)
wsh.row_dimensions[rw].height = 42
hdr2 = rw
for x in sorted(HOT, key=lambda x: (-len(by[x["sector_zh"]]), x["sector_zh"], x["ev_date"], x["sym"])):
    rw += 1
    put(wsh, rw, 1, x["sector_zh"]); link_ticker(wsh, rw, 2, x["sym"]); put(wsh, rw, 3, x["name"]); put(wsh, rw, 4, x["industry"])
    put(wsh, rw, 5, CAPZH[x["cap"]]); put(wsh, rw, 6, x["close"], PX, INPUT); put(wsh, rw, 7, x["ev_date"])
    put(wsh, rw, 8, x["ev_ret"], PCT, INPUT); put(wsh, rw, 9, x["ev_gap"], PCT, INPUT); put(wsh, rw, 10, x["ev_vol"], "0.0", INPUT)
    put(wsh, rw, 11, x["leg_from"]); put(wsh, rw, 12, x["leg"], "0%", INPUT); put(wsh, rw, 13, x["dv_ratio"], "0.00", INPUT)
    put(wsh, rw, 14, x["hi_date"]); put(wsh, rw, 15, x["ago"], "0", INPUT); put(wsh, rw, 16, x["dd"], PCT, INPUT); put(wsh, rw, 17, x["d20"], PCT2, INPUT)
    put(wsh, rw, 18, "跌穿 MA20" if x["d20"] < -0.03 else ("仍高於 MA20" if x["d20"] > 0.03 else "貼近 MA20"))
    put(wsh, rw, 19, "有" if x["ma10_ok"] else ""); put(wsh, rw, 20, x["c20"], "0.00", INPUT); put(wsh, rw, 21, x["cleg"], "0.00", INPUT)
    put(wsh, rw, 22, "、".join(GZH[k] for k in x["fail"]) or "全部通過", align=WRAP)
    if not x["fail"]:
        wsh.cell(row=rw, column=2).fill = NEW_FILL
    elif x["sym"] in ROW_OF:
        wsh.cell(row=rw, column=2).fill = T2_FILL
wsh.auto_filter.ref = f"A{hdr2}:V{rw}"

# ================================================================ 同R22對照
wso = wb.create_sheet(f"同{PREV_REV}對照")
wso.cell(row=1, column=1, value=f"{PREV_REV}（{PREV_DATE} 收市，高動能回到 20MA）名單 vs {REV}（{LAST} 收市，新條件）").font = TITLE
style_header(wso, ["類別", "代號", f"{PREV_REV} 排名", f"{REV} 排名", "說明"], [12, 8, 9, 9, 100], row=3, freeze_at="C4")
for i, x in enumerate(rev.get("vs_prev") or []):
    rw = 4 + i
    put(wso, rw, 1, x["kind"]); link_ticker(wso, rw, 2, x["sym"])
    put(wso, rw, 3, x.get("prev_rank"), "0"); put(wso, rw, 4, x.get("rank"), "0"); put(wso, rw, 5, x.get("why", ""), align=WRAP)
    if x["kind"] == "新上榜":
        wso.cell(row=rw, column=2).fill = NEW_FILL
    elif x["kind"] == "跌出":
        wso.cell(row=rw, column=2).fill = WARN_FILL

# ================================================================ 上一版向前測試
fw = rev.get("forward")
if fw:
    wsw = wb.create_sheet(f"{PREV_REV}向前測試")
    wsw.cell(row=1, column=1, value=f"{PREV_REV} 名單（{fw['from']} 收市）之後 {fw['n_days']} 個交易日點行（至 {LAST} 收市）").font = TITLE
    rw = 3
    for a, b in fw["summary"]:
        put(wsw, rw, 1, a, font=BOLD); wsw.merge_cells(start_row=rw, start_column=2, end_row=rw, end_column=10)
        put(wsw, rw, 2, b, align=WRAP); wsw.row_dimensions[rw].height = 32; rw += 1
    rw += 1
    head = [f"{PREV_REV} 排名", "代號", f"{fw['from']} 收市", f"{LAST} 收市", "期間回報", "減大市中位數", f"{LAST} 距 MA20%", "狀態", "新條件唔過嘅", f"{REV} 排名", f"{PREV_REV} 標記"]
    style_header(wsw, head, [8, 8, 11, 11, 9, 10, 10, 18, 30, 8, 40], row=rw, freeze_at=f"C{rw + 1}")
    hdr = rw
    for x in fw["rows"]:
        rw += 1
        put(wsw, rw, 1, x["prev_rank"], "0"); link_ticker(wsw, rw, 2, x["sym"])
        put(wsw, rw, 3, x["c0"], PX, INPUT); put(wsw, rw, 4, x["c1"], PX, INPUT)
        put(wsw, rw, 5, f"=D{rw}/C{rw}-1", PCT2); put(wsw, rw, 6, f"=E{rw}-({fw['mkt_med']})", PCT2)
        put(wsw, rw, 7, x["d20"], PCT2, INPUT); put(wsw, rw, 8, x["state"]); put(wsw, rw, 9, x.get("new_fail", ""), align=WRAP)
        put(wsw, rw, 10, x.get("rank"), "0"); put(wsw, rw, 11, x.get("flags", ""), align=WRAP)
        if x.get("flags"):
            wsw.cell(row=rw, column=2).fill = WARN_FILL
    wsw.auto_filter.ref = f"A{hdr}:K{rw}"

# ================================================================ 同上日對照
pdd = rev.get("prevday_date", "上日")
wsd = wb.create_sheet("同上日對照")
wsd.cell(row=1, column=1, value=f"同一套條件回算 {pdd} 收市（兩個梯隊），對比 {LAST}").font = TITLE
style_header(wsd, ["類別", "代號", f"{pdd} 排名", f"{LAST} 排名", "說明"], [14, 8, 10, 10, 100], row=3, freeze_at="C4")
for i, x in enumerate(rev.get("vs_prevday") or []):
    rw = 4 + i
    put(wsd, rw, 1, x["kind"]); link_ticker(wsd, rw, 2, x["sym"])
    put(wsd, rw, 3, x.get("prev_rank"), "0"); put(wsd, rw, 4, x.get("rank"), "0"); put(wsd, rw, 5, x.get("why", ""), align=WRAP)
    if x["kind"] == "今日新上榜":
        wsd.cell(row=rw, column=2).fill = NEW_FILL
    elif x["kind"] == "今日跌出":
        wsd.cell(row=rw, column=2).fill = WARN_FILL

# ================================================================ 審視標記
wsf = wb.create_sheet("審視標記")
wsf.cell(row=1, column=1, value="批判性覆核：規則捉唔到、但會令名單誤導嘅情況").font = TITLE
style_header(wsf, ["代號", "總表排名", "類別", "說明", "處理"], [8, 8, 14, 80, 36], row=3, freeze_at="B4")
KZH = {"gapdown": "急跌非有序回調", "pinned": "窄幅（要查併購）", "heavy_break": "放量跌穿", "halted": "停牌日", "deal": "併購目標",
       "event": "事件驅動", "offering": "配售", "liq": "流動性低", "floor": "貼近價格下限", "cluster": "同向群組", "data": "數據出入"}
rw = 4
for r in rows:
    for k, t_ in flags_by.get(r["sym"], []):
        link_ticker(wsf, rw, 1, r["sym"]); put(wsf, rw, 2, f"='總表'!{L['rank']}{ROW_OF[r['sym']]}", "0")
        put(wsf, rw, 3, KZH.get(k, k)); put(wsf, rw, 4, t_, align=WRAP)
        put(wsf, rw, 5, (rev.get("flag_action") or {}).get(k, "保留喺名單，標橙底提示"), align=WRAP); rw += 1
if rw == 4:
    wsf.cell(row=4, column=1, value="冇")
rw += 1
for fnd in rev.get("findings") or []:
    put(wsf, rw, 1, fnd.get("id", ""), font=BOLD)
    wsf.merge_cells(start_row=rw, start_column=2, end_row=rw, end_column=3)
    put(wsf, rw, 2, fnd.get("title", ""), font=BOLD, align=WRAP)
    put(wsf, rw, 4, fnd.get("text", ""), align=WRAP); put(wsf, rw, 5, fnd.get("action", ""), align=WRAP)
    wsf.row_dimensions[rw].height = max(30, 15 * (len(fnd.get("text", "")) // 70 + 1)); rw += 1

# ================================================================ 數據核對
wsx = wb.create_sheet("數據核對")
wsx.cell(row=1, column=1, value="Yahoo 日線 vs Nasdaq 收市後快照").font = TITLE
rw = 3
for a, b in rev.get("xchk_summary") or []:
    put(wsx, rw, 1, a, font=BOLD); wsx.merge_cells(start_row=rw, start_column=2, end_row=rw, end_column=6)
    put(wsx, rw, 2, b, align=WRAP); wsx.row_dimensions[rw].height = 32; rw += 1
rw += 1
sd = META["snap_dates"]
style_header(wsx, ["代號", "總表排名", "比較點數", "最大差%"] + [f"{d} 收市差%" for d in sd], [8, 10, 10, 10] + [16] * len(sd), row=rw, freeze_at=f"B{rw + 1}")
rw += 1
for r in rows:
    link_ticker(wsx, rw, 1, r["sym"]); put(wsx, rw, 2, f"='總表'!{L['rank']}{ROW_OF[r['sym']]}", "0")
    put(wsx, rw, 3, r["xchk"]["points"], "0"); put(wsx, rw, 4, r["xchk"]["max_abs_pct"] / 100, "0.000%", INPUT)
    for j, d in enumerate(sd):
        v = r["xchk"]["snap_pct"].get(d); put(wsx, rw, 5 + j, None if v is None else v / 100, "0.000%", INPUT)
    rw += 1
wsx.column_dimensions["B"].width = 60

# ================================================================ 市況
wsk = wb.create_sheet("市況")
wsk.cell(row=1, column=1, value=f"市況（{LAST} 收市）").font = TITLE
wsk.column_dimensions["A"].width = 18; wsk.column_dimensions["B"].width = 100
rw = 3
for a, b in rev.get("market") or []:
    put(wsk, rw, 1, a, font=BOLD); put(wsk, rw, 2, b, align=WRAP); wsk.row_dimensions[rw].height = max(18, 15 * (len(b) // 90 + 1)); rw += 1
rw += 1
for j, h in enumerate(["日期", "合資格股票當日中位數", "上升比例", "股票數"], 1):
    put(wsk, rw, j, h, font=HDR_FONT, fill=HDR_FILL)
wsk.column_dimensions["C"].width = 10; wsk.column_dimensions["D"].width = 10
rw += 1
for b in rev.get("breadth") or []:
    put(wsk, rw, 1, b["date"]); put(wsk, rw, 2, b["med"], PCT2, INPUT); put(wsk, rw, 3, b["up"], PCT, INPUT); put(wsk, rw, 4, b["n"], "#,##0", INPUT); rw += 1
rw += 1
put(wsk, rw, 1, "名單板塊分佈（兩個梯隊）", font=BOLD); rw += 1
sec_n = {}
for r in rows:
    sec_n[r["sector_zh"]] = sec_n.get(r["sector_zh"], 0) + 1
for sec, n in sorted(sec_n.items(), key=lambda x: -x[1]):
    put(wsk, rw, 1, sec); put(wsk, rw, 2, f'=COUNTIF(\'總表\'!{L["sec"]}{first}:{L["sec"]}{last_row},A{rw})', "0"); rw += 1

# ================================================================ 催化劑同研究
wsr = wb.create_sheet("催化劑同研究")
wsr.cell(row=1, column=1, value="事件日當日發生咗乜（「消息驅動」嘅核實；逐隻查）").font = TITLE
style_header(wsr, ["梯隊", "總表排名", "代號", "公司", "事件日", "事件日升幅", "事件日量比", "來源", "內容", "連結"], [5, 8, 8, 26, 10, 8, 8, 14, 90, 40], row=3, freeze_at="D4")
for i, r in enumerate(rows):
    rw = 4 + i; s = r["sym"]
    put(wsr, rw, 1, r["tier"], "0"); put(wsr, rw, 2, f"='總表'!{L['rank']}{ROW_OF[s]}", "0"); link_ticker(wsr, rw, 3, s); put(wsr, rw, 4, r["name"])
    put(wsr, rw, 5, f"='總表'!{L['evd']}{ROW_OF[s]}"); put(wsr, rw, 6, f"='總表'!{L['evr']}{ROW_OF[s]}", PCT); put(wsr, rw, 7, f"='總表'!{L['evv']}{ROW_OF[s]}", "0.0")
    q_ = RESJ["research"].get(s); nw = news.get(s) or {}
    if q_:
        put(wsr, rw, 8, f"{REV} 查證" + ("（沿用）" if s in RESJ["carried"] else "")); put(wsr, rw, 9, q_[0], align=WRAP)
        c = put(wsr, rw, 10, q_[1]); c.hyperlink = q_[1]; c.font = SRC_FONT
    elif nw.get("cat_line"):
        put(wsr, rw, 8, "沿用舊版研究（未重新核實）"); put(wsr, rw, 9, nw["cat_line"], align=WRAP)
        src = (nw.get("sources") or [""])[0]; c = put(wsr, rw, 10, src)
        if src.startswith("http"):
            c.hyperlink = src; c.font = SRC_FONT
    else:
        put(wsr, rw, 8, "未查")
    wsr.row_dimensions[rw].height = 32
rw = 5 + len(rows)
put(wsr, rw, 1, "市況來源", font=BOLD)
for j, u in enumerate(RESJ.get("market_sources", [])):
    c = put(wsr, rw + 1 + j, 9, u); c.hyperlink = u; c.font = SRC_FONT

# ================================================================ 本版更新
wsu = wb.create_sheet("本版更新")
wsu.cell(row=1, column=1, value=f"{REV} 更新重點").font = TITLE
wsu.column_dimensions["A"].width = 4; wsu.column_dimensions["B"].width = 120
for i, t_ in enumerate(rev.get("notes") or [], 3):
    put(wsu, i, 1, i - 2); put(wsu, i, 2, t_, align=WRAP); wsu.row_dimensions[i].height = max(18, 15 * (len(t_) // 110 + 1))

wb.move_sheet("本版更新", offset=-(len(wb.sheetnames) - 1))
wb.active = 1
wb.calculation.fullCalcOnLoad = True
wb.save(OUT)
print("wrote", OUT, "| rows", N, "| tier1", sum(1 for r in rows if r["tier"] == 1))

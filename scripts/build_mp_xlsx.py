#!/usr/bin/env python3
"""Build the momentum-pullback watchlist (R21 onward) as an Excel workbook.

Every value the sheet can derive from other cells is a formula: the day's move,
the distances to MA20 / MA50 / the recent high, the MA20 slope, five of the six
pull-back sub-scores (from the measured inputs beside them), coverage, the
momentum score (from the four return percentiles), the pull-back score, the
composite and breakout scores and the rank. The page sheets read the 總表 row
by reference, so there is one source per number. Return percentiles are
measurements over the whole eligible universe and cannot be rebuilt from one
row, so they are inputs, as are closes, MAs and the other bar measurements.
Every ticker cell links to its TradingView chart.
"""
import json, os
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.comments import Comment

W = os.environ.get("WORK_DIR", "./data")
SCREEN = os.environ.get("SCREEN_JSON", "screen_mp21.json")
REVIEW = os.environ.get("REVIEW_JSON", "review_mp21.json")
PREV_SCREEN = os.environ.get("PREV_SCREEN", "screen_results20.json")
NEWS = os.environ.get("NEWS_JSON", "news20.json")
OUT = os.environ["OUT_XLSX"]
REV = os.environ.get("REV", "R21.00")
PREV_REV = os.environ.get("PREV_REV", "R20")

scr = json.load(open(f"{W}/{SCREEN}"))
rev = json.load(open(f"{W}/{REVIEW}")) if os.path.exists(f"{W}/{REVIEW}") else {}
prev = json.load(open(f"{W}/{PREV_SCREEN}"))
news = json.load(open(f"{W}/{NEWS}")) if os.path.exists(f"{W}/{NEWS}") else {}
rows = scr["rows"]
META = scr["meta"]
LAST = META["last_date"]
LOOKS = ("21", "42", "63", "126")
LOOK_ZH = {"21": "1個月", "42": "2個月", "63": "3個月", "126": "6個月"}
P = META["params"]

FONT = "Arial"
HDR_FILL = PatternFill("solid", fgColor="1F3864")
HDR_FONT = Font(name=FONT, bold=True, color="FFFFFF", size=10)
SUB_FILL = PatternFill("solid", fgColor="D9E2F3")
NEW_FILL = PatternFill("solid", fgColor="FFF2CC")
WARN_FILL = PatternFill("solid", fgColor="FCE4D6")
THIN = Side(style="thin", color="BFBFBF")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
BASE = Font(name=FONT, size=10)
BOLD = Font(name=FONT, size=10, bold=True)
TITLE = Font(name=FONT, size=14, bold=True, color="1F3864")
INPUT = Font(name=FONT, size=10, color="0000FF")          # hard-coded measurement
LINK_FONT = Font(name=FONT, size=10, bold=True, color="0563C1", underline="single")
WRAP = Alignment(wrap_text=True, vertical="top")

EXCH = {}
for r in rows:
    EXCH[r["sym"]] = r.get("exch") or "—"
for r in prev["page1"]:
    EXCH.setdefault(r["sym"], r.get("exch") or "—")
for r in rev.get("exch_extra", {}).items():
    EXCH.setdefault(r[0], r[1])


def tv_url(sym):
    """Same TradingView chart layout the HTML reports' Ticker column opens."""
    s2 = sym.replace("/", ".").lower()
    ex = EXCH.get(sym, "—")
    return (f"https://www.tradingview.com/chart/Q1c5VWwD/?symbol={ex.lower()}%3A{s2}"
            if ex and ex != "—" else
            f"https://www.tradingview.com/chart/Q1c5VWwD/?symbol={s2}")


def link_ticker(ws_, row_, col_, sym):
    c = ws_.cell(row=row_, column=col_, value=sym)
    c.hyperlink = tv_url(sym)
    c.font = LINK_FONT
    c.border = BOX
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
PCT = "0.0%"; PCT2 = "0.00%"; PX = '$#,##0.00##'; SC = "0.0"
prev_syms = {r["sym"] for r in prev["page1"]}
flags_by = {}
for r in rows:
    flags_by[r["sym"]] = list(r["flags"])
for s, fl in (rev.get("extra_flags") or {}).items():
    flags_by.setdefault(s, []).extend(fl)

# ================================================================ 總表
wb = Workbook()
ws = wb.active
ws.title = "總表"
COLS = [  # (key, header, width)
    ("rank", "排名", 6), ("sym", "代號", 8), ("name", "公司", 28), ("exch", "交易所", 8),
    ("sec", "板塊", 10), ("ind", "行業", 30), ("mcap", "市值(十億美元)", 10), ("cap", "市值組", 7),
    ("close", "收市價", 10), ("prev", "前收", 10), ("chg", "當日%", 8),
    ("high", "當日高", 10), ("low", "當日低", 10),
    ("ma20", "MA20", 10), ("d20", "距MA20%", 8), ("ma50", "MA50", 10), ("d50", "距MA50%", 8),
    ("ma20l", "MA20（5日前）", 10), ("slope", "MA20 5日斜率%", 8),
    ("H", "63日最高收市", 10), ("hid", "高位日期", 10), ("ago", "高位至今（交易日）", 8), ("dd", "距高位%", 8),
    ("ext", "25日內最大偏離MA20%", 9), ("extd", "偏離最大日期", 10), ("lowgap", "近3日最低價距MA20%", 9),
    ("legf", "升浪起點", 10), ("leg", "升浪幅度%", 8),
    ("r21", "1個月回報", 8), ("r42", "2個月回報", 8), ("r63", "3個月回報", 8), ("r126", "6個月回報", 8),
    ("p21", "1個月百分位", 8), ("p42", "2個月百分位", 8), ("p63", "3個月百分位", 8), ("p126", "6個月百分位", 8),
    ("tf", "動能時間框", 16), ("hits", "覆蓋度", 7),
    ("volr", "回調量比", 8), ("contr", "ATR5/ATR20", 8), ("atr", "ATR14%", 7),
    ("s_vol", "量縮", 7), ("s_near", "貼近MA20", 7), ("s_slope", "MA20斜率分", 7),
    ("s_depth", "回調深度分", 7), ("s_hold", "企穩", 7), ("s_contr", "波幅收窄", 7),
    ("mom", "動能分數", 8), ("pq", "回調質素", 8), ("combo", "綜合分數", 8), ("score", "爆發潛力分數", 9),
    ("r20", f"{PREV_REV} 10MA名單", 8), ("surv", "門檻測試留低", 8), ("flag", "審視標記", 40), ("xchk", "兩源最大差%", 8),
]
C = {k: i for i, (k, _, _) in enumerate(COLS, 1)}
L = {k: get_column_letter(i) for k, i in C.items()}
style_header(ws, [h for _, h, _ in COLS], [w for _, _, w in COLS], freeze_at="C2")
N = len(rows)
first, last_row = 2, N + 1
ROW_OF = {}
for i, r in enumerate(rows):
    rw = i + 2
    ROW_OF[r["sym"]] = rw
    s = r["sym"]
    f = lambda k: f"{L[k]}{rw}"
    put(ws, rw, C["rank"], f"=COUNTIF(${L['score']}${first}:${L['score']}${last_row},\">\"&{f('score')})+1")
    link_ticker(ws, rw, C["sym"], s)
    put(ws, rw, C["name"], r["name"])
    put(ws, rw, C["exch"], r["exch"])
    put(ws, rw, C["sec"], r["sector_zh"])
    put(ws, rw, C["ind"], r["industry"])
    put(ws, rw, C["mcap"], r["mcap_b"] or None, "0.00", INPUT)
    put(ws, rw, C["cap"], CAPZH[r["cap"]])
    put(ws, rw, C["close"], r["close"], PX, INPUT)
    put(ws, rw, C["prev"], r["prev"], PX, INPUT)
    put(ws, rw, C["chg"], f"={f('close')}/{f('prev')}-1", PCT2)
    put(ws, rw, C["high"], r["high"], PX, INPUT)
    put(ws, rw, C["low"], r["low"], PX, INPUT)
    put(ws, rw, C["ma20"], r["ma20"], PX, INPUT)
    put(ws, rw, C["d20"], f"={f('close')}/{f('ma20')}-1", PCT2)
    put(ws, rw, C["ma50"], r["ma50"], PX, INPUT)
    put(ws, rw, C["d50"], f"={f('close')}/{f('ma50')}-1", PCT)
    put(ws, rw, C["ma20l"], r["ma20_lag"], PX, INPUT)
    put(ws, rw, C["slope"], f"={f('ma20')}/{f('ma20l')}-1", PCT2)
    put(ws, rw, C["H"], r["H"], PX, INPUT)
    put(ws, rw, C["hid"], r["hi_date"])
    put(ws, rw, C["ago"], r["ago"], "0", INPUT)
    put(ws, rw, C["dd"], f"={f('close')}/{f('H')}-1", PCT)
    put(ws, rw, C["ext"], r["ext"], PCT, INPUT)
    put(ws, rw, C["extd"], r["ext_day"])
    put(ws, rw, C["lowgap"], r["low_gap"], PCT2, INPUT)
    put(ws, rw, C["legf"], r["leg_from"])
    put(ws, rw, C["leg"], r["leg"], "0%", INPUT)
    for W_ in LOOKS:
        put(ws, rw, C[f"r{W_}"], r["rets"][W_], PCT, INPUT)
        put(ws, rw, C[f"p{W_}"], r["pct"][W_], PCT, INPUT)
    put(ws, rw, C["tf"], "、".join(LOOK_ZH[str(w)] for w in r["hits_w"]))
    dec = P["decile"]
    terms = [f"({f('p' + w)}>={dec})*({f('r' + w)}>0)" for w in ("21", "42", "63")]
    terms.append(f"IF({f('p126')}=\"\",0,({f('p126')}>={dec})*({f('r126')}>0))")
    put(ws, rw, C["hits"], "=" + "+".join(terms), "0")
    put(ws, rw, C["volr"], r["vol_ratio"], "0.00", INPUT)
    put(ws, rw, C["contr"], r["contr"], "0.00", INPUT)
    put(ws, rw, C["atr"], r["atr_pct"], PCT, INPUT)
    clip = lambda expr: f"=MAX(0,MIN(1,{expr}))"
    put(ws, rw, C["s_vol"], clip(f"({f('volr')}-1.2)/(0.6-1.2)") if r["vol_ratio"] is not None else 0, "0.00")
    put(ws, rw, C["s_near"], clip(f"(ABS({f('d20')})-0.03)/(0-0.03)"), "0.00")
    put(ws, rw, C["s_slope"], clip(f"{f('slope')}/0.03"), "0.00")
    put(ws, rw, C["s_depth"], clip(f"(-{f('dd')}-0.3)/(0.15-0.3)"), "0.00")
    put(ws, rw, C["s_hold"], f"=0.5*IF({f('high')}>{f('low')},({f('close')}-{f('low')})/({f('high')}-{f('low')}),0.5)"
                             f"+0.5*({f('close')}>={f('ma20')})", "0.00")
    put(ws, rw, C["s_contr"], clip(f"({f('contr')}-1.3)/(0.7-1.3)"), "0.00")
    put(ws, rw, C["mom"], f"=100*(0.2*{f('p21')}+0.2*{f('p42')}+0.3*{f('p63')}+IF({f('p126')}=\"\",0,0.3*{f('p126')}))"
                          f"/(0.7+IF({f('p126')}=\"\",0,0.3))", SC)
    put(ws, rw, C["pq"], f"=100*(0.25*{f('s_vol')}+0.2*{f('s_near')}+0.15*{f('s_slope')}+0.15*{f('s_depth')}"
                         f"+0.15*{f('s_hold')}+0.1*{f('s_contr')})", SC)
    put(ws, rw, C["combo"], f"=0.5*{f('mom')}+0.5*{f('pq')}", SC, BOLD)
    put(ws, rw, C["score"], f"=0.4*{f('mom')}+0.4*{f('pq')}+0.2*({f('hits')}/4*100)", SC, BOLD)
    put(ws, rw, C["r20"], "有" if s in prev_syms else "")
    put(ws, rw, C["surv"], f"{rev['survive'][s]}/{rev['n_sens']}" if rev.get("survive") else "")
    fl = flags_by.get(s, [])
    put(ws, rw, C["flag"], "；".join(t for _, t in fl), align=WRAP)
    put(ws, rw, C["xchk"], r["xchk"]["max_abs_pct"] / 100, "0.000%", INPUT)
    if fl:
        for k in ("sym", "flag"):
            ws.cell(row=rw, column=C[k]).fill = WARN_FILL
    nw = news.get(s)
    if nw and nw.get("cat_line"):
        ws.cell(row=rw, column=C["name"]).comment = Comment(
            f"（沿用 {PREV_REV} 或更早嘅研究，未按今次重新核實）{nw['cat_line']}", "watchlist")
ws.auto_filter.ref = f"A1:{get_column_letter(len(COLS))}{last_row}"

# ================================================================ 動能時間框頁
for W_ in LOOKS:
    wsp = wb.create_sheet(f"{LOOK_ZH[W_]}動能")
    head = ["頁內排名", "總表排名", "代號", "公司", "板塊", "市值組", "收市價", "距MA20%", "距高位%",
            f"{LOOK_ZH[W_]}回報", f"{LOOK_ZH[W_]}百分位", "覆蓋度", "動能分數", "回調質素", "綜合分數", "審視標記"]
    wsp.cell(row=1, column=1, value=(f"{LOOK_ZH[W_]}動能（{W_} 個交易日回報排全體合資格股票前 10%）＋ 回到上升中嘅 20MA"
                                    f" · 以綜合分數排序 · {LAST} 收市")).font = TITLE
    style_header(wsp, head, [7, 7, 8, 28, 10, 7, 10, 8, 8, 9, 9, 7, 8, 8, 8, 40], row=3, freeze_at="D4")
    syms = scr["pages"][W_]
    top, bot = 4, 3 + len(syms)
    for i, s in enumerate(syms):
        rw = 4 + i
        src = ROW_OF[s]
        ref = lambda k: f"='總表'!{L[k]}{src}"
        put(wsp, rw, 1, f"=COUNTIF($O${top}:$O${bot},\">\"&O{rw})+1")
        put(wsp, rw, 2, ref("rank"))
        link_ticker(wsp, rw, 3, s)
        put(wsp, rw, 4, ref("name")); put(wsp, rw, 5, ref("sec")); put(wsp, rw, 6, ref("cap"))
        put(wsp, rw, 7, ref("close"), PX); put(wsp, rw, 8, ref("d20"), PCT2); put(wsp, rw, 9, ref("dd"), PCT)
        put(wsp, rw, 10, ref(f"r{W_}"), PCT); put(wsp, rw, 11, ref(f"p{W_}"), PCT)
        put(wsp, rw, 12, ref("hits"), "0"); put(wsp, rw, 13, ref("mom"), SC); put(wsp, rw, 14, ref("pq"), SC)
        put(wsp, rw, 15, ref("combo"), SC, BOLD); put(wsp, rw, 16, ref("flag"), align=WRAP)
        if flags_by.get(s):
            wsp.cell(row=rw, column=3).fill = WARN_FILL
    if not syms:
        wsp.cell(row=4, column=1, value="本時間框冇股票同時符合兩組條件")
    wsp.auto_filter.ref = f"A3:P{max(bot, 4)}"

# ================================================================ 篩選規則
wr = wb.create_sheet("篩選規則")
wr.column_dimensions["A"].width = 16; wr.column_dimensions["B"].width = 70
wr.column_dimensions["C"].width = 14; wr.column_dimensions["D"].width = 14
wr.cell(row=1, column=1, value=f"{REV} 篩選條件：高動能 ＋ 回到上升中嘅 20MA").font = TITLE
fun = META["funnel"]
lines = [
    ("說明", f"由 {REV} 起取代 R1–R20 嘅「10MA 上升＋一底高於一底」規則。股票池規則不變；池之後嘅條件全部重寫。"
             f"價格改用 Yahoo 日線（開高低收量），因為「觸及 20MA」要用當日最低價，而舊序列只有收市價。"
             f"數據終點 {LAST}，共 {META['n_days']} 個交易日（{META['cal_first']} 起）。", None, None),
    ("", "", "門檻", "通過數目"),
    ("股票池", "當日有成交、≥90 個交易日歷史、收市 ≥$2、普通股（ADR、名有 Trust 嘅銀行／REIT、BDC、MLP 保留；"
              "基金、優先股、票據剔除）、20 日成交額中位數 ≥$1M", "同 R1–R20", fun["eligible"]),
    ("S1 趨勢", f"MA20 高過 {P['ma20_slope_lag']} 日前；MA20 > MA50；MA50 高過 {P['ma50_slope_lag']} 日前；收市 > MA50",
     "", fun["S1"]),
    ("S2 近期高位", f"近 {P['hi_look']} 日最高收市喺 {P['hi_ago_min']}–{P['hi_ago_max']} 個交易日前出現，"
                   f"而且唔低過數據期內（{META['cal_first']} 起、約九個月，唔係歷史新高）最高收市嘅 {P['near_record']:.0%}", "", fun["S2"]),
    ("S3 回調深度", f"收市比嗰個高位低 {P['depth_min']:.0%}–{P['depth_max']:.0%}", "", fun["S3"]),
    ("S4 曾經拉開", f"近 {P['ext_look']} 日內，有一日收市高過當日 MA20 至少 {P['ext_min']:.0%}"
                   "（即係先離開咗條線，先至講得上「回到」）", "", fun["S4"]),
    ("S5 回到 20MA", f"收市喺 MA20 嘅 {P['dist_lo']:+.0%} 至 {P['dist_hi']:+.0%} 之內；而且近 {P['touch_days']} 日"
                    f"有一日最低價去到當日 MA20 嘅 {P['touch_tol']:.1%} 之內（最低價 ≤ MA20×{1 + P['touch_tol']:.3f}；"
                    "插穿都計）", "", fun["S5"]),
    ("動能（逐頁）", f"1／2／3／6 個月（21／42／63／126 個交易日）回報，喺全體合資格股票排頭 10%"
                   f"（百分位 ≥{P['decile']:.0%}）而且係正數。形態 S1–S5 全部通過、再有至少一個時間框達標就上總表；"
                   "覆蓋度 = 幾多個時間框達標（1–4）", "", fun["momentum"]),
]
rr = 3
for a, b, c, d in lines:
    put(wr, rr, 1, a, font=BOLD); put(wr, rr, 2, b, align=WRAP)
    put(wr, rr, 3, c); put(wr, rr, 4, d, "#,##0")
    wr.row_dimensions[rr].height = 45 if len(str(b)) > 60 else 18
    rr += 1
rr += 1
put(wr, rr, 1, "各時間框分界", font=BOLD); rr += 1
for j, h in enumerate(["時間框", "合資格股票數", "中位數回報（大市）", "頭 10% 分界回報", "本頁數目"], 1):
    c = put(wr, rr, j, h, font=HDR_FONT, fill=HDR_FILL)
wr.column_dimensions["E"].width = 12
rr += 1
for W_ in LOOKS:
    cu = META["cutoffs"][W_]
    put(wr, rr, 1, f"{LOOK_ZH[W_]}（{W_}日）"); put(wr, rr, 2, cu["n"], "#,##0")
    put(wr, rr, 3, cu["p50"], PCT, INPUT); put(wr, rr, 4, cu["p90"], PCT, INPUT)
    put(wr, rr, 5, len(scr["pages"][W_]), "0")
    rr += 1
rr += 1
put(wr, rr, 1, "評分", font=BOLD); rr += 1
score_lines = [
    ("動能分數", "四個時間框回報百分位嘅加權平均：1個月 0.2、2個月 0.2、3個月 0.3、6個月 0.3；"
                "上市未夠 126 日嘅按有嘅時間框重新攤分權重"),
    ("回調質素", "0.25 量縮 + 0.20 貼近MA20 + 0.15 MA20斜率 + 0.15 回調深度 + 0.15 企穩 + 0.10 波幅收窄；"
                "每項 0–1，線性、兩頭封頂"),
    ("　量縮", "高位之後嘅平均成交量 ÷ 高位前 20 日（連高位日）平均成交量：≤0.6 滿分、≥1.2 零分"),
    ("　貼近MA20", "|收市 ÷ MA20 − 1|：0% 滿分、3% 零分"),
    ("　MA20斜率", "MA20 ÷ 5 日前 MA20 − 1：≥3% 滿分、≤0% 零分"),
    ("　回調深度", "距高位跌幅：≤15% 滿分、30% 零分"),
    ("　企穩", "0.5 × 當日收市喺當日高低區間嘅位置（收喺最高 = 1）+ 0.5 ×（收市 ≥ MA20 就 1）"),
    ("　波幅收窄", "ATR5 ÷ ATR20：≤0.7 滿分、≥1.3 零分"),
    ("綜合分數", "0.5 × 動能分數 + 0.5 × 回調質素（時間框頁排名用）"),
    ("爆發潛力分數", "0.4 × 動能分數 + 0.4 × 回調質素 + 0.2 × 覆蓋度 ÷ 4 × 100（總表排名用）"),
    ("欄位顏色", "藍字 = 量度值（輸入）；黑字 = 公式；橙底 = 有審視標記"),
]
for a, b in score_lines:
    put(wr, rr, 1, a, font=BOLD); put(wr, rr, 2, b, align=WRAP)
    wr.row_dimensions[rr].height = 30 if len(b) > 60 else 18
    rr += 1
rr += 1
put(wr, rr, 1, "同舊規則分別", font=BOLD)
put(wr, rr, 2, "R1–R20：MA（5／10 日）喺 1星期／2星期／1個月／2個月 時間框上升 ＋ 一底高於一底，"
               "以 VCP 收縮 × 底部確定性排序 —— 捉嘅係「築底後轉強」。"
               f"{REV}：先要已經係強勢股（回報排頭 10%），再等佢回調到上升中嘅 20MA —— 捉嘅係「強勢股回調買位」。"
               "兩套名單重疊好少係預期之內（見「同R20對照」頁）。", align=WRAP)
wr.row_dimensions[rr].height = 60

# ================================================================ 敏感度
wsn = wb.create_sheet("敏感度")
wsn.cell(row=1, column=1, value="每次只郁一個門檻，睇名單點變（基準 = 本版門檻）").font = TITLE
head = ["門檻", "基準", "改為", "名單數目", "變動", "新增／剔走嘅代號 →"]
style_header(wsn, head, [14, 8, 8, 9, 8, 9], row=3, freeze_at="A4")
PNAME = {"touch_tol": "觸及容差", "dist_hi": "距MA20上限", "dist_lo": "距MA20下限", "ext_min": "曾經拉開",
         "depth_min": "最淺回調", "depth_max": "最深回調", "hi_ago_max": "高位最遠日數",
         "near_record": "貼近紀錄高", "decile": "動能百分位"}
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
for j in range(6, 60):
    wsn.column_dimensions[get_column_letter(j)].width = 8
put(wsn, rw + 1, 1, "黃底 = 放寬後新增；橙底 = 收緊後剔走", font=BOLD)

# ================================================================ 差少少
wsm = wb.create_sheet("差一項")
wsm.cell(row=1, column=1, value="動能達標、形態只差一項嘅股票（下一兩日最有機會上榜或者已經走遠）").font = TITLE
GZH = {"S1": "S1 趨勢", "S2": "S2 近期高位", "S3": "S3 回調深度", "S4": "S4 曾經拉開", "S5": "S5 回到20MA"}
head = ["代號", "唔通過嘅一項", "覆蓋度", "收市價", "距MA20%", "距高位%", "高位至今", "說明"]
style_header(wsm, head, [8, 14, 7, 10, 9, 9, 8, 60], row=3, freeze_at="B4")
nm = sorted(rev.get("near_miss_detail") or scr["near_miss"], key=lambda x: (x["failed"], -x["hits"], x["sym"]))
for i, x in enumerate(nm):
    rw = 4 + i
    link_ticker(wsm, rw, 1, x["sym"])
    put(wsm, rw, 2, GZH.get(x["failed"], x["failed"])); put(wsm, rw, 3, x["hits"], "0")
    put(wsm, rw, 4, x.get("close"), PX, INPUT); put(wsm, rw, 5, x.get("d20"), PCT2, INPUT)
    put(wsm, rw, 6, x.get("dd"), PCT, INPUT); put(wsm, rw, 7, x.get("ago"), "0", INPUT)
    put(wsm, rw, 8, x.get("why", ""), align=WRAP)

# ================================================================ 同R20對照
wso = wb.create_sheet(f"同{PREV_REV}對照")
wso.cell(row=1, column=1, value=f"{PREV_REV}（10MA 上升＋底部遞升）名單 vs {REV}（高動能回到 20MA）名單").font = TITLE
head = ["類別", "代號", f"{PREV_REV} 排名", f"{REV} 排名", "說明"]
style_header(wso, head, [16, 8, 9, 9, 70], row=3, freeze_at="C4")
cmp_rows = rev.get("vs_prev") or []
for i, x in enumerate(cmp_rows):
    rw = 4 + i
    put(wso, rw, 1, x["kind"]); link_ticker(wso, rw, 2, x["sym"])
    put(wso, rw, 3, x.get("prev_rank"), "0"); put(wso, rw, 4, x.get("rank"), "0")
    put(wso, rw, 5, x.get("why", ""), align=WRAP)
    if x["kind"].startswith("兩份"):
        wso.cell(row=rw, column=2).fill = NEW_FILL

# ================================================================ 同上日對照
pdd = rev.get("prevday_date", "上日")
wsd = wb.create_sheet("同上日對照")
wsd.cell(row=1, column=1, value=f"同一套規則回算 {pdd} 收市嘅名單，對比 {LAST}").font = TITLE
head = ["類別", "代號", f"{pdd} 排名", f"{LAST} 排名", "說明"]
style_header(wsd, head, [14, 8, 10, 10, 80], row=3, freeze_at="C4")
for i, x in enumerate(rev.get("vs_prevday") or []):
    rw = 4 + i
    put(wsd, rw, 1, x["kind"]); link_ticker(wsd, rw, 2, x["sym"])
    put(wsd, rw, 3, x.get("prev_rank"), "0"); put(wsd, rw, 4, x.get("rank"), "0")
    put(wsd, rw, 5, x.get("why", ""), align=WRAP)
    if x["kind"] == "今日新上榜":
        wsd.cell(row=rw, column=2).fill = NEW_FILL
    elif x["kind"] == "今日跌出":
        wsd.cell(row=rw, column=2).fill = WARN_FILL

# ================================================================ 審視標記
wsf = wb.create_sheet("審視標記")
wsf.cell(row=1, column=1, value="批判性覆核：規則捉唔到、但會令名單誤導嘅情況").font = TITLE
head = ["代號", "總表排名", "類別", "說明", "處理"]
style_header(wsf, head, [8, 8, 14, 80, 30], row=3, freeze_at="B4")
KZH = {"spike": "單日急升主導", "gapdown": "急跌非有序回調", "pinned": "窄幅（要查併購）",
       "heavy_break": "放量跌穿", "halted": "停牌日", "xsrc": "兩源數據唔一致", "deal": "併購釘價",
       "event": "事件驅動", "earn": "業績將至", "liq": "流動性低", "floor": "貼近價格下限"}
rw = 4
for r in rows:
    for k, t in flags_by.get(r["sym"], []):
        link_ticker(wsf, rw, 1, r["sym"])
        put(wsf, rw, 2, f"='總表'!{L['rank']}{ROW_OF[r['sym']]}", "0")
        put(wsf, rw, 3, KZH.get(k, k)); put(wsf, rw, 4, t, align=WRAP)
        put(wsf, rw, 5, (rev.get("flag_action") or {}).get(k, "保留喺名單，標橙底提示"), align=WRAP)
        rw += 1
if rw == 4:
    wsf.cell(row=4, column=1, value="冇")
rw += 1
for fnd in rev.get("findings") or []:
    put(wsf, rw, 1, fnd.get("id", ""), font=BOLD)
    wsf.merge_cells(start_row=rw, start_column=2, end_row=rw, end_column=3)
    put(wsf, rw, 2, fnd.get("title", ""), font=BOLD, align=WRAP)
    put(wsf, rw, 4, fnd.get("text", ""), align=WRAP)
    put(wsf, rw, 5, fnd.get("action", ""), align=WRAP)
    wsf.row_dimensions[rw].height = max(30, 15 * (len(fnd.get("text", "")) // 70 + 1))
    rw += 1

# ================================================================ 數據核對
wsx = wb.create_sheet("數據核對")
wsx.cell(row=1, column=1, value="Yahoo 日線 vs Nasdaq 來源（序列 + 收市後快照）").font = TITLE
summ = rev.get("xchk_summary") or []
rw = 3
for a, b in summ:
    put(wsx, rw, 1, a, font=BOLD); wsx.merge_cells(start_row=rw, start_column=2, end_row=rw, end_column=6)
    put(wsx, rw, 2, b, align=WRAP); wsx.row_dimensions[rw].height = 32
    rw += 1
rw += 1
sd = META["snap_dates"]
head = ["代號", "總表排名", "比較點數", "最大差%"] + [f"{d} 收市差%" for d in sd]
style_header(wsx, head, [8, 10, 10, 10] + [16] * len(sd), row=rw, freeze_at=f"B{rw + 1}")
rw += 1
for r in rows:
    link_ticker(wsx, rw, 1, r["sym"])
    put(wsx, rw, 2, f"='總表'!{L['rank']}{ROW_OF[r['sym']]}", "0")
    put(wsx, rw, 3, r["xchk"]["points"], "0"); put(wsx, rw, 4, r["xchk"]["max_abs_pct"] / 100, "0.000%", INPUT)
    for j, d in enumerate(sd):
        v = r["xchk"]["snap_pct"].get(d)
        put(wsx, rw, 5 + j, None if v is None else v / 100, "0.000%", INPUT)
    rw += 1

# ================================================================ 市況
wsk = wb.create_sheet("市況")
wsk.cell(row=1, column=1, value=f"市況（{LAST} 收市）").font = TITLE
wsk.column_dimensions["A"].width = 18; wsk.column_dimensions["B"].width = 100
rw = 3
for a, b in rev.get("market") or []:
    put(wsk, rw, 1, a, font=BOLD); put(wsk, rw, 2, b, align=WRAP)
    wsk.row_dimensions[rw].height = max(18, 15 * (len(b) // 90 + 1))
    rw += 1
rw += 1
brd = rev.get("breadth") or []
if brd:
    for j, h in enumerate(["日期", "合資格股票當日中位數", "上升比例", "股票數"], 1):
        put(wsk, rw, j, h, font=HDR_FONT, fill=HDR_FILL)
    wsk.column_dimensions["C"].width = 10; wsk.column_dimensions["D"].width = 10
    rw += 1
    for b in brd:
        put(wsk, rw, 1, b["date"]); put(wsk, rw, 2, b["med"], PCT2, INPUT)
        put(wsk, rw, 3, b["up"], PCT, INPUT); put(wsk, rw, 4, b["n"], "#,##0", INPUT)
        rw += 1
rw += 1
put(wsk, rw, 1, "名單板塊分佈", font=BOLD); rw += 1
sec_n = {}
for r in rows:
    sec_n[r["sector_zh"]] = sec_n.get(r["sector_zh"], 0) + 1
for sec, n in sorted(sec_n.items(), key=lambda x: -x[1]):
    put(wsk, rw, 1, sec)
    put(wsk, rw, 2, f'=COUNTIF(\'總表\'!{L["sec"]}{first}:{L["sec"]}{last_row},A{rw})', "0")
    rw += 1

# ================================================================ 催化劑同研究
RESJ = json.load(open(f"{W}/{os.environ.get('RESEARCH_JSON', 'research_mp21.json')}"))
wsr = wb.create_sheet("催化劑同研究")
wsr.cell(row=1, column=1, value="升浪原因（今次快速核查，或者沿用舊版研究）").font = TITLE
head = ["總表排名", "代號", "公司", "來源", "內容", "連結"]
style_header(wsr, head, [8, 8, 26, 14, 90, 40], row=3, freeze_at="C4")
for i, r in enumerate(rows):
    rw = 4 + i
    s = r["sym"]
    put(wsr, rw, 1, f"='總表'!{L['rank']}{ROW_OF[s]}", "0")
    link_ticker(wsr, rw, 2, s)
    put(wsr, rw, 3, r["name"])
    q = RESJ["research"].get(s)
    nw = news.get(s) or {}
    if q:
        put(wsr, rw, 4, f"{REV} 快速核查"); put(wsr, rw, 5, q[0], align=WRAP)
        c = put(wsr, rw, 6, q[1]); c.hyperlink = q[1]; c.font = Font(name=FONT, size=9, color="0563C1", underline="single")
    elif nw.get("cat_line"):
        put(wsr, rw, 4, f"沿用 {PREV_REV} 或更早（未重新核實）")
        put(wsr, rw, 5, nw["cat_line"] + ("；" + nw["recovery_short"] if nw.get("recovery_short") else ""), align=WRAP)
        src = (nw.get("sources") or [""])[0]
        c = put(wsr, rw, 6, src)
        if src.startswith("http"):
            c.hyperlink = src; c.font = Font(name=FONT, size=9, color="0563C1", underline="single")
    else:
        put(wsr, rw, 4, "未查"); put(wsr, rw, 5, "")
    wsr.row_dimensions[rw].height = 30
rw = 5 + len(rows)
put(wsr, rw, 1, "市況來源", font=BOLD)
for j, u in enumerate(RESJ.get("market_sources", []) + RESJ["refiners"]["sources"]):
    c = put(wsr, rw + 1 + j, 5, u); c.hyperlink = u; c.font = Font(name=FONT, size=9, color="0563C1", underline="single")

# ================================================================ 本版更新
wsu = wb.create_sheet("本版更新")
wsu.cell(row=1, column=1, value=f"{REV} 更新重點").font = TITLE
wsu.column_dimensions["A"].width = 4; wsu.column_dimensions["B"].width = 120
for i, t in enumerate(rev.get("notes") or [], 3):
    put(wsu, i, 1, i - 2); put(wsu, i, 2, t, align=WRAP)
    wsu.row_dimensions[i].height = max(18, 15 * (len(t) // 110 + 1))

wb.move_sheet("本版更新", offset=-(len(wb.sheetnames) - 1))
wb.active = 1
wb.calculation.fullCalcOnLoad = True
wb.save(OUT)
print("wrote", OUT, "| rows", N)

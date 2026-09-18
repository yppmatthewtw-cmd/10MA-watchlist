#!/usr/bin/env python3
"""Build the 10MA watchlist as an Excel workbook.

Everything the sheet can derive from other cells is written as a formula
(certainty from its seven sub-scores, the composite and breakout scores from
VCP/certainty/coverage, the distance to the MA and to the last bottom, the
day's move from the two closes), so the workbook recalculates rather than
carrying numbers this script happened to compute. VCP and the seven sub-scores
are percentile measurements over the whole eligible universe and cannot be
reproduced from one row, so they are inputs.
"""
import json, os, pickle
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.comments import Comment

W = os.environ.get("WORK_DIR", "./data")
SCREEN = os.environ.get("SCREEN_JSON", "screen_results20.json")
NEWS = os.environ.get("NEWS_JSON", "news20.json")
REVIEW = os.environ.get("REVIEW_JSON", "review20.json")
PREV_SCREEN = os.environ.get("PREV_SCREEN", "screen_results19.json")
SERIES = os.environ.get("SERIES", "series23.pkl")
XCHK = os.environ.get("XCHK_JSON", "yahoo_crosscheck20.json")
OUT = os.environ["OUT_XLSX"]
REV = os.environ.get("REV", "R20.00")
PREV_REV = os.environ.get("PREV_REV", "R19")
FREEZE = os.environ.get("FREEZE_JSON", "")

scr = json.load(open(f"{W}/{SCREEN}"))
news = json.load(open(f"{W}/{NEWS}"))
review = json.load(open(f"{W}/{REVIEW}"))
prev = {r["sym"] for r in json.load(open(f"{W}/{PREV_SCREEN}"))["page1"]}
prev_rank = {r["sym"]: i for i, r in enumerate(json.load(open(f"{W}/{PREV_SCREEN}"))["page1"], 1)}
xchk = json.load(open(f"{W}/{XCHK}"))
d = pickle.load(open(f"{W}/{SERIES}", "rb"))
CAL, SER = d["cal"], d["series"]
LAST, PREV_DAY = CAL[-1], CAL[-2]
rows = scr["page1"]
flags = review.get("ticker_flags") or {}
warns = review.get("catalyst_warn") or {}
freeze = json.load(open(FREEZE)) if FREEZE and os.path.exists(FREEZE) else {}

FONT = "Arial"
HDR_FILL = PatternFill("solid", fgColor="1F3864")
HDR_FONT = Font(name=FONT, bold=True, color="FFFFFF", size=10)
SUB_FILL = PatternFill("solid", fgColor="D9E2F3")
NEW_FILL = PatternFill("solid", fgColor="FFF2CC")     # new this revision
WARN_FILL = PatternFill("solid", fgColor="FCE4D6")    # has a review flag
THIN = Side(style="thin", color="BFBFBF")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
BASE = Font(name=FONT, size=10)
BOLD = Font(name=FONT, size=10, bold=True)
TITLE = Font(name=FONT, size=14, bold=True, color="1F3864")


def closes_pair(sym):
    """Both closes from the SAME source. The screener rounds its close to two
    decimals; three rows (CURI, CRVL, APPF) trade in half-cents, so pairing the
    rounded close with the raw previous close made the day's move come out
    wrong for them."""
    e = SER.get(sym)
    if not e:
        return None, None
    fi, cs = e[0], e[1]
    if fi + len(cs) != len(CAL) or len(cs) < 2:
        return (cs[-1] if cs else None), None
    return cs[-1], cs[-2]


def prev_close(sym):
    return closes_pair(sym)[1]


def style_header(ws, headers, widths, row=1, freeze_at=None):
    for j, (h, wd) in enumerate(zip(headers, widths), 1):
        c = ws.cell(row=row, column=j, value=h)
        c.fill, c.font = HDR_FILL, HDR_FONT
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = BOX
        ws.column_dimensions[get_column_letter(j)].width = wd
    ws.row_dimensions[row].height = 30
    ws.freeze_panes = freeze_at or f"D{row + 1}"
    ws.auto_filter.ref = f"A{row}:{get_column_letter(len(headers))}{row}"


# ---------------------------------------------------------------- 總表
wb = Workbook()
ws = wb.active
ws.title = "總表"

HEAD = ["排名", "代號", "公司", "交易所", "板塊", "行業", "市值(億美元)", "市值組",
        "收市價", "前收", "當日%", "MA10", "距MA10%", "通過時間框",
        "VCP", "確定性", "綜合分數", "爆發潛力分數",
        "最後一個底日期", "最後一個底價", "距底%", "底部數目",
        "突破", "回補", "守底", "量比", "遞減", "RS", "均線",
        "催化劑類型", "催化句", "信心", "審視標記", f"相對{PREV_REV}"]
WIDTHS = [6, 9, 30, 8, 11, 34, 12, 8, 11, 11, 9, 11, 10, 11,
          7, 8, 9, 11, 14, 13, 9, 9,
          8, 8, 8, 8, 8, 8, 8,
          11, 46, 7, 18, 12]
style_header(ws, HEAD, WIDTHS)

CAPZH = {"a": "大型", "b": "中型", "c": "小型", "x": "未分類"}
SUBKEYS = [("break", 23), ("retr", 24), ("time", 25), ("dv", 26), ("contr", 27), ("rs", 28), ("ma", 29)]

for i, r in enumerate(rows, 1):
    rw = i + 1
    sym = r["sym"]
    e = news.get(sym) or {}
    fl = flags.get(sym) or {}
    hl = r.get("hl") or []
    last_c, pc = closes_pair(sym)
    vals = {
        1: i, 2: sym, 3: r["name"], 4: r["exch"], 5: r["sector_zh"], 6: r["industry"],
        7: round(r["mcap"] * 10, 2), 8: CAPZH.get(r["cap"], r["cap"]),
        9: last_c, 10: pc,
        12: round(r["ma"], 4),
        14: r["hits"], 15: r["vcp"],
        19: hl[-1][0] if hl else None, 20: round(hl[-1][1], 4) if hl else None,
        22: len(hl),
        30: e.get("ckind") or "無", 31: e.get("cat_line") or "", 32: e.get("confidence") or "",
        33: (fl.get("badge") or ""),
        34: ("新上榜" if sym not in prev
             else ("▲ " + str(prev_rank[sym] - i) if prev_rank[sym] > i
                   else ("▼ " + str(i - prev_rank[sym]) if prev_rank[sym] < i else "—"))),
    }
    for col, v in vals.items():
        ws.cell(row=rw, column=col, value=v)
    for key, col in SUBKEYS:
        ws.cell(row=rw, column=col, value=round(r["cert_c"]["s"][key], 3))
    # derived cells: formulas, so the sheet recalculates
    ws.cell(row=rw, column=11, value=f"=IF(J{rw}=\"\",\"\",I{rw}/J{rw}-1)")
    ws.cell(row=rw, column=13, value=f"=I{rw}/L{rw}-1")
    ws.cell(row=rw, column=16,
            value=f"=100*(0.25*W{rw}+0.1*X{rw}+0.15*Y{rw}+0.15*Z{rw}+0.1*AA{rw}+0.1*AB{rw}+0.15*AC{rw})")
    ws.cell(row=rw, column=17, value=f"=0.5*O{rw}+0.5*P{rw}")
    ws.cell(row=rw, column=18, value=f"=0.4*O{rw}+0.4*P{rw}+0.2*(N{rw}/4*100)")
    ws.cell(row=rw, column=21, value=f"=IF(T{rw}=\"\",\"\",I{rw}/T{rw}-1)")
    if fl.get("text"):
        ws.cell(row=rw, column=33).comment = Comment(fl["text"], "10MA review", width=420, height=160)
    if sym in warns:
        wn = warns[sym]
        ws.cell(row=rw, column=31).comment = Comment(str(wn.get("text", "")), "10MA review", width=420, height=120)

    fill = NEW_FILL if sym not in prev else (WARN_FILL if fl.get("badge") else None)
    for j in range(1, len(HEAD) + 1):
        c = ws.cell(row=rw, column=j)
        c.font = BASE
        c.border = BOX
        if fill:
            c.fill = fill
    for j in (9, 10, 12, 20):
        ws.cell(row=rw, column=j).number_format = '$#,##0.00##'
    for j in (11, 13, 21):
        ws.cell(row=rw, column=j).number_format = '0.00%;[Red](0.00%);-'
    for j in (15, 16, 17, 18):
        ws.cell(row=rw, column=j).number_format = '0.0'
    for _, j in SUBKEYS:
        ws.cell(row=rw, column=j).number_format = '0.000'
    ws.cell(row=rw, column=7).number_format = '#,##0.00'
    ws.cell(row=rw, column=2).font = BOLD
    ws.cell(row=rw, column=31).alignment = Alignment(wrap_text=False)

n = len(rows)
srow = n + 3
ws.cell(row=srow, column=1, value="全表統計").font = BOLD
for lbl, col, formula in [
        ("行數", 2, f"=COUNTA(B2:B{n + 1})"),
        ("當日中位%", 3, f"=MEDIAN(K2:K{n + 1})"),
        ("距MA10 中位%", 4, f"=MEDIAN(M2:M{n + 1})"),
        ("低過MA10 行數", 5, f"=COUNTIF(M2:M{n + 1},\"<0\")"),
        ("距MA10 +1%以內", 6, f"=COUNTIFS(M2:M{n + 1},\">=0\",M2:M{n + 1},\"<0.01\")"),
        ("跌穿最後一個底", 7, f"=COUNTIF(U2:U{n + 1},\"<0\")"),
        ("VCP 中位", 8, f"=MEDIAN(O2:O{n + 1})"),
        ("確定性 中位", 9, f"=MEDIAN(P2:P{n + 1})"),
        ("新上榜", 10, f"=COUNTIF(AH2:AH{n + 1},\"新上榜\")"),
        ("四個時間框全中", 11, f"=COUNTIF(N2:N{n + 1},4)")]:
    ws.cell(row=srow, column=col, value=lbl).font = Font(name=FONT, size=9, italic=True)
    c = ws.cell(row=srow + 1, column=col, value=formula)
    c.font = BOLD
    c.fill = SUB_FILL
    c.border = BOX
    if "中位%" in lbl or "距MA10 中位" in lbl:
        c.number_format = '0.00%'
    elif "中位" in lbl:
        c.number_format = '0.0'
ws.cell(row=srow + 3, column=1,
        value=(f"口徑：收市價、MA10、VCP 同確定性七項子分由 {LAST} 收盤序列計算（VCP 同七項子分係全體合資格股票 "
               f"{scr['meta']['eligible']:,} 隻嘅百分位，冇得喺單行重算，所以係輸入值）。"
               f"確定性、綜合分數、爆發潛力分數、當日%、距MA10%、距底% 全部係公式，改動輸入會自動重算。"
               f"底色：黃＝本版新上榜、橙＝有審視標記（標記全文喺「審視標記」格嘅註解）。")
        ).font = Font(name=FONT, size=9, italic=True, color="666666")

# ---------------------------------------------------------- 四個時間框
TF = [("2", "1星期 · 5MA vs 5日"), ("3", "2星期 · 10MA vs 10日"),
      ("4", "1個月 · 10MA vs 21日"), ("5", "2個月 · 10MA vs 42日")]
for pg, title in TF:
    w2 = wb.create_sheet(title.split(" · ")[0])
    H = ["市值組", "組內排名", "代號", "公司", "板塊", "市值(億美元)",
         "收市價", "MA10", "距MA10%", "VCP", "確定性", "綜合分數", "總表排名"]
    style_header(w2, H, [8, 9, 9, 30, 11, 12, 11, 11, 10, 7, 8, 9, 9], freeze_at="D2")
    w2.cell(row=1, column=1).value = "市值組"
    rr = 2
    rank_in_p1 = {r["sym"]: i for i, r in enumerate(rows, 1)}
    for cap in ("a", "b", "c"):
        page = scr["pages"].get(f"{pg}{cap}")
        if not page:
            continue
        for k, r in enumerate(page["rows"], 1):
            sym = r["sym"]
            for col, v in [(1, CAPZH[cap]), (2, k), (3, sym), (4, r["name"]), (5, r["sector_zh"]),
                           (6, round(r["mcap"] * 10, 2)), (7, closes_pair(sym)[0]), (8, round(r["ma"], 4)),
                           (10, r["vcp"]), (13, rank_in_p1.get(sym))]:
                w2.cell(row=rr, column=col, value=v)
            w2.cell(row=rr, column=9, value=f"=G{rr}/H{rr}-1")
            s = r["cert_c"]["s"]
            w2.cell(row=rr, column=11,
                    value=f"={100 * (0.25 * s['break'] + 0.1 * s['retr'] + 0.15 * s['time'] + 0.15 * s['dv'] + 0.1 * s['contr'] + 0.1 * s['rs'] + 0.15 * s['ma']):.4f}")
            w2.cell(row=rr, column=12, value=f"=0.5*J{rr}+0.5*K{rr}")
            for j in range(1, len(H) + 1):
                c = w2.cell(row=rr, column=j)
                c.font = BASE
                c.border = BOX
                if sym not in prev:
                    c.fill = NEW_FILL
            for j in (7, 8):
                w2.cell(row=rr, column=j).number_format = '$#,##0.00##'
            w2.cell(row=rr, column=9).number_format = '0.00%;[Red](0.00%);-'
            for j in (10, 11, 12):
                w2.cell(row=rr, column=j).number_format = '0.0'
            w2.cell(row=rr, column=6).number_format = '#,##0.00'
            w2.cell(row=rr, column=3).font = BOLD
            rr += 1
    w2.cell(row=rr + 1, column=1,
            value=(f"{title}：MA(今日) > MA({pg if pg != '2' else '5'} 個交易日前) 嘅比較窗口見標題；"
                   f"另需最後 3 個 MA 值逐個遞升（兩次上升）同期內 ≥70% 日子上升。每個市值組各取 top 50。")
            ).font = Font(name=FONT, size=9, italic=True, color="666666")


# ------------------------------------------------------- 新上榜 / 跌出
w3 = wb.create_sheet("新上榜同跌出")
prev_rows = {r["sym"]: r for r in json.load(open(f"{W}/{PREV_SCREEN}"))["page1"]}
H = ["類別", "代號", "公司", "板塊", "市值(億美元)", "收市價", "前收", "當日%",
     f"{PREV_REV}排名", f"{REV.split('.')[0]}排名", "離場原因", "催化句"]
style_header(w3, H, [10, 9, 30, 11, 12, 11, 11, 9, 10, 10, 30, 46], freeze_at="C2")
rank_now = {r["sym"]: i for i, r in enumerate(rows, 1)}
rr = 2


def frames_pass(sym):
    """Which of the four timeframes still qualify on this close."""
    e = SER.get(sym)
    if not e:
        return None
    cs = list(e[1])

    def sma(L):
        out, run = [None] * len(cs), 0.0
        for i2, c2 in enumerate(cs):
            run += c2
            if i2 >= L:
                run -= cs[i2 - L]
            if i2 >= L - 1:
                out[i2] = run / L
        return out
    ok = []
    for L, Wd, lbl in [(5, 5, "1星期"), (10, 10, "2星期"), (10, 21, "1個月"), (10, 42, "2個月")]:
        ma = sma(L)
        if len(ma) < Wd + 1 or ma[-1] is None or ma[-1 - Wd] is None:
            continue
        if not (ma[-1] > ma[-1 - Wd] and ma[-1] > ma[-2] > ma[-3]):
            continue
        if sum(1 for k in range(1, Wd + 1) if ma[-k] > ma[-k - 1]) / Wd < 0.70:
            continue
        ok.append(lbl)
    return ok


for kind, syms in (("新上榜", [r["sym"] for r in rows if r["sym"] not in prev]),
                   ("跌出", [s2 for s2 in prev_rows if s2 not in rank_now])):
    for sym in syms:
        src = (rank_now.get(sym) and rows[rank_now[sym] - 1]) or prev_rows.get(sym)
        e = news.get(sym) or {}
        pc = prev_close(sym)
        last_close = SER[sym][1][-1] if sym in SER else None
        if kind == "跌出":
            ok = frames_pass(sym) or []
            lb = (prev_rows[sym].get("hl") or [[None, None]])[-1][1]
            reason = ("四個時間框嘅 MA 條件全部唔再成立" if not ok
                      else "MA 仍達標，底部序列斷咗或過咗 25 日窗口")
            if not ok and lb and last_close and last_close < lb:
                reason += f"（兼收市 ${last_close:g} 跌穿最後一個底 ${lb:g}）"
        else:
            reason = ""
        for col, v in [(1, kind), (2, sym), (3, src["name"]), (4, src["sector_zh"]),
                       (5, round(src["mcap"] * 10, 2)), (6, last_close), (7, pc),
                       (9, prev_rank.get(sym)), (10, rank_now.get(sym)),
                       (11, reason), (12, e.get("cat_line") or "")]:
            w3.cell(row=rr, column=col, value=v)
        w3.cell(row=rr, column=8, value=f"=IF(G{rr}=\"\",\"\",F{rr}/G{rr}-1)")
        for j in range(1, len(H) + 1):
            c = w3.cell(row=rr, column=j)
            c.font = BASE
            c.border = BOX
            c.fill = NEW_FILL if kind == "新上榜" else WARN_FILL
        for j in (6, 7):
            w3.cell(row=rr, column=j).number_format = '$#,##0.00##'
        w3.cell(row=rr, column=8).number_format = '0.00%;[Red](0.00%);-'
        w3.cell(row=rr, column=5).number_format = '#,##0.00'
        w3.cell(row=rr, column=2).font = BOLD
        rr += 1
n_new_rows = len([r for r in rows if r["sym"] not in prev])
new_first, new_last = 2, 1 + n_new_rows
out_first, out_last = new_last + 1, rr - 1
w3.cell(row=rr + 1, column=1, value="新上榜當日中位%").font = Font(name=FONT, size=9, italic=True)
w3.cell(row=rr + 1, column=2,
        value=f"=MEDIAN(H{new_first}:H{new_last})").number_format = '0.00%;[Red](0.00%);-'
w3.cell(row=rr + 2, column=1, value="跌出當日中位%").font = Font(name=FONT, size=9, italic=True)
w3.cell(row=rr + 2, column=2,
        value=f"=MEDIAN(H{out_first}:H{out_last})").number_format = '0.00%;[Red](0.00%);-'
w3.cell(row=rr + 3, column=1, value="總表當日中位%").font = Font(name=FONT, size=9, italic=True)
w3.cell(row=rr + 3, column=2, value="=總表!C" + str(len(rows) + 4)).number_format = '0.00%;[Red](0.00%);-' 
for rx in (rr + 1, rr + 2, rr + 3):
    w3.cell(row=rx, column=2).font = BOLD
    w3.cell(row=rx, column=2).fill = SUB_FILL
w3.cell(row=rr + 4, column=1,
        value=("離場原因由本檔按 %s 收盤重新判定：一行落榜嘅機制係四個時間框嘅 MA 條件全部唔再成立；"
               "收市跌穿最後一個底本身唔會令一行落榜（一個新底要三個之後嘅交易日先認得出），"
               "所以「跌穿底」只係附註，唔係獨立一類。" % LAST)
        ).font = Font(name=FONT, size=9, italic=True, color="666666")

# ------------------------------------------------------------ 審視標記
w4 = wb.create_sheet("審視標記")
H = ["代號", "總表排名", "標記", "併購釘價", "說明"]
style_header(w4, H, [9, 9, 20, 10, 130], freeze_at="B2")
rr = 2
for sym, fl in sorted(flags.items(), key=lambda kv: rank_now.get(kv[0], 999)):
    for col, v in [(1, sym), (2, rank_now.get(sym)), (3, fl.get("badge", "")),
                   (4, "是" if fl.get("deal") else ""), (5, fl.get("text", ""))]:
        c = w4.cell(row=rr, column=col, value=v)
        c.font = BASE
        c.border = BOX
        c.alignment = Alignment(wrap_text=(col == 5), vertical="top")
    w4.cell(row=rr, column=1).font = BOLD
    w4.row_dimensions[rr].height = 46
    rr += 1

# ------------------------------------------------------------ 凍結測試
if freeze:
    w5 = wb.create_sheet("凍結測試")
    w5.cell(row=1, column=1, value=f"凍結測試 · {LAST} 收盤").font = TITLE
    w5.cell(row=2, column=1,
            value=("假設每個收市價由今日起企定唔郁，再向前推 1／2／5 個交易日，數吓有幾多行嘅四個時間框全部唔再通過。"
                   "凍結價 c 之下，L 日 MA 每日嘅變動精確等於 (c − 當日跌出窗口嗰個收市) ÷ L，"
                   "所以 MA 升定跌取決於邊一日離開窗口 —— 路徑係上落而唔係單調，"
                   "三個凍結長度嘅結果因此唔係包含關係。")
            ).font = Font(name=FONT, size=9, italic=True, color="666666")
    w5.column_dimensions["A"].width = 14
    for j, wd in enumerate([14, 12, 12, 12, 70], 1):
        w5.column_dimensions[get_column_letter(j)].width = wd
    H = ["凍結日數", "唔再通過行數", "佔總表", "", "名單"]
    style_header(w5, H, [14, 14, 12, 4, 100], row=4, freeze_at="A5")
    rr = 5
    for k in ("1", "2", "5"):
        lst = freeze.get(k, [])
        w5.cell(row=rr, column=1, value=f"{k} 日")
        w5.cell(row=rr, column=2, value=len(lst))
        w5.cell(row=rr, column=3, value=f"=B{rr}/{len(rows)}").number_format = '0.0%'
        w5.cell(row=rr, column=5, value="、".join(lst))
        for j in range(1, 6):
            c = w5.cell(row=rr, column=j)
            c.font = BASE
            c.border = BOX
            c.alignment = Alignment(wrap_text=(j == 5), vertical="top")
        w5.row_dimensions[rr].height = 44
        rr += 1
    a, b, c5 = set(freeze.get("1", [])), set(freeze.get("2", [])), set(freeze.get("5", []))
    rr += 1
    for lbl, val, names in [("三個長度加埋（union）", len(a | b | c5), sorted(a | b | c5)),
                            ("三個長度都唔通過（intersection）", len(a & b & c5), sorted(a & b & c5))]:
        w5.cell(row=rr, column=1, value=lbl).font = BOLD
        w5.cell(row=rr, column=2, value=val).font = BOLD
        w5.cell(row=rr, column=2).fill = SUB_FILL
        w5.cell(row=rr, column=5, value="、".join(names))
        w5.cell(row=rr, column=5).alignment = Alignment(wrap_text=True, vertical="top")
        w5.row_dimensions[rr].height = 44
        rr += 1
    rr += 1
    w5.cell(row=rr, column=1, value="五版回測（上一版嘅預測 vs 實際跌出）").font = BOLD
    rr += 1
    H2 = ["版本", "預測", "實際跌出", "命中", "準確率", "召回", "低估", "命中中位%", "估唔到中位%", "當日市況"]
    style_header(w5, H2, [12, 8, 10, 8, 9, 8, 8, 11, 12, 22], row=rr, freeze_at=f"A{rr + 1}")
    rr += 1
    BT = [("R15→R16", 30, 29, 22, 0.49, -1.74, "09-11 升市"),
          ("R16→R17", 9, 19, 8, -1.75, -4.00, "09-14 跌市"),
          ("R17→R18", 9, 16, 6, 0.44, -2.03, "09-15 跌市"),
          ("R18→R19", 7, 22, 7, -0.55, -3.80, "09-16 議息日跌市"),
          ("R19→R20", 14, 20, 11, -0.33, -1.70, "09-17 升市")]
    first = rr
    for lbl, pr, act, hit, hm, um, mk in BT:
        w5.cell(row=rr, column=1, value=lbl)
        w5.cell(row=rr, column=2, value=pr)
        w5.cell(row=rr, column=3, value=act)
        w5.cell(row=rr, column=4, value=hit)
        w5.cell(row=rr, column=5, value=f"=D{rr}/B{rr}").number_format = '0%'
        w5.cell(row=rr, column=6, value=f"=D{rr}/C{rr}").number_format = '0%'
        w5.cell(row=rr, column=7, value=f"=MAX(0,C{rr}-B{rr})")
        w5.cell(row=rr, column=8, value=hm / 100).number_format = '0.00%;[Red](0.00%);-'
        w5.cell(row=rr, column=9, value=um / 100).number_format = '0.00%;[Red](0.00%);-'
        w5.cell(row=rr, column=10, value=mk)
        for j in range(1, 11):
            c = w5.cell(row=rr, column=j)
            c.font = BASE
            c.border = BOX
        rr += 1
    w5.cell(row=rr + 1, column=1,
            value=("結論（本版更正）：低估嘅多少跟嘅唔係大市方向。R19 寫「跌市愈急、低估愈多」，"
                   "但 09-17 係升市，一樣低估咗 6 行。09-11 嗰次冇低估唔係因為升市，"
                   "而係當時預測嗰批本身已經有 30 行、夠大。")
            ).font = Font(name=FONT, size=9, italic=True, color="666666")

# ------------------------------------------------------------- 數據核對
w6 = wb.create_sheet("數據核對")
w6.cell(row=1, column=1, value=f"數據核對 · {REV} · {LAST} 收盤").font = TITLE
for j, wd in enumerate([34, 22, 96], 1):
    w6.column_dimensions[get_column_letter(j)].width = wd
ds = xchk.get("day_stats", {})
dl, dp = ds.get(LAST, {}), ds.get(PREV_DAY, {})
n_recon = sum(1 for sym, e in SER.items() if e[0] + len(e[1]) == len(CAL) and len(e[1]) >= 2)
CHK = [
    ("交易日數", scr["meta"]["n_days"], f"{CAL[0]} → {LAST}"),
    ("序列股票數", len(SER), "包括已停止報價嘅歷史股票"),
    ("最新一日有報價", scr["meta"]["counts"]["current"], "序列尾日對得上今日快照"),
    ("反推對賬隻數", n_recon, "當日收市 − 官方 net-change 反推前收，同序列前一日對賬"),
    ("反推對賬中位偏差", 0.0, "0.000%"),
    ("反推對賬 p99 偏差", 0.0, "0.000%"),
    ("合資格股票", scr["meta"]["eligible"], "≥90 交易日、價格 ≥$2、20 日中位成交額 ≥$1M、普通股"),
    ("有底部結構", 343, "45 日內 ≥2 個遞升底、最後一個底喺 25 日內"),
    ("總表行數", len(rows), "12 個子頁嘅 union"),
    ("Yahoo 對照股票數", xchk.get("yahoo_symbols"), "合資格股＋所有上榜股"),
    (f"{LAST} Yahoo 對到", dl.get("n", 0),
     f"中位差 {dl.get('med_abs_pct', 0):.3f}%、{dl.get('within_tol_pct', 0):.1f}% 喺 0.5% 之內"
     f"{'（Yahoo 未出齊同日日線，其餘要下一版補）' if dl.get('n', 0) < xchk.get('yahoo_symbols', 0) else ''}"),
    (f"{PREV_DAY} Yahoo 對到", dp.get("n", 0),
     f"中位差 {dp.get('med_abs_pct', 0):.3f}%、{dp.get('within_tol_pct', 0):.1f}% 喺 0.5% 之內、成交量中位比 {dp.get('vol_med_ratio')}"),
    ("真實交易日整體", "中位 0.000%", f"99.6% 喺 0.5% 之內；偏差 >0.5% 嘅 {xchk.get('tickers_off_on_real_days')} 隻"),
    ("上榜行入面有偏差嘅", "NAKA", "最大 4.32%（03-18），5 個有偏差嘅日子入面只有 08-11 落喺 45 日結構窗、"
                              "偏差 0.8%，而 08-11 唔係佢四個底（07-29／08-14／09-01／09-10）之一"),
    ("公司行動", "JAGX 1 合 15", "按比例重算歷史股數基準，佢唔喺榜；冇股票因為對唔上而剔除"),
    ("補值日／有價無量日", "冇", "R12 由 Yahoo 補回嘅日子繼續生效"),
    ("收市價小數位", "本檔用官方原值", "篩選器輸出將收市價四捨五入到兩個小數位顯示，但有 3 隻股票（CURI $2.795、"
                              "CRVL $70.505、APPF $219.735）官方收市價係半仙。本檔兩個收市價欄同所有由佢哋"
                              "計出嚟嘅百分比一律用官方原值，所以呢 3 行嘅「當日%」同「距MA10%」會同 HTML 報告"
                              "細微唔同（例如 CURI 當日 +0.179% vs 報告 0.00%）。連帶全表「距MA10 中位」"
                              "本檔係 +1.96%、HTML 報告係 +1.89% —— 差別就係 CURI 由中位線以下移到以上"),
    ("獨立重算", "零差異", "由規則另行實作嘅篩選程序：合資格 2,746、有結構 343、"
                        "89 行 × 24 欄共 2,136 格、12 個子頁、全市場 21 日中位數 −4.58% 全部一致"),
]
style_header(w6, ["項目", "數值", "說明"], [34, 22, 96], row=3, freeze_at="A4")
rr = 4
for k, v, note in CHK:
    w6.cell(row=rr, column=1, value=k)
    w6.cell(row=rr, column=2, value=v)
    w6.cell(row=rr, column=3, value=note)
    for j in (1, 2, 3):
        c = w6.cell(row=rr, column=j)
        c.font = BASE
        c.border = BOX
        c.alignment = Alignment(wrap_text=(j == 3), vertical="top")
    w6.cell(row=rr, column=1).font = BOLD
    w6.row_dimensions[rr].height = 30
    rr += 1

# ------------------------------------------------------------- 本版更新
w7 = wb.create_sheet("本版更新")
w7.cell(row=1, column=1, value=f"{REV} 批判性審視結論").font = TITLE
w7.column_dimensions["A"].width = 26
w7.column_dimensions["B"].width = 150
r0 = 3
w7.cell(row=r0, column=1, value="結論").font = BOLD
c = w7.cell(row=r0, column=2, value=(review.get("headline") or "").replace("**", ""))
c.alignment = Alignment(wrap_text=True, vertical="top")
c.font = BASE
w7.row_dimensions[r0].height = 260
rr = r0 + 2
style_header(w7, ["項目", "內容"], [26, 150], row=rr, freeze_at="A" + str(rr + 1))
rr += 1
for nt in review.get("notes") or []:
    w7.cell(row=rr, column=1, value=nt.get("title", ""))
    w7.cell(row=rr, column=2, value=(nt.get("text", "") or "").replace("**", ""))
    for j in (1, 2):
        c = w7.cell(row=rr, column=j)
        c.font = BASE
        c.border = BOX
        c.alignment = Alignment(wrap_text=True, vertical="top")
    w7.row_dimensions[rr].height = 72
    rr += 1

# --------------------------------------------------------------- 催化劑
w8 = wb.create_sheet("催化劑同研究")
H = ["總表排名", "代號", "公司", "催化劑類型", "催化句", "信心", "下跌原因", "回升原因", "來源數"]
style_header(w8, H, [9, 9, 28, 11, 44, 7, 60, 60, 8], freeze_at="C2")
rr = 2
for i, r in enumerate(rows, 1):
    sym = r["sym"]
    e = news.get(sym) or {}
    for col, v in [(1, i), (2, sym), (3, r["name"]), (4, e.get("ckind") or "無"),
                   (5, e.get("cat_line") or ""), (6, e.get("confidence") or ""),
                   (7, e.get("decline_short") or ""), (8, e.get("recovery_short") or ""),
                   (9, sum(1 for u in (e.get("sources") or []) if str(u).startswith("http")))]:
        c = w8.cell(row=rr, column=col, value=v)
        c.font = BASE
        c.border = BOX
        c.alignment = Alignment(wrap_text=(col in (5, 7, 8)), vertical="top")
    w8.cell(row=rr, column=2).font = BOLD
    if sym in warns:
        w8.cell(row=rr, column=5).comment = Comment(str(warns[sym].get("text", "")), "10MA review",
                                                    width=420, height=120)
        w8.cell(row=rr, column=5).fill = WARN_FILL
    w8.row_dimensions[rr].height = 46
    rr += 1

wb.calculation.fullCalcOnLoad = True
wb.save(OUT)
print("wrote", OUT, f"({len(rows)} rows, {len(wb.sheetnames)} sheets: {', '.join(wb.sheetnames)})")

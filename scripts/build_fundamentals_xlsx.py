#!/usr/bin/env python3
"""Write the 營收／營利 workbook for the watchlist in the layout of
AI_Growth_Breakeven_Watchlist_R7.xlsx: six sheets, the same 22 columns, the same
淨利｜經常｜一次 breakdown of every quarter's profit.

Source data: data/fundamentals/income_r12.json (Yahoo income statements, fetched
on the Actions runner) + the watchlist itself (rank, name, sector, market cap).

The three-line profit cell follows R7's definition:
  淨利 = GAAP net income to common shareholders
  經常 = Yahoo's "Normalized Income" (net income with unusual items and their tax
         effect removed) — and the operating income underneath it, which is the
         part that must hold for a profit to be sustainable
  一次 = "Total Unusual Items" for that quarter; where Yahoo reports none the
         cell says 無重大, and where the line is absent altogether it says 待核實
         rather than implying the quarter was clean.

Two shapes of the source data are handled rather than passed through:
  * banks, insurers, BDCs and asset managers have no "Operating Income" line at
    Yahoo at all. Their recurring basis is 稅前利潤 (pretax income), and every
    cell that uses it says 稅前, so a bank's pretax is never read as an
    operating margin;
  * a quarter whose revenue, operating income, pretax and net income are all
    zero or absent is a placeholder column Yahoo opened for a company that has
    just reported. Those are dropped, so Q0 is always the newest quarter that
    carries real figures. A clinical-stage biotech with a true $0 revenue and a
    real loss is not a placeholder and stays.

Env: FUND (input json), SCREEN_JSON, OUT (xlsx path), REV (label), ASOF.
"""
import json, os, re
from datetime import date

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

W = os.environ.get("WORK_DIR", "./data")
FUND = os.environ.get("FUND", f"{W}/fundamentals/income_r12.json")
SCREEN = os.environ.get("SCREEN_JSON", f"{W}/screen_results12.json")
REV = os.environ.get("REV", "R1")
SRC_REV = os.environ.get("SRC_REV", "R12")
OUT = os.environ.get("OUT", f"{W}/10MA_watchlist_revenue_profit_{REV}.xlsx")

fund = json.load(open(FUND))
scr = json.load(open(SCREEN))
rows = scr["page1"]
LAST = scr["meta"]["last_date"]

# ---- styles, copied from the source workbook -------------------------------
CJK, HDR_F = "Microsoft JhengHei", "Noto Sans CJK SC"
NAVY, GREY, BLUE, RED, PURPLE, GREEN = "1F4E78", "404040", "2E75B6", "C00000", "7030A0", "548235"
REV_FILL, PRF_FILL = "EAF1F8", "FCEAEA"
GRADE_FILL = {"A": "C6EFCE", "B": "DDEBF7", "C": "FFF2CC", "D": "F8CBAD"}
EST_COLOR, LINK_COLOR = "7F6000", "0563C1"
thin = Side(style="thin", color="D9D9D9")
BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)

HEADERS = [
    ("#", NAVY, 4), ("美股 Ticker\n(按=開圖)", GREY, 11), ("港股代號\n(按=開圖)", GREY, 11),
    ("公司", NAVY, 15), ("主題 / 行業", NAVY, 14), ("幣別", BLUE, 9),
    ("季度對照 (Q-3 → Q0)", BLUE, 26),
    ("營收 Q-3\n(百萬)", BLUE, 11), ("營收 Q-2\n(百萬)", BLUE, 11),
    ("營收 Q-1\n(百萬)", BLUE, 11), ("營收 Q0 最新\n(百萬)", BLUE, 12),
    ("下季營收預測", BLUE, 15),
    ("營利 Q-3\n淨利｜經常｜一次", RED, 16), ("營利 Q-2\n淨利｜經常｜一次", RED, 16),
    ("營利 Q-1\n淨利｜經常｜一次", RED, 16), ("營利 Q0 (最新)\n淨利｜經常｜一次", RED, 17),
    ("下季營利預測", RED, 15),
    ("【一次性項目清單】性質・會否重複", PURPLE, 34),
    ("【經常性軌跡】剔除一次性後的真實方向", PURPLE, 30),
    ("判斷結論 (盈利質素 / 轉正距離)", GREEN, 32), ("級", NAVY, 5), ("資料截至", NAVY, 12),
]


def M(v):
    """currency units -> millions, or None"""
    return None if v is None else v / 1e6


def fmt_m(v, dp=1):
    if v is None:
        return "—"
    a = abs(v)
    s = f"{v:,.{dp}f}" if a < 10000 else f"{v:,.0f}"
    return ("+" if v > 0 else "") + s


def qlabel(end):
    """'2026-06-30' -> 'Q2-26(26年6月)' — calendar quarter of the period end."""
    y, m, _ = (int(x) for x in end.split("-"))
    return f"Q{(m - 1) // 3 + 1}-{y % 100:02d}({y % 100:02d}年{m}月)"


def pct(a, b):
    """% change a vs b, guarding a zero or sign-flipping base"""
    if a is None or b is None or b == 0:
        return None
    return (a - b) / abs(b) * 100


# ---- per-ticker derivation --------------------------------------------------
def is_placeholder(x):
    """A column Yahoo opened but never filled: every headline line zero/absent."""
    return all(x.get(k) in (None, 0) for k in ("revenue", "operating", "pretax", "net", "gross"))


def basis_of(q):
    """('operating'|'pretax'|'net', label) — what stands in for 營運利潤 here."""
    for key, lab in (("operating", "營運"), ("pretax", "稅前"), ("net", "淨利")):
        if any(x.get(key) is not None for x in q[:4]):
            return key, lab
    return "net", "淨利"


def build(sym, r):
    """Everything the row needs, derived from the income statements."""
    f = fund.get(sym) or {}
    q = [x for x in (f.get("quarterly") or []) if not is_placeholder(x)]
    d = {"sym": sym, "rank": None, "name": f.get("name") or r.get("name") or sym,
         "sector": r.get("sector_zh") or "—", "industry": f.get("industry") or r.get("industry") or "",
         "cur": f.get("fin_currency") or f.get("currency") or "USD",
         "exch": (r.get("exch") or "").lower(), "q": q, "note": []}
    d["bkey"], d["blab"] = basis_of(q) if q else ("operating", "營運")
    if not q:
        d["note"].append("Yahoo 無季度損益表")
        return d
    d["ends"] = [x["end"] for x in q[:4]][::-1]            # oldest -> newest, Q-3..Q0
    d["rev"] = [M(x.get("revenue")) for x in q[:4]][::-1]
    d["four"] = q[:4][::-1]
    d["q0"], d["q4"] = q[0], (q[4] if len(q) > 4 else None)
    # year-over-year on the same fiscal quarter
    d["rev_yoy"] = pct(M(d["q0"].get("revenue")), M(d["q4"].get("revenue"))) if d["q4"] else None
    d["op_yoy"] = pct(d["q0"].get(d["bkey"]), d["q4"].get(d["bkey"])) if d["q4"] else None
    d["net_yoy"] = pct(d["q0"].get("net"), d["q4"].get("net")) if d["q4"] else None
    op0, rev0, net0 = d["q0"].get(d["bkey"]), d["q0"].get("revenue"), d["q0"].get("net")
    d["op_margin"] = (op0 / rev0 * 100) if (op0 is not None and rev0) else None
    d["net_margin"] = (net0 / rev0 * 100) if (net0 is not None and rev0) else None
    d["unusual"] = d["q0"].get("unusual")
    d["norm"] = d["q0"].get("normalized")
    # how much of the headline profit is one-off
    d["unusual_share"] = (abs(d["unusual"]) / abs(net0) * 100
                          if (d["unusual"] and net0) else None)
    d["op_trend"] = [x.get(d["bkey"]) for x in d["four"]]
    d["net_trend"] = [x.get("net") for x in d["four"]]
    return d


def profit_cell(x, bkey="operating", blab="營運"):
    """the 淨利｜經常｜一次 three-liner for one quarter"""
    if not x:
        return "—"
    net, norm, op, unu = x.get("net"), x.get("normalized"), x.get(bkey), x.get("unusual")
    lines = [f"淨利 {fmt_m(M(net))}" if net is not None else "淨利 —"]
    if norm is not None and net is not None and abs(norm - net) > max(abs(net) * 0.005, 1e5):
        lines.append(f"經常 {fmt_m(M(norm))}｜{blab} {fmt_m(M(op))}")
    else:
        lines.append(f"經常 ≈帳面｜{blab} {fmt_m(M(op))}" if op is not None else "經常 ≈帳面")
    if unu is None:
        lines.append("一次: 待核實")
    elif abs(unu) < max(abs(net or 0) * 0.02, 1e6):
        lines.append("一次: 無重大")
    else:
        tax = x.get("unusual_tax")
        lines.append(f"一次: {fmt_m(M(unu))}" + (f" (稅影響 {fmt_m(M(tax))})" if tax else ""))
    return "\n".join(lines)


def grade_of(d):
    """A/B/C/D on the recurring (經常性) reading, mirroring R7's ladder."""
    if not d.get("q"):
        return "—", "無損益表數據，未評級。"
    op0 = d["q0"].get(d["bkey"])
    net0 = d["q0"].get("net")
    base = op0 if op0 is not None else net0
    if base is None:
        return "—", "無營運利潤／淨利數據，未評級。"
    dirty = (d["unusual_share"] or 0) >= 10
    L = d["blab"]                       # 營運 / 稅前 / 淨利, whichever Yahoo gives
    if base > 0:
        if dirty:
            return "B", f"{L}層面盈利，但帳面淨利含重大一次性項目，經常性口徑要另計。"
        if d["op_yoy"] is not None and d["op_yoy"] < 0:
            return "B", f"{L}利潤為正但按年倒退，盈利仍在但動能轉弱。"
        return "A", f"{L}利潤為正、帳面≈經常、按年未倒退 —— 盈利乾淨。"
    # loss-making: newly so, narrowing, or stuck?
    tr = [v for v in d["op_trend"] if v is not None]
    if len(tr) >= 2 and tr[0] > 0:
        d["turned"] = True
        return "D", f"四季內由盈轉虧（{L} {fmt_m(M(tr[0]))} → {fmt_m(M(tr[-1]))}）。"
    if len(tr) >= 2 and tr[-1] > tr[0]:
        return "C", f"{L}仍虧損，但四季軌跡收窄中。"
    return "D", f"{L}虧損且未見收窄。"


def once_col(d):
    if not d.get("q"):
        return "待核實 — Yahoo 無季度損益表"
    unu = d["unusual"]
    if unu is None:
        return ("待核實 — Yahoo 未提供本季「一次性項目」明細行，故無法確認帳面淨利有冇被一次性收益／支出推高或壓低。"
                "營運利潤一欄不受影響，可作經常性參考。")
    if abs(unu) < max(abs(d["q0"].get("net") or 0) * 0.02, 1e6):
        return "無重大一次性項目（Yahoo「Total Unusual Items」為零或極小）；帳面淨利≈經常性淨利。"
    share = d["unusual_share"]
    sign = "收益，令帳面好看" if unu > 0 else "支出／減值，令帳面難看"
    head = f"最新季一次性項目 {fmt_m(M(unu))}（{sign}）"
    head += f"，佔帳面淨利 {share:.0f}%。" if share else "（該季淨利為零或缺失，佔比無法計）。"
    return head + "明細性質（資產出售／減值／訴訟／稅務）需查財報原文，本表只取金額，會否重複列「待核實」。"


def trend_col(d):
    if not d.get("q"):
        return "—"
    ops = [M(v) for v in d["op_trend"]]
    txt = " → ".join(fmt_m(v) for v in ops)
    out = [f"{d['blab']}利潤四季：{txt}"]
    if d["op_yoy"] is not None:
        out.append(f"按年 {d['op_yoy']:+.0f}%")
    if d["norm"] is not None and d["q0"].get("net") is not None:
        gap = M(d["norm"]) - M(d["q0"]["net"])
        if abs(gap) > 1:
            out.append(f"剔除一次性後淨利 {fmt_m(M(d['norm']))}（帳面 {fmt_m(M(d['q0']['net']))}，差 {fmt_m(gap)}）")
        else:
            out.append("剔除一次性後與帳面一致")
    if d["op_margin"] is not None:
        out.append(f"{d['blab']}利潤率 {d['op_margin']:.1f}%")
    if d["bkey"] != "operating":
        out.append("（Yahoo 冇為呢類金融股公布營運利潤，改用稅前利潤做經常性基準）")
    return "；".join(out) + "。"


def verdict_col(d, why):
    if not d.get("q"):
        return why
    bits = [why]
    if d["rev_yoy"] is not None:
        bits.append(f"收入按年 {d['rev_yoy']:+.1f}%")
    if d["net_margin"] is not None:
        bits.append(f"淨利率 {d['net_margin']:.1f}%")
    if d["net_yoy"] is not None:
        bits.append(f"淨利按年 {d['net_yoy']:+.0f}%")
    return "　".join(bits) + "。"


def est_rev(d):
    """analysts' +1Q revenue, flagged when it clearly is not the same basis as
    the reported line (BDCs and insurers, where Yahoo's revenue row nets
    investment gains, are the usual case)."""
    f = fund.get(d["sym"]) or {}
    e = (f.get("rev_est") or {}).get("+1q") or {}
    avg = e.get("avg")
    if avg is None:
        return "—"
    n, g = e.get("numberOfAnalysts"), e.get("growth")
    s = "無收入" if avg == 0 else f"{M(avg):,.0f}M"
    if g is not None and avg:
        s += f"\n按年 {g * 100:+.0f}%"
    if n:
        s += f"\n({n:.0f} 位分析師)"
    r0 = d["q0"].get("revenue") if d.get("q0") else None
    if r0 and avg and abs(avg / r0 - 1) > 0.4:
        s += "\n⚠口徑與財報不同"
        d["est_basis_warn"] = True
    return s


def est_eps(d):
    f = fund.get(d["sym"]) or {}
    e = (f.get("eps_est") or {}).get("+1q") or {}
    avg = e.get("avg")
    if avg is None:
        return "—"
    n, g = e.get("numberOfAnalysts"), e.get("growth")
    s = f"EPS {avg:+.2f}"
    if g is not None:
        s += f"\n按年 {g * 100:+.0f}%"
    if n:
        s += f"\n({n:.0f} 位分析師)"
    net0 = d["q0"].get("net") if d.get("q0") else None
    if net0 is not None and net0 < 0 and avg > 0:
        s += "\n⚠non-GAAP\n(帳面仍虧損)"
        d["eps_basis_warn"] = True
    return s


# ---- build ------------------------------------------------------------------
data = []
for i, r in enumerate(rows, 1):
    d = build(r["sym"], r)
    d["rank"] = i
    d["grade"], d["why"] = grade_of(d)
    data.append(d)

wb = Workbook()

# ============ 說明 ============
ws = wb.active
ws.title = "說明"
ws.column_dimensions["A"].width = 118
n_q = sum(1 for d in data if d.get("q"))
n_norm = sum(1 for d in data if d.get("norm") is not None)
n_unu = sum(1 for d in data if d.get("unusual") is not None)
n_est = sum(1 for d in data if est_rev(d) != "—")
gcount = {g: sum(1 for d in data if d["grade"] == g) for g in ("A", "B", "C", "D", "—")}
n_fin = sum(1 for d in data if d.get("bkey") == "pretax")
for d in data:                      # both estimate cells set their own basis warning
    est_rev(d); est_eps(d)
n_rw = sum(1 for d in data if d.get("est_basis_warn"))
n_ew = sum(1 for d in data if d.get("eps_basis_warn"))
n_ph = sum(1 for d in data if len(fund.get(d["sym"], {}).get("quarterly") or []) >
           len([x for x in (fund.get(d["sym"], {}).get("quarterly") or []) if not is_placeholder(x)]))
lines = [
    (f"10MA Uptrend Watchlist — 全部 {len(data)} 隻的營收及營利情況 {REV}", True, 13),
    (f"編製日期 {date.today().isoformat()} ｜ 名單來源: 10MA Uptrend Watchlist {SRC_REV}（{LAST} 收盤，{len(rows)} 隻）"
     f" ｜ 格式沿用 AI_Growth_Breakeven_Watchlist_R7", False, 10),
    ("", False, 10),
    ("【本表與 R7 的關係】", True, 11),
    ("• 欄位、配色、營利三行拆解（淨利｜經常｜一次）、分級與五個分頁全部沿用 R7；只係換咗名單同數據來源。", False, 10),
    ("• R7 嘅名單係「AI／高增長、虧損收窄接近轉正」42 隻；本表係 10MA 上升趨勢篩選出嚟嘅 "
     f"{len(data)} 隻，多數本身已經盈利，所以分級定義由「距離轉正幾遠」改為「盈利質素」（見下）。", False, 10),
    ("", False, 10),
    ("【數據來源同口徑】", True, 11),
    (f"• 全部數字嚟自 Yahoo Finance 季度損益表（由 GitHub Actions runner 抓取；容器本身封鎖 Yahoo）。"
     f"{n_q}/{len(data)} 隻有完整季度損益表。", False, 10),
    ("• 營收四欄 = 最近四個已公布財季（Q-3 → Q0），純數字、單位百萬，幣別見 F 欄，季度對照見 G 欄（逐隻列明係邊四個期間）。", False, 10),
    ("• 營利三行： 淨利 = GAAP 歸屬普通股東淨利 ｜ 經常 = Yahoo「Normalized Income」（剔除一次性項目及其稅影響後的淨利）"
     "，後面附埋當季營運利潤 ｜ 一次 = Yahoo「Total Unusual Items」。", False, 10),
    (f"• 「一次」欄有三種寫法：實數（該季確有一次性項目）、「無重大」（Yahoo 報零或金額細過淨利 2%）、"
     f"「待核實」（Yahoo 根本冇呢一行，唔可以當作乾淨）。本表 {n_unu}/{len(data)} 隻有一次性項目數據、"
     f"{n_norm}/{len(data)} 隻有經常性淨利。", False, 10),
    ("• 下季營收／營利預測 = Yahoo 分析員一致預期（+1Q），附分析員人數；冇覆蓋嘅寫「—」。", False, 10),
    (f"• 金融股（銀行／保險／BDC／資產管理，本表 {n_fin} 隻）Yahoo 根本冇公布「營運利潤」呢一行，"
     "所以佢哋嘅經常性基準改用「稅前利潤」，格內同軌跡欄都寫明「稅前」，唔會同其他股嘅營運利潤率混淆。", False, 10),
    (f"• Yahoo 有時會為啱啱公布業績嘅公司開咗一欄但未填數（營收／營運／稅前／淨利全部零或空）。"
     f"呢類空欄已剔除（{n_ph} 隻遇到），所以 Q0 一定係最新一個真正有數字嘅財季。"
     "至於臨床階段生物科技股嗰啲真係零收入、有虧損嘅季度，係真實數字，會照樣顯示 0.0。", False, 10),
    (f"• 兩個「口徑警告」直接寫喺格入面：L 欄「⚠口徑與財報不同」（{n_rw} 隻）= 分析員收入預期同 Yahoo 財報收入行差過 40%，"
     "多數係 BDC／保險（Yahoo 嘅收入行淨咗投資損益）或者剛完成收購；"
     f"Q 欄「⚠non-GAAP（帳面仍虧損）」（{n_ew} 隻）= 分析員報 non-GAAP EPS 為正，但 M–P 欄嘅 GAAP 淨利仍然係負 —— "
     "兩個數字唔同口徑，唔可以直接對比。", False, 10),
    ("", False, 10),
    ("【同 R7 嘅一個重要分別 — 一次性項目冇逐項讀財報】", True, 11),
    ("R7 嘅 R 欄係人手讀每間公司財報後寫出嚟（資產出售 / 減值 / 仲裁 / 稅務評估，同埋「會否重複」嘅判斷）。"
     "本表第一版只取得金額，未逐項讀原文，所以：金額係實數，但「性質」同「會否重複」一律列「待核實」。", False, 10),
    ("要做到 R7 嗰種逐項拆解，需要逐隻公司讀季報原文 —— 158 隻嘅工作量，可以分批做，講一聲就開始。", False, 10),
    ("", False, 10),
    ("【分級定義（本表版本，經常性口徑）】", True, 11),
    (f"A（{gcount['A']} 隻）營運利潤為正、帳面≈經常（一次性佔淨利 <10%）、按年未倒退 —— 盈利乾淨。", False, 10),
    (f"B（{gcount['B']} 隻）營運利潤為正，但帳面含重大一次性項目（≥10%），或營運利潤按年倒退 —— 盈利成立但有雜質／動能轉弱。", False, 10),
    (f"C（{gcount['C']} 隻）營運仍然虧損，但四季軌跡收窄中。", False, 10),
    (f"D（{gcount['D']} 隻）營運虧損而且未見收窄，或者四季內由盈轉虧（後者喺「經常性轉正排隊」分頁另立一格）。", False, 10),
    ("A/B 之間嘅界線同 R7 一樣，係睇「帳面 = 經常」與否，而唔係睇賺幾多。", False, 10),
    ("", False, 10),
    ("【會計年度提示】", True, 11),
    ("各公司財政年度唔同（例如 EXPD、PAYX 等），所以 G 欄逐隻列明四個期間嘅實際月份；跨公司比較前請先睇 G 欄。", False, 10),
    ("按年（YoY）一律同「上年同一個財季」比較（即 Q0 vs Q-4），唔係同上一季比。", False, 10),
    ("", False, 10),
    ("【圖例】", True, 11),
    ("營收欄：正體黑字 = 財報公布數字（本表全部為公布數字，冇推算）。", False, 10),
    ("級欄底色：綠 = A ｜ 藍 = B ｜ 黃 = C ｜ 橙 = D。", False, 10),
    ("", False, 10),
    ("【免責】本表為公開資料整理與研究參考，非投資建議。財務數據以各公司正式公告為準；"
     "Yahoo 嘅口徑（尤其 Normalized Income 同 Unusual Items）同公司自己嘅 non-GAAP 口徑可能有出入。", False, 10),
]
for i, (txt, bold, sz) in enumerate(lines, 1):
    c = ws.cell(i, 1, txt)
    c.font = Font(name=CJK, size=sz, bold=bold)
    c.alignment = Alignment(vertical="top", wrap_text=True)

# ============ 觀察名單 ============
ws = wb.create_sheet("觀察名單")
for j, (title, fill, width) in enumerate(HEADERS, 1):
    c = ws.cell(1, j, title)
    c.font = Font(name=HDR_F, size=9.5, bold=True, color="FFFFFF")
    c.fill = PatternFill("solid", fgColor=fill)
    c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    c.border = BORDER
    ws.column_dimensions[get_column_letter(j)].width = width
ws.row_dimensions[1].height = 51.75

for i, d in enumerate(data, 2):
    ends = d.get("ends") or []
    vals = [
        d["rank"], d["sym"], "—", d["name"], (d["sector"] + ("／" + d["industry"] if d["industry"] else ""))[:38],
        d["cur"], " / ".join(qlabel(e) for e in ends) if ends else "—",
    ]
    for j, v in enumerate(vals, 1):
        c = ws.cell(i, j, v)
        c.border = BORDER
        c.alignment = Alignment(horizontal="center" if j in (1, 2, 3, 6) else "left",
                                vertical="center", wrap_text=True)
        c.font = Font(name=CJK, size=7.5 if j == 7 else (8 if j == 6 else 9),
                      bold=(j == 2 or j == 6), color=LINK_COLOR if j == 2 else None)
    ws.cell(i, 2).hyperlink = f"https://www.tradingview.com/chart/Q1c5VWwD/?symbol={d['exch']}%3A{d['sym'].lower()}"
    # 營收 H-K
    rev = (d.get("rev") or [None] * 4)
    for k, v in enumerate(rev):
        c = ws.cell(i, 8 + k, None if v is None else round(v, 1))
        c.number_format = "#,##0.0"
        c.fill = PatternFill("solid", fgColor=REV_FILL)
        c.font = Font(name=CJK, size=9.5, bold=True, color="000000")
        c.alignment = Alignment(horizontal="right", vertical="center")
        c.border = BORDER
    c = ws.cell(i, 12, est_rev(d))
    # 營利 M-P
    four = d.get("four") or [None] * 4
    for k in range(4):
        c = ws.cell(i, 13 + k, profit_cell(four[k] if k < len(four) else None, d["bkey"], d["blab"]))
        c.fill = PatternFill("solid", fgColor=PRF_FILL)
        c.font = Font(name=HDR_F, size=7.5, bold=(k == 3))
        c.alignment = Alignment(vertical="top", wrap_text=True)
        c.border = BORDER
    ws.cell(i, 17, est_eps(d))
    ws.cell(i, 18, once_col(d))
    ws.cell(i, 19, trend_col(d))
    ws.cell(i, 20, verdict_col(d, d["why"]))
    for j in (12, 17, 18, 19, 20):
        c = ws.cell(i, j)
        c.font = Font(name=CJK, size=8.5)
        c.alignment = Alignment(vertical="top", wrap_text=True)
        c.border = BORDER
    g = ws.cell(i, 21, d["grade"])
    g.font = Font(name=CJK, size=9, bold=True)
    g.alignment = Alignment(horizontal="center", vertical="center")
    g.fill = PatternFill("solid", fgColor=GRADE_FILL.get(d["grade"], "F2F2F2"))
    g.border = BORDER
    v = ws.cell(i, 22, qlabel(ends[-1]).split("(")[0] if ends else "—")
    v.font = Font(name=CJK, size=9)
    v.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    v.border = BORDER
    longest = max(len(ws.cell(i, j).value or "") for j in (18, 19, 20))
    ws.row_dimensions[i].height = max(62, min(127.5, 20 + longest / 34 * 11))
ws.freeze_panes = "F2"
ws.auto_filter.ref = f"A1:V{len(data) + 1}"

# ============ 圖表連結 ============
ws = wb.create_sheet("圖表連結")
for col, w in zip("ABCDEF", (4, 13, 22, 13, 5, 62)):
    ws.column_dimensions[col].width = w
ws["A1"] = f"{len(data)} 隻 TradingView 圖表連結一覽 — 點 B 欄開圖; F 欄為純文字 URL, 方便複製"
ws["A2"] = "連結格式沿用你的 layout: https://www.tradingview.com/chart/Q1c5VWwD/"
for r in (1, 2):
    ws.cell(r, 1).font = Font(name=CJK, size=10, bold=(r == 1))
for j, t in enumerate(["#", "美股", "公司", "港股", "級", "純文字 URL"], 1):
    c = ws.cell(4, j, t)
    c.font = Font(name=HDR_F, size=9.5, bold=True, color="FFFFFF")
    c.fill = PatternFill("solid", fgColor=NAVY)
    c.alignment = Alignment(horizontal="center", vertical="center")
    c.border = BORDER
for i, d in enumerate(data, 5):
    url = f"https://www.tradingview.com/chart/Q1c5VWwD/?symbol={d['exch']}%3A{d['sym'].lower()}"
    for j, v in enumerate([d["rank"], d["sym"], d["name"], "—", d["grade"], url], 1):
        c = ws.cell(i, j, v)
        c.font = Font(name=CJK, size=9, bold=(j == 2),
                      color=LINK_COLOR if j == 2 else None)
        c.alignment = Alignment(horizontal="left" if j in (3, 6) else "center", vertical="center")
        c.border = BORDER
    ws.cell(i, 2).hyperlink = url
    ws.cell(i, 5).fill = PatternFill("solid", fgColor=GRADE_FILL.get(d["grade"], "F2F2F2"))
ws.freeze_panes = "A5"

# ============ 一次性項目總表 ============
ws = wb.create_sheet("一次性項目總表")
for col, w in zip("ABCDE", (18, 20, 34, 16, 44)):
    ws.column_dimensions[col].width = w
mat = [d for d in data if d.get("unusual") and d.get("unusual_share") and d["unusual_share"] >= 10]
mat.sort(key=lambda d: -d["unusual_share"])
ws["A1"] = f"最新季含重大一次性／非營運項目嘅 {len(mat)} 隻 — 佔帳面淨利 10% 或以上"
ws["A2"] = ("金額嚟自 Yahoo「Total Unusual Items」，係實數；但項目性質同「會否重複」需要逐隻讀財報原文，本版未做，一律列「待核實」。"
            "R7 嗰六類分法（資產出售／減值／仲裁稅務／公允值重估／或有代價／基期扭曲）要人手歸類。")
for r in (1, 2):
    ws.cell(r, 1).font = Font(name=CJK, size=10, bold=(r == 1))
    ws.cell(r, 1).alignment = Alignment(vertical="top", wrap_text=True)
ws.row_dimensions[2].height = 30
for j, t in enumerate(["方向", "個股", "項目與金額 (最新季)", "會否重複", "對判斷的影響"], 1):
    c = ws.cell(4, j, t)
    c.font = Font(name=HDR_F, size=9.5, bold=True, color="FFFFFF")
    c.fill = PatternFill("solid", fgColor=PURPLE)
    c.alignment = Alignment(horizontal="center", vertical="center")
    c.border = BORDER
for i, d in enumerate(mat, 5):
    unu, net = M(d["unusual"]), M(d["q0"].get("net"))
    norm = M(d["norm"]) if d["norm"] is not None else None
    direction = "① 收益 — 令帳面好看" if unu > 0 else "② 支出／減值 — 令帳面難看"
    impact = (f"帳面淨利 {fmt_m(net)}，剔除後 {fmt_m(norm)}" if norm is not None
              else f"帳面淨利 {fmt_m(net)}，剔除後 Yahoo 未提供")
    if norm is not None and net is not None and (norm > 0) != (net > 0):
        impact += "　— 剔除後由虧轉盈，帳面方向唔可信" if net < 0 else "　— 剔除後由盈轉虧，帳面方向唔可信"
    for j, v in enumerate([direction, f"{d['sym']} {d['name'][:18]}",
                           f"{fmt_m(unu)}（佔帳面淨利 {d['unusual_share']:.0f}%）",
                           "待核實", impact], 1):
        c = ws.cell(i, j, v)
        c.font = Font(name=CJK, size=8.5)
        c.alignment = Alignment(vertical="top", wrap_text=True)
        c.border = BORDER
    ws.row_dimensions[i].height = 30
ws.freeze_panes = "A5"

# ============ 經常性軌跡排隊 ============
ws = wb.create_sheet("經常性轉正排隊")
for col, w in zip("ABC", (24, 24, 90)):
    ws.column_dimensions[col].width = w
ws["A1"] = "按「經常性口徑」重新排隊 — 帳面同經常性嘅差異就係拆解嘅價值"
ws["A1"].font = Font(name=CJK, size=10, bold=True)
for j, t in enumerate(["經常性狀態", "口徑", "個股與依據"], 1):
    c = ws.cell(3, j, t)
    c.font = Font(name=HDR_F, size=9.5, bold=True, color="FFFFFF")
    c.fill = PatternFill("solid", fgColor=PURPLE)
    c.alignment = Alignment(horizontal="center", vertical="center")
    c.border = BORDER


def joinlist(items, n=24):
    return " ｜ ".join(items[:n]) + (f" …（共 {len(items)} 隻）" if len(items) > n else "")


buckets = [
    ("經常性盈利且乾淨", "GAAP / 營運利潤 (金融股為稅前)",
     [f"{d['sym']} ({d['blab']} {fmt_m(M(d['q0'].get(d['bkey'])))}, 率 {d['op_margin']:.0f}%)"
      for d in data if d["grade"] == "A" and d.get("op_margin") is not None]),
    ("盈利但帳面含重大一次性", "GAAP vs 經常",
     [f"{d['sym']} (一次 {fmt_m(M(d['unusual']))}, 佔 {d['unusual_share']:.0f}%)"
      for d in data if d["grade"] == "B" and (d.get("unusual_share") or 0) >= 10]),
    ("盈利但利潤按年倒退", "營運／稅前利潤 YoY",
     [f"{d['sym']} ({d['op_yoy']:+.0f}%)" for d in data
      if d["grade"] == "B" and (d.get("unusual_share") or 0) < 10 and d.get("op_yoy") is not None]),
    ("虧損收窄中", "營運／稅前四季軌跡",
     [f"{d['sym']} ({fmt_m(M(d['op_trend'][0]))} → {fmt_m(M(d['op_trend'][-1]))})"
      for d in data if d["grade"] == "C"]),
    ("四季內由盈轉虧", "營運／稅前四季軌跡",
     [f"{d['sym']} ({fmt_m(M(d['op_trend'][0]))} → {fmt_m(M(d['op_trend'][-1]))})"
      for d in data if d["grade"] == "D" and d.get("turned")]),
    ("虧損未見收窄", "營運／稅前四季軌跡",
     [f"{d['sym']} ({fmt_m(M(d['op_trend'][0]))} → {fmt_m(M(d['op_trend'][-1]))})"
      for d in data if d["grade"] == "D" and not d.get("turned")]),
    ("無損益表數據", "—", [d["sym"] for d in data if not d.get("q")]),
]
r = 4
for name, basis, items in buckets:
    if not items:
        continue
    for j, v in enumerate([f"{name} ({len(items)} 隻)", basis, joinlist(items)], 1):
        c = ws.cell(r, j, v)
        c.font = Font(name=CJK, size=8.5, bold=(j == 1))
        c.alignment = Alignment(vertical="top", wrap_text=True)
        c.border = BORDER
    ws.row_dimensions[r].height = min(150, 16 + len(joinlist(items)) / 90 * 12)
    r += 1
ws.freeze_panes = "A4"

# ============ 分級彙總 ============
ws = wb.create_sheet("分級彙總")
for col, w in zip("ABCD", (8, 46, 8, 78)):
    ws.column_dimensions[col].width = w
ws["A1"] = "分級彙總 — 以「經常性口徑」評級 (數量由 COUNTIF 連動觀察名單 U 欄)"
ws["A1"].font = Font(name=CJK, size=10, bold=True)
for j, t in enumerate(["分級", "定義 (經常性口徑)", "數量", "Tickers"], 1):
    c = ws.cell(3, j, t)
    c.font = Font(name=HDR_F, size=9.5, bold=True, color="FFFFFF")
    c.fill = PatternFill("solid", fgColor=NAVY)
    c.alignment = Alignment(horizontal="center", vertical="center")
    c.border = BORDER
DEFS = [("A", "營運利潤為正、帳面≈經常 (一次性 <10%)、按年未倒退"),
        ("B", "營運利潤為正，但含重大一次性 (≥10%) 或營運利潤按年倒退"),
        ("C", "營運仍虧損，四季軌跡收窄中"),
        ("D", "營運虧損且未見收窄，或四季內由盈轉虧"),
        ("—", "Yahoo 無季度損益表，未評級")]
for i, (g, defi) in enumerate(DEFS, 4):
    syms = [d["sym"] for d in data if d["grade"] == g]
    for j, v in enumerate([g, defi, f'=COUNTIF(觀察名單!U:U,"{g}")', ", ".join(syms)], 1):
        c = ws.cell(i, j, v)
        c.font = Font(name=CJK, size=9, bold=(j == 1))
        c.alignment = Alignment(horizontal="center" if j in (1, 3) else "left",
                                vertical="top", wrap_text=True)
        c.border = BORDER
    ws.cell(i, 1).fill = PatternFill("solid", fgColor=GRADE_FILL.get(g, "F2F2F2"))
    ws.row_dimensions[i].height = min(120, 16 + len(", ".join(syms)) / 78 * 12)
i = len(DEFS) + 4
ws.cell(i, 1, "合計").font = Font(name=CJK, size=9, bold=True)
ws.cell(i, 3, f"=SUM(C4:C{i - 1})").font = Font(name=CJK, size=9, bold=True)
ws.cell(i, 3).alignment = Alignment(horizontal="center")
ws.cell(i + 2, 1, f"資料截至各公司最新已公布財季；名單為 10MA Uptrend Watchlist {SRC_REV}（{LAST} 收盤）。"
                  "Yahoo 口徑，非投資建議。").font = Font(name=CJK, size=9)

os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
wb.save(OUT)
print(f"wrote {OUT}: {len(data)} tickers · grades " +
      str({g: sum(1 for d in data if d['grade'] == g) for g in ('A', 'B', 'C', 'D', '—')}) +
      f" · with quarterly {n_q} · unusual {n_unu} · normalized {n_norm} · rev estimates {n_est}")

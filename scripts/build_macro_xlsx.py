"""Excel workbook for the macro-regime study, from data/macro_regimes.json and
the charts in reports/macro/. usage: build_macro_xlsx.py OUT.xlsx"""
import csv, datetime, glob, gzip, json, os, sys
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter as gl
from openpyxl.drawing.image import Image as XLImage
from openpyxl.worksheet.formula import ArrayFormula
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import macro_events as E
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
J = json.load(open(f"{REPO}/data/macro_regimes.json"))
OUT = sys.argv[1]
HKT = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime("%Y-%m-%d %H:%M")

# ---- TradingView links ------------------------------------------------------------------------
EXCH = {}
try:
    S = json.load(open(f"{REPO}/data/screen_hm23.json"))
    for r in S.get("rows", []) + S.get("hot", []):
        if r.get("exch"): EXCH.setdefault(r["sym"], r["exch"])
    for s, g in S.get("gates", {}).items():
        if isinstance(g, dict) and g.get("exch"): EXCH.setdefault(s, g["exch"])
except Exception:
    pass
for f in sorted(glob.glob(f"{REPO}/data/snapshots/*.csv"))[-1:]:
    with open(f) as fh:
        rd = csv.DictReader(fh)
        cols = {c.lower(): c for c in rd.fieldnames or []}
        sc = cols.get("symbol") or cols.get("sym"); ec = cols.get("exchange") or cols.get("exch")
        if sc and ec:
            for row in rd:
                if row.get(ec): EXCH.setdefault(row[sc], row[ec])
ETF_EXCH = {"XLE": "AMEX", "XLK": "AMEX", "XLF": "AMEX", "XLV": "AMEX", "XLU": "AMEX", "XLP": "AMEX", "XLY": "AMEX", "XLI": "AMEX", "XLB": "AMEX",
            "XLRE": "AMEX", "XLC": "AMEX", "IYR": "AMEX", "IWD": "AMEX", "IWF": "AMEX", "GLD": "AMEX", "TLT": "NASDAQ", "SPY": "AMEX", "QQQ": "NASDAQ"}
INDEX_TV = {"^GSPC": "SPX", "^IXIC": "IXIC", "^RUT": "RUT", "^SOX": "SOX", "^OSX": "OSX", "^XAU": "XAU", "^HGX": "HGX", "^BKX": "BKX",
            "^DJT": "DJT", "^DJU": "DJU", "^DJI": "DJI", "^VIX": "VIX", "^TNX": "TNX", "^IRX": "IRX", "DX-Y.NYB": "DXY"}
def tv_url(sym):
    if sym in INDEX_TV: return f"https://www.tradingview.com/chart/Q1c5VWwD/?symbol={INDEX_TV[sym]}"
    s2 = sym.replace("-", ".").replace("/", ".")
    ex = ETF_EXCH.get(sym) or EXCH.get(sym) or EXCH.get(s2)
    return (f"https://www.tradingview.com/chart/Q1c5VWwD/?symbol={ex.lower()}%3A{s2}" if ex and ex != "—"
            else f"https://www.tradingview.com/chart/Q1c5VWwD/?symbol={s2}")
def link(ws, r, c, sym):
    cell = ws.cell(row=r, column=c, value=sym); cell.hyperlink = tv_url(sym); cell.font = Font(color="0563C1", underline="single"); return cell

# ---- styles -------------------------------------------------------------------------------------
H = Font(bold=True, color="FFFFFF"); HF = PatternFill("solid", fgColor="1F4E78"); SUB = PatternFill("solid", fgColor="DDEBF7")
WRAP = Alignment(wrap_text=True, vertical="top")
def header(ws, r, cols, widths=None):
    for j, c in enumerate(cols, 1):
        x = ws.cell(row=r, column=j, value=c); x.font = H; x.fill = HF; x.alignment = Alignment(wrap_text=True, vertical="center")
    if widths:
        for j, w in enumerate(widths, 1): ws.column_dimensions[gl(j)].width = w
def title(ws, text, sub=None):
    ws["A1"] = text; ws["A1"].font = Font(bold=True, size=14)
    if sub: ws["A2"] = sub; ws["A2"].font = Font(italic=True, color="555555")
def pct(cell, fmt="0.0%"): cell.number_format = fmt
def put(ws, r, c, v, fmt=None, bold=False, wrap=False):
    x = ws.cell(row=r, column=c, value=v)
    if fmt: x.number_format = fmt
    if bold: x.font = Font(bold=True)
    if wrap: x.alignment = WRAP
    return x
f1 = lambda v: None if v is None else round(v, 1)

wb = Workbook()
now, sim, eps, forces = J["now"], J["similarity"], J["episodes"], J["forces"]
by_key = {e["key"]: e for e in eps}
rank = sorted([e for e in eps if e["stats"]["dist"] is not None], key=lambda e: e["stats"]["dist"])

# ================= 結論 =======================================================================
ws = wb.active; ws.title = "結論"
title(ws, f"油價高企＋加息預期：美國歷史上邊段時期最似 2026 年 10 月？（生成 {HKT} HKT）",
      "數據驅動對標：九項宏觀特徵（油價 12 個月變化、CPI、3 個月息 3／12 個月變化、10 年期 12 個月變化、曲線斜率、實質短息、標普 12 個月回報、距高位）加權 z 距離；板塊回報用 ETF／指數，1998 年前用長壽股籃")
ws.column_dimensions["A"].width = 30; ws.column_dimensions["B"].width = 150
import statistics as st
NOWM = J["now_month"]
liq_done = [h for h in forces["liquidity"] if h["end"]]
m_first12 = st.median(h["sp_after_first12"] * 100 for h in liq_done); n_first_dd = sum(1 for h in liq_done if h["maxdd_after_first"] <= -10)
dd_names = "、".join(str(int(h["start"][:4]) + (1 if h["start"][5:] == "12" else 0)) for h in liq_done if h["maxdd_after_first"] <= -10)
m_last12 = st.median(h["sp_after12"] * 100 for h in liq_done); n_rec = sum(1 for h in liq_done if h["recession_after"]); m_len = st.median(h["months"] for h in liq_done)
pol = [p for p in forces["politics"] if not p.get("partial")]
m_pdd = st.median(p["maxdd"] for p in pol); m_plow = st.median(p["from_low_12"] * 100 for p in pol); n_ppos = sum(1 for p in pol if p["from_low_12"] > 0)
p_exc = "、".join(str(p["year"]) for p in pol if p["from_low_12"] <= 0); p26 = next(p for p in forces["politics"] if p["year"] == 2026)
te = forces["tech_extra"]; ai = forces["tech"][-1]
sup = {x["month"]: x for x in forces["supply_shocks"]}
tops = sim["top"]; m_f12 = st.median(r["fwd12"] for r in tops); n_pos12 = sum(1 for r in tops if r["fwd12"] > 0); m_dd12 = st.median(r["maxdd12"] for r in tops)
m_f24 = st.median(r["fwd24"] for r in tops if r["fwd24"] is not None); n_pos24 = sum(1 for r in tops if r["fwd24"] is not None and r["fwd24"] > 0)
bad24 = "、".join(f'{r["month"]}（{r["fwd24"]:+.0f}%）' for r in sorted(tops, key=lambda r: r["fwd24"] if r["fwd24"] is not None else 0)[:5])
good24 = "、".join(f'{r["month"]}（{r["fwd24"]:+.0f}%）' for r in sorted(tops, key=lambda r: -(r["fwd24"] if r["fwd24"] is not None else 0))[:5])
def _f12(r): return "—" if r["fwd12"] is None else f'{r["fwd12"]:+.0f}%'
def _f24(r): return "—" if r["fwd24"] is None else f'{r["fwd24"]:+.0f}%'
s73, s79, s90, s22, s26 = sup["1973-10"], sup["1979-01"], sup["1990-08"], sup["2022-02"], sup["2026-02"]
rows = []
rows.append((f"現時（{NOWM}，10 月為至 10-01 嘅部分月）", f'WTI ${now["wti"]:.0f}（12 個月 {now["oil_12m"]:+.0f}% 對數變化）、CPI {now["cpi_yoy"]:.1f}%、3 個月息 {now["irx"]:.2f}%（3 個月內 {now["irx_3m"]:+.2f} 點）、10 年期 {now["y10"]:.2f}%（12 個月 {now["y10_12m"]:+.2f} 點；09-30 盤中 5.34% 為 2002 年後最高）、曲線 10 年－3 月 {now["slope"]:+.2f}、實質短息 {now["real_rate"]:+.1f}%、標普 12 個月 {now["sp_12m"]:+.0f}%、距 24 個月高位 {now["sp_dd"]:+.1f}%、VIX {now["vix"]:.0f}、美元指數 {now["dxy"]:.0f}、黃金 ${now["gold"]:.0f}；聯儲 09-16 加息至 3.75–4.00%（12 比 0），點陣圖年內再加一次，期貨 12 月加息機率約 79%'))
rows.append(("機械對標（九項特徵）最近嘅月份", "、".join(f'{r["month"]}（距離 {r["dist"]:.2f}；之後 12 個月標普 {_f12(r)}、24 個月 {_f24(r)}）' for r in tops[:8])))
rows.append(("十個候選時期按相似度排序（越低越似）", "、".join(f'{e["key"]} {e["title"]}（{e["stats"]["dist"]:.2f}）' for e in rank) + "。注意：1973 同 1979 排最尾 —— 當年 CPI 9–12%、短息 7–12%，而家 CPI 3.4%、短息 4%，宏觀強度差成個數量級；1970 年代係「第二波通脹」嘅尾部劇本，唔係基準"))
rows.append(("對標月份之後點走（統計）", f'最似嘅 {len(tops)} 個月之後 12 個月標普中位數 {m_f12:+.1f}%（{n_pos12}/{len(tops)} 次上升、12 個月內最大回撤中位數 {m_dd12:+.1f}%），同全樣本（1962 年起任何月份：12 個月 {sim["base"]["fwd12_median"]:+.1f}%、{sim["base"]["fwd12_pos"]:.0f}% 上升）差唔多 —— 即係「油價高＋加息預期＋股市高位」本身唔係睇淡訊號。'
             f'但 24 個月後分化極大：差嘅 {bad24}；好嘅 {good24}。分界線唔係油價，係通脹有冇第二波：1966／1968／1972／1999 之後 CPI 再升、聯儲繼續加，1995／1996／2004／2006／2013／2017 之後通脹受控、聯儲停手'))
rows.append(("判斷：最似邊個時期", "冇一段完全一樣，數據指向三個時期嘅混合：①「債息＋政治」最似 2006 年 5–6 月（距離 0.36–0.44：10 年期 5.2%、加息尾聲、第二任總統中期選舉年、油價歷史新高、能源／原材料／工業領漲、樓市股見頂）；"
             "②「市場結構」最似 1999 年 10 月至 2000 年 3 月（距離 0.36–0.54：減息後重新加息、科技狂熱同油價三倍並存、指數靠少數股票撐住、債息 6%+、市寬極差）；"
             "③「政治劇本」最似 2018 年 9 月（距離 0.28，機械對標第一：同一位總統、同一個中期年、關稅＋加息＋伊朗制裁推高油價、9 月創新高後 Q4 −20%）。"
             "1987 年 4–9 月（距離 0.46）係第四個對照：10 年期由 7% 升到 10%、股市照創新高、VIX 式波幅極低 —— 債市主導嘅調整。"
             "1979–80 只係宏觀「本質」相似（供應型油震、聯儲先減後加、長債息見多年高、硬資產跑贏），數字上距離最遠。"))
rows.append(("油震＋加息窗口內邊啲股票回報高（相對標普超額，ETF／指數；* = 長壽股籃）", "能源／油服 —— 只要油價升勢持續就係第一：2000 +22／油服 +71、2006 +48／+80、2022 +84／+79、1979 +81*；但油震一兩個月就逆轉嘅 1990（−4*）同 2018（−12／油服 −40）反而跑輸。"
             "必需消費：1990 +17*、2000 +14、2008 +29、2011 +14、2022 +19（2006 −4、2018 −2 例外）。醫療：1990 +43*、2008 +18、2011 +12、2018 +13、2022 +17。"
             "公用事業：1990 年後七次全部正超額（+9 至 +21）—— 但 1973 −7*、1979 −40*、1987 −8*：長債息急升嘅時期公用事業係最差板塊，而 2026 年 9 月 XLU −6%、XLP −5% 已經係 1979／1987 模式，唔係 2022 模式。"
             "黃金（GLD）五次窗口全部正超額（+4 至 +59），黃金股就要弱美元先得（2006 +50、1987 +22*；1990／2000／2011／2018 負）；而家美元創年內新高、金價月跌 6% —— 似 2018 多過 2006。"))
rows.append(("窗口內邊啲股票低迷", "房屋建築／按揭敏感：2006 −49、2018 −23、1987 −31*（要到息口見頂先反彈：1990 後 +70*、2000 後 +163*）。銀行：2006 −15、2008 −17、2011 −25、2018 −13。運輸／航空（油價係成本）：1987 −20*、2000 −15、2018 −7。"
             "非必需消費：1973 −18*、1979 −30*、2022 −17。長債：加息窗口 2006 −20、2022 −12（減息／避險窗口先贏：2008 +84、2011 +34）。半導體：窗口內 2006 −6、2008 −17、2011 −12、2022 −16，錨點後 12 個月 2000 −38、2006 −11、2011 −11；科技 2000 錨點後 −41、納指 −46。"
             "1973–74 嘅漂亮 50（高估值消費／科技龍頭）跌 60–80%；1979–81 公用事業、汽車、航空、儲貸機構最差。"))
rows.append(("錨點之後 12 個月（油價頂／加息頂之後）邊啲接力", "冇衰退嘅版本（2006、2018、1990）：公用事業（2006 +11、2018 +23、1990 +14*）、必需消費（2018 +16、1990 +14*）、房地產（2018 +14、1990 +19*）、黃金（2018 +20）、長債（2018 +19）接力，油服（2018 −57）、能源（2018 −20、1990 −18*）、小型股（2018 −15）、銀行（2006 −14）跑輸。"
             "有衰退嘅版本（2000、1973）：2000 後公用 +50、金融 +46、必需 +37、能源 +35、房地產 +67* 對科技 −41、半導體 −38；1973 後原材料 +14*、能源 +7* 對金融 −14*、非必需 −11*。"
             "通脹第二波版本（1979）：能源 +38*、科技 +11*、納指 +12 繼續領先，公用事業 −21*、金融 −21*、非必需 −17* 繼續低迷 —— 即係如果 CPI 再上 5%，而家嘅「買公用事業避險」會錯。"))
rows.append(("同今日最大嘅唔同（對標嘅限制）", f'① 緊縮程度：聯儲由 3.5% 起步、實質短息 {now["real_rate"]:+.1f}%，遠低過 1980（+5%）、2000（+3%）、2006（+1%）；② 油價 ${now["wti"]:.0f} 實質只等於 1980 年頂嘅三分一、2008 年頂嘅六成，而美國已係淨出口國，油震係再分配多過總量衝擊（能源股 9 月跌、煉油股 YTD +80%）；'
             f'③ VIX {now["vix"]:.0f}、標普距高位 {now["sp_dd"]:+.1f}%、科技 YTD +36%、半導體 +69% —— 市場未為加息定價，呢點似 1987-08 同 2018-09 多過似 2022；④ 10 年期 5.3% 係 2002 年後最高，期限溢價（財赤＋通脹）重現，呢點似 1987 同 1994 嘅債市主導調整，而唔係 2006（當年 10 年期由 5.25% 回落）'))
rows.append(("四大力量：而家處於邊個階段", f'① 流動性：加息周期第 1 個月。12 個已完結加息周期：首次加息後 12 個月標普中位數 {m_first12:+.1f}%，但 {n_first_dd}/12 次喺 12 個月內出現 ≥10% 回撤（{dd_names}）；周期歷時中位數 {m_len:.0f} 個月；最後加息後 12 個月中位數 {m_last12:+.1f}%；{n_rec}/12 次喺最後加息後兩年內衰退。起點 CPI 3.4%、油價 12 個月 +42%，最似 1977-01、1987-01、1999-06 嘅起步。'
             f'② 政治：第二任總統中期選舉年 Q4。1954–2022 共 {len(pol)} 個中期年：年內最大回撤中位數 {m_pdd:+.1f}%，由年內低位計之後 12 個月中位數 {m_plow:+.1f}%、{n_ppos}/{len(pol)} 次上升（唯一例外 {p_exc} —— 正正係第二次石油危機前夕）；2026 年至今最大回撤只有 {p26["maxdd"]:+.1f}%（3 月低位），係歷來最淺嘅中期年之一，同 1958、2006、2014 相若 —— 淺回撤嘅中期年風險係推遲（2007-10、2018-Q4）而唔係消失。'
             f'③ 產業：生成式 AI 資本開支浪第 {te["months_ai"]} 個月，納指相對標普由 2022-10 起升 {te["rel_2022_10_to_now"]:.2f} 倍（1995-01→2000-03 升 {te["rel_1995_01_to_2000_03"]:.1f} 倍）；1999-06 聯儲開始加息後納指再升 9 個月先見頂（+{te["nq_1999_06_to_2000_03"]*100:.0f}%，標普 +{te["sp_1999_06_to_2000_03"]*100:.0f}%）；1973、1983、2000、2021 四次爆破都係加息周期開始後 6–18 個月 —— 位置約等於 1999 年中：加息開始但狂熱未完。'
             f'④ 黑天鵝：荷姆茲油震第 8 個月。供應型油震：1973 衝擊→油頂 {s73["months_to_peak"]} 個月、聯儲繼續加息到 1974-07，標普低位遲過油頂 {s73["low_vs_peak"]} 個月、跌 {s73["sp_dd"]*100:.0f}%；1990 油頂 {s90["months_to_peak"]} 個月、聯儲減息，標普低位同油頂同月、跌 {s90["sp_dd"]*100:.0f}%；2022 油頂 {s22["months_to_peak"]} 個月、聯儲繼續加，標普低位遲 {s22["low_vs_peak"]} 個月、跌 {s22["sp_dd"]*100:.0f}%；1979 股市全程冇回撤但通脹升到 14.8%。'
             f'今次油價 {s26["oil_peak"]} 見頂（+{s26["oil_gain"]*100:.0f}%）、標普 3 月低位只跌 {s26["sp_dd"]*100:.0f}% —— 油頂已過但聯儲喺油頂之後先開始加息，係 1973／2022 嘅次序（股市低位喺油頂後 3–8 個月），唔係 1990 嘅次序。'))
rows.append(("要睇嘅領先指標（完結周期參考）", f'1) 油價：Brent 收返 $85 以下＝油震解除（1991-01、2008-10、2022-09 都係油價跌穿 3 個月前低位後 1–2 個月股市見底）；2) 曲線：10 年－3 月 {now["slope"]:+.2f}，歷次加息周期末段倒掛先衰退（1973、1980、1989、2000、2006、2019、2022 全部先倒掛）—— 而家離倒掛仲有 125 點子，即係加息周期未到尾段；'
             f'3) 信貸同銀行股：2006 同 2018 都係銀行股相對大市先跌 6–9 個月；4) 市寬：9 月 75% 標普成分股下跌但指數只跌 0.5%，呢種「指數靠 AI 撐」嘅背馳同 1999-Q4、2007-Q3、2018-Q3 一樣，歷史上維持 3–9 個月；5) 公用事業／必需消費相對大市：佢哋同長債一齊跌（9 月 XLU −6%）係 1979／1987 式「債息主導」訊號，佢哋轉強先係 2000／2018 式「避險輪動」訊號；6) 中期選舉後：{len(pol)} 次中期年低位之後 12 個月 {n_ppos} 次上升，但 1974、2002、2022 嘅升係由 −25% 至 −35% 嘅低位起步'))
rows.append(("對 10 ma watchlist 嘅含意", "按歷史劇本，油震＋加息期間「熱錢回調到 20MA」嘅名單應該偏向能源／油服、黃金、必需消費、醫療，避開房屋建築、銀行、航空、長久期科技；R23 嘅熱錢板塊入面醫療 68 隻（集中度 1.97×）同板塊劇本一致，但能源只有 2 隻、公用 2 隻、金融 13 隻 —— 即係市場仍然當呢次油震係短暫，熱錢仲喺 AI 半導體（4–6 月嘅舊錢）同生物科技；"
             "如果 10 月油價唔再創高、CPI 企喺 3.5% 以下，劇本偏向 2006／2018（指數再創高、年底前有 10–20% 回撤風險）；如果 CPI 升穿 4%、10 年期企穩 5.5%，就係 1973／1999 嘅次序，防守板塊都唔會避到。"))
for i, (k, v) in enumerate(rows, 4):
    put(ws, i, 1, k, bold=True, wrap=True); put(ws, i, 2, v, wrap=True); ws.row_dimensions[i].height = max(30, 15 * (len(v) // 95 + 1))

# ================= 現時數據 ===================================================================
ws = wb.create_sheet("現時數據"); title(ws, "2026 年 10 月 2 日嘅宏觀同市場狀況（用嚟做對標嘅輸入）")
header(ws, 3, ["項目", "數值", "日期", "來源／備注"], [34, 18, 14, 110])
cur = [
    ("聯邦基金目標區間", "3.75%–4.00%", "2026-09-16", "FOMC 12 比 0 加息 25 點子；2023-07 以來首次加息；主席 Kevin Warsh：「通脹太高、高得太耐」；點陣圖 18 人中 16 人預期年內再加一次（CNBC、Schwab、Chase）"),
    ("市場加息預期", "10 月 25–35%、12 月約 79%", "2026-10-01", "CME FedWatch；期貨定價 2027-01 約 4.1%、2027-10 約 4.7%（CNBC 09-23、Babypips 10-01、US News 09-30 高盛推遲至 12 月）"),
    ("10 年期美債息", f'{now["y10"]:.2f}%（月底）', "2026-09-30", "09-30 盤中 5.342%，2002 年 4 月後最高；30 年期 24 年高（Seoul Economic Daily、CNBC）"),
    ("3 個月國庫券（政策代理）", f'{now["irx"]:.2f}%', "2026-09-30", "Yahoo ^IRX 月收市"),
    ("CPI 按年", "3.4%（8 月）", "2026-09-10", "2026 年：1 月 2.4、2 月 2.4、3 月 3.3、4 月 3.8、5 月 4.2（三年高）、6 月 3.5、7 月 3.4、8 月 3.4；核心 PCE 3.0%（8 月，低過預期 3.3%）；PPI 5.4%"),
    ("WTI／Brent", "$92.6／約 $98", "2026-10-02", "Trading Economics；WTI 12 個月前（2025-10 均價）$60.9；2026 年高位：WTI $114.6（04-07）、Brent $138.2（04-07，EIA 現貨）；09-10 Brent $107.6 為 5 月後新高"),
    ("油震來源", "荷姆茲海峽 02-28 起實質封閉", "2026-02-28", "美以空襲伊朗；04-08 巴基斯坦斡旋停火、04-19 伊朗再限制通行；9 月流量回升至 1,320 萬桶／日（仍低過戰前）；沙特東西管道修復、延布出口恢復；美伊就重開方案談判中（CNBC、Al Jazeera、oilprice.com）"),
    ("標普 500", f'{now["sp"]:.0f}（最新月收市）', NOWM, "9 月 −0.5%、道指 −4.3%、納指 +1.9%；Q3 標普 +2%；09-25 收 7,743 創收市新高、10-01 收 7,667（AP、CNBC、Yahoo）"),
    ("板塊", "科技 YTD +36%、半導體 +69%", "2026-09-30", "9 月 11 個 SPDR 板塊只有 XLK 升（+5.1%），公用 −6%、必需消費 −5%、其餘 −0.4% 至 −7.6%；75% 標普成分股 9 月下跌（CNBC「broken market」、24/7 Wall St）"),
    ("VIX", f'{now["vix"]:.0f}', "2026-09-30", "低波幅——市場未為加息／油震定價"),
    ("美元指數", "101.6–102.1", "2026-10-02", "2026 年新高；1 個月 +2.1%、12 個月 +3.9%（Trading Economics、FXStreet）"),
    ("黃金", "$4,190", "2026-10-02", "1 個月 −6.4%、12 個月 +7.8%（Trading Economics）"),
    ("就業", "失業率 4.1%、工資按年 3.1–3.2%", "2026-10-02", "8 月非農 +162k 勝預期；9 月預期 +84–94k；ADP 9 月 +90k；實質工資接近零增長（CNBC、CEPR）"),
    ("增長", "Q2 GDP 上修至 2.2%", "2026-09-30", "由 1.5% 上修；令 12 月加息預期維持"),
    ("關稅", "IEEPA 關稅 02-20 被最高法院推翻（6 比 3）", "2026-02-20", "約 $1,650 億退款；改用 232／338 條款；加拿大 09-08 反制 $276 億；美國 09-29 起 338 條款禁止部分加拿大貨品進口"),
    ("政治周期", "特朗普第二任第 2 年；中期選舉 2026-11-03", "", "對應 2006（小布殊第二任中期年）、2018（特朗普第一任中期年）"),
]
for i, r in enumerate(cur, 4):
    for j, v in enumerate(r, 1): put(ws, i, j, v, wrap=(j == 4))
r0 = len(cur) + 6
put(ws, r0, 1, f"對標用嘅九項特徵（{NOWM}）", bold=True)
header(ws, r0 + 1, ["特徵", "數值", "權重", "說明"])
desc = {"oil_12m": "WTI 12 個月對數變化 %", "cpi_yoy": "CPI 按年 %", "irx_3m": "3 個月息 3 個月變化（點）", "irx_12m": "3 個月息 12 個月變化（點）",
        "y10_12m": "10 年期 12 個月變化（點）", "slope": "10 年期 − 3 個月息（點）", "real_rate": "3 個月息 − CPI（%）", "sp_12m": "標普 12 個月對數回報 %", "sp_dd": "標普距 24 個月高位 %"}
for i, f in enumerate(sim["features"], r0 + 2):
    put(ws, i, 1, f); put(ws, i, 2, sim["now"][f]); put(ws, i, 3, sim["weights"][f]); put(ws, i, 4, desc[f])

# ================= 四大力量 ===================================================================
ws = wb.create_sheet("四大力量"); title(ws, "四大力量嘅牛熊周期：每個周期嘅轉折事件、嗰陣標普點走、而家對應邊個階段（月線計）")
r = 3
put(ws, r, 1, "① 宏觀流動性：聯儲加息周期", bold=True); r += 1
header(ws, r, ["周期", "首次加息", "最後加息", "聯邦基金 由", "至", "周期內標普", "首次加息後 12 個月標普", "首次加息後 12 個月內最大回撤", "最後加息後 12 個月標普", "最後加息後 12 個月內最大回撤", "周期內油價", "CPI 起", "CPI 終", "之後衰退（NBER 頂）", "歷時（月）"],
       [26, 11, 11, 11, 8, 12, 16, 18, 16, 18, 12, 9, 9, 14, 9]); r += 1
l0 = r
for h in forces["liquidity"]:
    vals = [h["label"], h["start"], h["end"] or "進行中", h["ff_from"], h["ff_to"], h["sp_during"], h["sp_after_first12"], None if h["maxdd_after_first"] is None else h["maxdd_after_first"] / 100,
            h["sp_after12"], None if h["maxdd_after"] is None else h["maxdd_after"] / 100, h["oil_during"], h["cpi_start"], h["cpi_end"], h["recession_after"] or "—", h["months"]]
    for j, v in enumerate(vals, 1):
        c = put(ws, r, j, v)
        if j in (6, 7, 8, 9, 10, 11) and isinstance(v, float): pct(c)
    r += 1
put(ws, r, 1, "中位數（已完結周期）", bold=True)
for j in (6, 7, 8, 9, 10, 11):
    c = put(ws, r, j, f"=MEDIAN({gl(j)}{l0}:{gl(j)}{r - 2})"); pct(c)
put(ws, r, 15, f"=MEDIAN({gl(15)}{l0}:{gl(15)}{r - 2})")
r += 1
put(ws, r, 1, "而家：2026-09 首次加息，由 3.5–3.75% 起步；起點 CPI 3.4%、油價 12 個月 +42% —— 起點通脹同油價動量最似 1977-01、1987-01、1999-06；13 個周期中 9 個喺最後加息後 24 個月內衰退", wrap=True); ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=12); ws.row_dimensions[r].height = 32; r += 2

put(ws, r, 1, "② 政治周期：中期選舉年（總統第 2／第 6 年）", bold=True); r += 1
header(ws, r, ["年份", "總統", "黨", "年內最大回撤（月線）", "低位月", "全年標普", "低位起 12 個月", "年底油價 12 個月變化 %", "年內有加息周期"]); r += 1
p0 = r
for p in forces["politics"]:
    vals = [p["year"], p["president"], p["party"], p["maxdd"] / 100, p["low_month"], p["year_ret"], p["from_low_12"], p["oil_12m"], "是" if p["hiking"] else "否"]
    for j, v in enumerate(vals, 1):
        c = put(ws, r, j, v)
        if j in (4, 6, 7) and isinstance(v, float): pct(c)
    if p.get("partial"): put(ws, r, 10, "年內（至 9 月）")
    r += 1
put(ws, r, 1, "中位數（1954–2022）", bold=True)
for j in (4, 6, 7):
    c = put(ws, r, j, f"=MEDIAN({gl(j)}{p0}:{gl(j)}{r - 2})"); pct(c)
put(ws, r, 8, f'=COUNTIF({gl(7)}{p0}:{gl(7)}{r - 2},">0")&"/"&COUNT({gl(7)}{p0}:{gl(7)}{r - 2})&" 次低位起 12 個月上升"'); r += 1
put(ws, r, 1, "而家：2026 中期年至 9 月最大回撤只係個位數 —— 歷來最淺之一（同 1958、2006 相若）；劇本係 Q4 選舉前後出低位、之後 12 個月上升，但 2006 之後嘅 2007-10 頂同 2018 嘅 Q4 −20% 都提醒：淺回撤嘅中期年，風險會推遲而唔係消失", wrap=True); ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=10); ws.row_dimensions[r].height = 32; r += 2

put(ws, r, 1, "③ 技術革命／產業周期", bold=True); r += 1
header(ws, r, ["浪潮", "起", "終", "領漲", "標普（浪內）", "納指（浪內）", "之後爆破期", "爆破期標普", "爆破期納指"]); r += 1
busts = {b["start"]: b for b in forces["tech_busts"]}
for t in forces["tech"]:
    b = busts.get(t["bust"][0]) if t["bust"] else None
    vals = [t["label"], t["start"], t["end"] or "進行中", t["leaders"], t["sp"], t["nasdaq"], f'{t["bust"][0]}→{t["bust"][1]}' if t["bust"] else "—",
            None if not b else b["sp"], None if not b else b["nasdaq"]]
    for j, v in enumerate(vals, 1):
        c = put(ws, r, j, v)
        if j in (5, 6, 8, 9) and isinstance(v, float): pct(c)
    r += 1
put(ws, r, 1, "而家：生成式 AI 資本開支浪 2022-11 起計第 47 個月；1991–2000 互聯網浪聯儲 1999-06 開始加息時納指再升 11 個月先見頂（+80%），1983、2000、2021 三次爆破都係加息周期開始後 6–18 個月", wrap=True); ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=9); ws.row_dimensions[r].height = 32; r += 2

put(ws, r, 1, "④ 黑天鵝／地緣", bold=True); r += 1
header(ws, r, ["月份", "事件", "類型", "之後 3 個月內標普最大跌幅（對前月）", "低位月", "事件後 12 個月標普", "油價 事件前 1 個月→後 6 個月"]); r += 1
s0 = r
for s in forces["shocks"]:
    vals = [s["month"], s["label"], s["type"], None if s["dd3"] is None else s["dd3"] / 100, s["low_month"], s["r12"], s["oil6"]]
    for j, v in enumerate(vals, 1):
        c = put(ws, r, j, v)
        if j in (4, 6, 7) and isinstance(v, float): pct(c)
    r += 1
put(ws, r, 1, "中位數（中東／油震類）", bold=True)
for j in (4, 6, 7):
    ref = f"{gl(j)}{r}"
    ws[ref] = ArrayFormula(ref, f'=MEDIAN(IF(ISNUMBER(SEARCH("油",$C${s0}:$C${r - 1})),{gl(j)}{s0}:{gl(j)}{r - 1}))'); pct(ws[ref])
r += 1
put(ws, r, 1, "供應型油震嘅時序", bold=True); r += 1
header(ws, r, ["衝擊月", "事件", "油價見頂月", "衝擊→見頂（月）", "油價升幅（對衝擊前月）", "標普低位月", "低位對油價頂（月，正 = 遲過油頂）", "標普低位對衝擊前月", "油價見頂時聯儲仍在加息"]); r += 1
for x in forces["supply_shocks"]:
    vals = [x["month"], x["label"], x["oil_peak"], x["months_to_peak"], x["oil_gain"], x["sp_low"], x["low_vs_peak"], x["sp_dd"], "是" if x["fed_hiking_after_peak"] else "否"]
    for j, v in enumerate(vals, 1):
        c = put(ws, r, j, v)
        if j in (5, 8) and isinstance(v, float): pct(c)
    r += 1
put(ws, r, 1, "而家：荷姆茲油震第 8 個月。供應型油震（1973、1979、1990）油價由衝擊到見頂 3–14 個月、股市低位滯後油價頂 0–3 個月；需求／金融型（2008、2022）油價頂 = 衰退／熊市中段。今次 Brent 04-07 $138 頂、09-15 $131 次頂 —— 若 10 月唔再創高，劇本偏向 1990-10 式見底多過 1979 式第二波", wrap=True); ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=7); ws.row_dimensions[r].height = 40

# ================= 對標時期 ===================================================================
ws = wb.create_sheet("對標時期"); title(ws, f"十個候選對標時期：錨點月嘅九項特徵、同 {NOWM} 嘅距離、窗口內同之後 12 個月表現")
cols = ["相似度排名", "時期", "錨點月", "距離（越低越似）", "WTI", "油價 12 個月 %", "CPI %", "3 個月息", "3 個月息 3 個月變化", "10 年期", "10 年期 12 個月變化", "曲線", "實質短息", "標普 12 個月 %", "距高位 %",
        "窗口", "窗口內標普", "窗口內 WTI", "窗口內黃金", "錨點後 12 個月標普", "錨點後 12 個月 WTI", "錨點後 12 個月內最大回撤", "油價", "聯儲", "通脹", "市場", "政治", "產業", "備注"]
header(ws, 3, cols, [8, 30, 9, 9, 7, 9, 7, 8, 9, 8, 9, 7, 8, 9, 8, 18, 10, 10, 10, 11, 11, 12, 26, 30, 14, 36, 30, 22, 44])
ws.freeze_panes = "C4"
for i, e in enumerate(eps, 4):
    s = e["stats"]
    vals = [None if s["dist"] is None else 1 + sum(1 for x in rank if x["stats"]["dist"] < s["dist"]), e["title"], e["anchor"], s["dist"], s["wti"], s["oil_12m"], s["cpi_yoy"], s["irx"], s["irx_3m"], s["y10"], s["y10_12m"], s["slope"], s["real_rate"], s["sp_12m"], s["sp_dd"],
            f'{e["span"][0]}→{e["span"][1]}', e["span_ret"]["sp"], e["span_ret"]["wti"], e["span_ret"]["gold"], e["after12"]["sp"], e["after12"]["wti"], None if e["maxdd12"] is None else e["maxdd12"] / 100,
            e["oil"], e["fed"], e["infl"], e["mkt"], e["politics"], e["tech"], e["note"]]
    for j, v in enumerate(vals, 1):
        c = put(ws, i, j, v, wrap=(j >= 23))
        if j in (17, 18, 19, 20, 21, 22) and isinstance(v, float): pct(c)
    ws.row_dimensions[i].height = 45

# ================= 板塊回報 ===================================================================
ws = wb.create_sheet("板塊回報"); title(ws, "每個對標時期邊類股票跑贏／跑輸（總回報，含股息；ETF／指數同長壽股等權籃 —— 籃只有倖存者，數字偏高）")
header(ws, 3, ["時期", "類別", "種類", "代號", "成分數", "窗口內回報", "窗口內標普", "窗口內超額（公式）", "錨點後 12 個月回報", "錨點後 12 個月標普", "錨點後 12 個月超額（公式）", "成分（籃）"],
       [26, 24, 10, 10, 7, 11, 11, 13, 13, 13, 15, 80])
ws.freeze_panes = "A4"; r = 4
for e in eps:
    put(ws, r, 1, f'{e["key"]} {e["title"]}　窗口 {e["span"][0]}→{e["span"][1]}　錨點 {e["anchor"]}', bold=True)
    for j in range(1, 13): ws.cell(row=r, column=j).fill = SUB
    r += 1
    spw, spa = e["sp_tr"]["win"], e["sp_tr"]["after"]
    for g in e["groups"]:
        put(ws, r, 1, e["key"]); put(ws, r, 2, g["group"]); put(ws, r, 3, g["kind"])
        if g["sym"]: link(ws, r, 4, g["sym"])
        put(ws, r, 5, g["n"])
        pct(put(ws, r, 6, g["win"])); pct(put(ws, r, 7, spw))
        pct(put(ws, r, 8, f"=IF(OR(F{r}=\"\",G{r}=\"\"),\"\",F{r}-G{r})"))
        pct(put(ws, r, 9, g["after"])); pct(put(ws, r, 10, spa))
        pct(put(ws, r, 11, f"=IF(OR(I{r}=\"\",J{r}=\"\"),\"\",I{r}-J{r})"))
        if g.get("members"): put(ws, r, 12, " ".join(g["members"]))
        r += 1
    r += 1

# ================= 長壽股籃成分 ===============================================================
ws = wb.create_sheet("長壽股籃成分"); title(ws, "長壽股等權籃嘅成分（Yahoo 月線首月；籃入面只有今日仍上市嘅公司，所以 1970–80 年代嘅回報有倖存者偏差）")
header(ws, 3, ["板塊", "代號", "Yahoo 數據首月"], [16, 10, 16])
import importlib; MR = importlib.import_module("macro_regimes")
r = 4
for sec in MR.BASKET_ORDER:
    for s in MR.SECTOR_OF[sec]:
        if s in J["yahoo_first"]:
            put(ws, r, 1, sec); link(ws, r, 2, s); put(ws, r, 3, J["yahoo_first"][s]); r += 1

# ================= 相似度 =====================================================================
ws = wb.create_sheet("相似度"); title(ws, f"1962 年起每個月同 {NOWM} 嘅加權 z 距離：最近嘅 12 個月份（互相至少相隔 18 個月）同之後嘅標普表現")
header(ws, 3, ["月份", "距離"] + [desc[f] for f in sim["features"]] + ["之後 6 個月標普", "之後 12 個月標普", "12 個月內最大回撤", "之後 24 個月標普", "24 個月內最大回撤"], [10, 8] + [13] * 9 + [12, 12, 12, 12, 12])
r = 4
put(ws, r, 1, f"{NOWM}（現在）", bold=True); put(ws, r, 2, 0)
for j, f in enumerate(sim["features"], 3): put(ws, r, j, sim["now"][f])
r += 1; t0 = r
for x in sim["top"]:
    put(ws, r, 1, x["month"]); put(ws, r, 2, x["dist"])
    for j, f in enumerate(sim["features"], 3): put(ws, r, j, x[f])
    for j, key in ((12, "fwd6"), (13, "fwd12"), (14, "maxdd12"), (15, "fwd24"), (16, "maxdd24")):
        pct(put(ws, r, j, None if x[key] is None else x[key] / 100))
    r += 1
put(ws, r, 1, "中位數（公式）", bold=True)
for j in (12, 13, 14, 15, 16): pct(put(ws, r, j, f"=MEDIAN({gl(j)}{t0}:{gl(j)}{r - 1})"))
r += 1
put(ws, r, 1, "上升次數（公式）", bold=True)
for j in (12, 13, 15): put(ws, r, j, f'=COUNTIF({gl(j)}{t0}:{gl(j)}{r - 2},">0")&"/"&COUNT({gl(j)}{t0}:{gl(j)}{r - 2})')
r += 2
put(ws, r, 1, "全樣本基準（1962 年起所有月份）", bold=True); r += 1
for k, v in (("之後 12 個月中位數", sim["base"]["fwd12_median"] / 100), ("之後 12 個月上升比例", sim["base"]["fwd12_pos"] / 100), ("之後 6 個月中位數", sim["base"]["fwd6_median"] / 100), ("12 個月內最大回撤中位數", sim["base"]["maxdd12_median"] / 100),
             ("之後 24 個月中位數", sim["base"]["fwd24_median"] / 100), ("24 個月內最大回撤中位數", sim["base"]["maxdd24_median"] / 100)):
    put(ws, r, 1, k); pct(put(ws, r, 2, v)); r += 1
r += 1
put(ws, r, 1, "權重", bold=True); r += 1
for f in sim["features"]: put(ws, r, 1, desc[f]); put(ws, r, 2, sim["weights"][f]); r += 1

# ================= 月度數據 ===================================================================
ws = wb.create_sheet("月度數據"); title(ws, "月度數據（月底；1986 年前油價為官方牌價錨點內插；CPI 2023-10 後由 BLS 公布嘅按年變化推算；詳見注釋）")
series = ["sp", "sp_real", "cpi_yoy", "wti", "oil_real", "y10", "irx", "gold", "vix", "ixic", "sp_dd", "dxy"]
names = {"sp": "標普 500", "sp_real": "標普 實質（2026 物價）", "cpi_yoy": "CPI 按年 %", "wti": "WTI $", "oil_real": "WTI 實質", "y10": "10 年期 %", "irx": "3 個月息 %", "gold": "黃金 $", "vix": "VIX", "ixic": "納指", "sp_dd": "標普距 24 個月高位 %", "dxy": "美元指數"}
header(ws, 3, ["月份"] + [names[s] for s in series], [10] + [13] * len(series)); ws.freeze_panes = "B4"
for i, m in enumerate(J["months"], 4):
    put(ws, i, 1, m)
    for j, s in enumerate(series, 2):
        v = J["frame"][s][i - 4]
        if v is not None: put(ws, i, j, v)

# ================= 圖表 =======================================================================
ws = wb.create_sheet("圖表"); title(ws, "圖表（PNG 亦喺 reports/macro/）")
r = 3
for f, cap in (("01_four_forces.png", "① 四大力量牛熊周期 1960–2026"), ("02_analogues.png", "② 十個對標時期 vs 2026（錨點前後）"), ("03_sectors.png", "③ 板塊超額回報熱圖"), ("04_similarity.png", "④ 相似度時序")):
    p = f"{REPO}/reports/macro/{f}"
    if os.path.exists(p):
        put(ws, r, 1, cap, bold=True); img = XLImage(p); scale = 1400 / img.width; img.width, img.height = int(img.width * scale), int(img.height * scale)
        ws.add_image(img, f"A{r + 1}"); r += int(img.height / 20) + 4

# ================= 注釋 =======================================================================
ws = wb.create_sheet("注釋"); title(ws, "數據來源、補值同限制")
ws.column_dimensions["A"].width = 26; ws.column_dimensions["B"].width = 140
notes = [
    ("標普 500", "Yahoo ^GSPC 月底收市（1962 起，由日線重取樣）；之前用 Shiller 月均；10 月用 10-01 收市 7,743。板塊同長壽股用 Yahoo 調整收市（含股息）"),
    ("CPI", "Shiller 月度 CPI 至 2023-09；之後用 BLS 公布嘅按年變化推算指數：" + "、".join(f"{k} {v}" for k, v in J["cpi_recent"].items())),
    ("油價", "WTI 現貨日線（EIA 經 datahub 鏡像）1986 起，月均；1986 年前用 BP 統計年鑑官方牌價錨點（Arabian Light）對數線性內插，年內路徑係近似；Brent 現貨 2026-04-07 $138.2、09-15 $130.8 係 EIA 歐洲現貨（實物溢價），期貨當日約 $108–118"),
    ("利率", "10 年期：FRED GS10 月均（datahub 鏡像）至 2026-08，之後 Yahoo ^TNX 月底；政策利率代理：Yahoo ^IRX 13 周國庫券（1960 起）—— 唔係聯邦基金利率，1970 年代兩者差距可達 1–2 點"),
    ("黃金、VIX", "datahub 鏡像月度（金）同日線（VIX，1990 起）"),
    ("補值", "; ".join(f"{k}: " + ", ".join(f"{m} = {v[0]}（{v[1]}）" for m, v in d.items()) for k, d in J["patches"].items())),
    ("相似度", "九項特徵對 1962 年起全部月份 z 標準化，加權歐氏距離；排除最近 24 個月；最近月份之間至少相隔 18 個月。權重係判斷（油價同息口方向加重），唔係擬合"),
    ("板塊回報", "1998-12 起用 SPDR 板塊 ETF 同指數（^OSX 1997、^SOX 1994、^BKX 1993、^DJT 1992、^HGX 2002、IYR 2000、IWD/IWF 2000、TLT 2002、GLD 2004）；1998 年前用今日仍上市嘅公司等權籃，只計窗口內有完整數據嘅股票 —— 倖存者偏差令 1970–80 年代籃嘅回報偏高、1987／1990 年代科技籃偏高（2000 年窗口籃 +93 vs XLK −17 就係例證），所以熱圖同結論以 ETF 為準，籃只用於冇 ETF 嘅年代，並標 *"),
    ("周期界定", "衰退：NBER；加減息周期：聯邦基金目標轉向月（手工表 scripts/macro_events.py）；熊市：月線收市由高位跌 ≥20%；中期年回撤：年內月線收市對年內前高"),
    ("事實核對", "聯儲 09-16 加息、點陣圖、CME FedWatch、10 年期 5.342%、CPI 月度、油價同荷姆茲時序、關稅裁決、就業、美元同金價均來自 2026-10-02 當日網上報道（結論頁同現時數據頁列明來源）"),
    ("限制", "① 1960 年前冇政策利率代理，相似度由 1962 起；② 月線解像度，日內／周內極端（1987-10-19）被平滑；③ 對標係統計上嘅相似，唔係因果 —— 樣本只有十幾個油震／加息周期；④ 2026 嘅油震發生喺美國係淨出口國、AI 資本開支佔 GDP 比重創新高嘅背景，歷史上冇先例"),
]
for i, (k, v) in enumerate(notes, 3):
    put(ws, i, 1, k, bold=True); put(ws, i, 2, v, wrap=True); ws.row_dimensions[i].height = max(30, 15 * (len(v) // 90 + 1))

wb.save(OUT); print("saved", OUT)

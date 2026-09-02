#!/usr/bin/env python3
"""Second pass of the R7 critical review: content-lens and ranking-lens outcome.

Runs AFTER merge_news8.py and apply_review8.py; edits data/news8.json and
data/review8.json in place (idempotent — re-running is a no-op).

What it does (all spec-preserving; nothing here changes the screening rules):
  1. Price moves quoted in the blurbs are corrected to close-to-close figures
     from data/series4.pkl (after-hours / pre-market numbers, wrong days, and
     "52週低" claims contradicted by the series).
  2. Stale "current price" phrasing ("股價升返$8.16") is rewritten.
  3. Catalyst badges that are analyst notes get the new kind 評級; badges whose
     event day actually closed down get a red "事件日 −X%" warning
     (review8.json → catalyst_warn) so the reader does not mistake the decline
     cause for the recovery catalyst.
  4. 信心 is capped by the sources: 高 needs ≥2 article URLs; a row whose only
     sources are quote pages becomes 低; titles-without-URL cap at 中.
  5. Hot spans that only quote the price reaction (circular) are dropped when
     an event span remains.
  6. Deal flags for TXNM (delayed take-private) and VOYA (activist sale pressure).
  7. Review notes for the ranking-lens findings the user has to decide on.
Optional: FACT_JSON (scratchpad r8_fact_1.json, web fact-check) feeds a second
edit table — see EDITS_FACT below — applied only for questions marked verified.
"""
import json, os, pickle, re

SCRATCH = os.environ.get("WORK_DIR", "./data")
FACT = os.environ.get("FACT_JSON", "/tmp/claude-0/-home-user-10MA-watchlist/"
                      "1821eb3b-7002-5041-b904-77ace4d47850/scratchpad/r8_fact_1.json")

news = json.load(open(f"{SCRATCH}/news8.json"))
review = json.load(open(f"{SCRATCH}/review8.json"))
scr = json.load(open(f"{SCRATCH}/screen_results8.json"))
listed = {r["sym"]: r for r in scr["page1"]}
d = pickle.load(open(f"{SCRATCH}/{os.environ.get('SERIES', 'series4.pkl')}", "rb"))
CAL, SER = d["cal"], d["series"]
IDX = {c: i for i, c in enumerate(CAL)}
log, problems = [], []


def ret_on(sym, date):
    fi, cs, vs, ff = SER[sym]; j = IDX[date] - fi
    return (cs[j] / cs[j - 1] - 1) * 100


def close_on(sym, date):
    fi, cs, vs, ff = SER[sym]; return SER[sym][1][IDX[date] - fi]


def edit(sym, old, new):
    """Replace `old` by `new` in whichever blurb contains it (idempotent)."""
    e = news.get(sym)
    if not e: problems.append(f"{sym}: not in news8"); return
    for k in ("decline_short", "recovery_short"):
        if old in e[k]:
            e[k] = e[k].replace(old, new, 1); log.append(f"{sym}: {k} «{old[:24]}» → «{new[:24]}»"); return
        if new in e[k]:
            return  # already applied
    problems.append(f"{sym}: phrase not found «{old}»")


# ---- 1/2. blurb corrections (every number below was checked against series4.pkl) ----
EDITS = [
    ("FIVE", "Q1經調整EPS $2.22遠勝$1.69；8月13日Jefferies升至買入、目標價由$210抽上$350",
             "6月Q1業績日曾跌13.8%；8月13日Jefferies升至買入、目標價由$210抽上$350，消費股回暖下重拾升勢"),
    ("FCX", "單日跌3.9%", "業績日收跌2.3%"),
    ("EFX", "7月21日公布Q2後急挫逾7%", "7月21日公布Q2後三日累挫7.4%"),
    ("GLOB", "單日瀉17%", "單日收瀉8.8%"),
    ("NOW", "翌日抽6.1%", "翌日先跌3.7%見底、再翌日抽7.4%"),
    ("CAI", "盤後飆15.26%", "翌日收升21.6%"),
    ("RCEL", "8月6日Q2收入創新高2170萬美元、盤前飆21.7%；8月18日PermeaDerm試驗效果媲美屍皮但平七成，單日抽25%",
             "8月6日Q2收入創新高2170萬美元，翌日收升63.6%；8月18日PermeaDerm試驗效果媲美屍皮但平七成，單日抽24.7%"),
    ("A", "上調全年指引，盤後升3.17%", "上調全年指引，翌日僅升1.9%後連跌三日，已跌穿8月24日底$153.43"),
    ("NUE", "8月24日美加談判破裂單日升4%", "8月24日美加談判破裂、關稅減免憂慮消退，8月21至25日累升2.9%"),
    ("PMTS", "單日飆13%", "兩日累升22%"),
    ("WDAY", "挫約57%", "挫約54%"),
    ("WDAY", "單日飆18%創十年最佳", "單日飆12.1%"),
    ("TWLO", "單日飆15.7%", "單日飆24.9%"),
    ("EPAM", "盤前瀉9%", "單日收瀉15.3%"),
    ("SBH", "股價仍插5.3%至$14.01；", "股價仍插5.3%；"),
    ("VREX", "6月29日插至$9.98近52週低", "6月29日插至$9.98，重返5月低位（$9.32）附近"),
    ("ZBH", "7月1日跌至$84.17近52週低", "7月1日跌至$84.17，重返5月低位（$79.58）上方"),
    ("TW", "單日瀉12%見52週低位", "單日瀉9.6%至$97.80，重返7月9日低位附近"),
    ("TW", "股價由$97回升至$108以上", "股價由$97回升至$107水平"),
    ("CXM", "股價升返$8.16", "股價一度升返$8.16，9月1日再跌7.4%至$7.60"),
    ("CHRD", "股價升至$146", "股價升至$150水平"),
    ("SENEA", "連創歷史新高見$196.50", "連創歷史新高並升穿$200"),
    ("SBET", "8月下旬單日彈13.75%，股價重上$8.20", "8月19日單日彈12.6%，股價重上$8"),
    ("VOYA", "（遣散費兼另類投資虧損）跌5.6%；8月6日TOMS發起不信任投票，8月20日見低",
             "（遣散費兼另類投資虧損）；8月6日TOMS發起不信任投票，其後陰跌至8月20日$97.49見低"),
    ("OOMA", "7月29日憑AirDial增長預期急升6.5%", "7月28日憑AirDial增長預期急升6.5%"),
    ("ACN", "6月23日加碼回購20億美元", "6月23日（底部前一週）加碼回購20億美元"),
    ("HALO", "單日急升18%創歷史新高", "翌日急升20.2%創歷史新高"),
    ("INSP", "單日彈13.6%", "單日彈22.8%"),
    ("JNJ", "Q2收入創紀錄$253億、升6.6%，EPS $2.90勝預期並上調全年銷售及盈利指引，腫瘤及免疫新藥監管捷報接力推升",
            "Q2（收入創紀錄$253億、上調全年指引）當日跌2.7%後獲消化，腫瘤及免疫新藥監管捷報接力推升"),
]
for sym, old, new in EDITS:
    if sym in listed: edit(sym, old, new)

# ---- 3a. badge relabels: analyst-driven → 評級; plans named as plans; stale deal ----
CAT = {
    "FIVE": ("升評級·目標價$350", "評級"),
    "EFX": ("升評級至買入", "評級"),
    "ANRO": ("大行升目標價至$37", "評級"),
    "ZS": ("摩通升目標價", "評級"),
    "FDS": ("大行上調目標價", "評級"),
    "NTSK": ("大行上調目標價", "評級"),
    "PAYX": ("Citi升目標價至$150", "評級"),      # Paycor closed in 2025 — not a catalyst for this move
    "ANGO": ("獲醫保覆蓋", "監管"),
    "ACHV": ("私募$3.54億兼重交NDA", "監管"),
    "PMTS": ("Q2業績兩日升22%", "業績"),
    "WDAY": ("傳銀湖私有化", "併購"),
    "SLDB": ("SGT-003耐受良好", "臨床"),
    "MGTX": ("bota-vec擬年內報批", "監管"),
    "HALO": ("Q2大勝翌日飆20%", "業績"),
}
for sym, (cat, kind) in CAT.items():
    e = news.get(sym)
    if not e or sym not in listed: continue
    if (e["catalyst"], e["ckind"]) != (cat, kind):
        log.append(f"{sym}: badge «{e['catalyst']}/{e['ckind']}» → «{cat}/{kind}»")
        e["catalyst"], e["ckind"] = cat, kind

# ---- 3b. badge event that the market sold: red warning on the badge ----
CWARN = {  # sym → (event close date, what the badge names)
    "JNJ": ("2026-07-15", "Q2 業績日"),
    "FCX": ("2026-07-23", "Q2 業績日"),
    "GLOB": ("2026-08-14", "Q2 業績日（同一份報告削全年指引）"),
    "HUBS": ("2026-08-06", "回購同日公布 Q2 指引遜預期"),
    "TRI": ("2026-08-05", "Q2 業績日"),
    "SXC": ("2026-07-30", "Q2 業績日"),
    "ATRC": ("2026-07-31", "Q2 業績翌日"),
}
review["catalyst_warn"] = {}
for sym, (day, what) in CWARN.items():
    if sym not in listed: continue
    r = ret_on(sym, day)
    review["catalyst_warn"][sym] = {
        "day": day[5:].replace("-", "/"), "ret": round(r, 1),
        "text": f"{what}（{day[5:].replace('-', '/')}）收市跌 {abs(r):.1f}%：badge 所指嘅事件當日被市場沽售，回升係其後嘅事；催化劑同下跌原因係同一件事。",
    }

# ---- explicit hot-span rewrites for rows whose text changed above ----
HOT = {
    "FIVE": ["Jefferies升至買入、目標價由$210抽上$350"],
    "JNJ": ["上調全年指引", "腫瘤及免疫新藥監管捷報"],
    "HUBS": ["$10億回購"],
    "NOW": ["AI年合約值破$10億", "Salesforce勁績再飆9%"],
    "ATRC": ["經調整EPS $0.18勝預期-$0.01", "BTIG升目標價至$55"],
    "CAI": ["Q2收入升45%", "上調全年指引至10.3-10.4億美元"],
    "RCEL": ["Q2收入創新高2170萬美元", "PermeaDerm試驗效果媲美屍皮但平七成"],
    "NUE": ["熱軋卷提價至1135美元", "美加談判破裂"],
    "PMTS": ["收入1.49億勝預期", "自由現金流創紀錄"],
    "SAIL": ["ARR升26%至$11.63億"],
    "WDAY": ["Silver Lake洽私有化", "AI佔新增ACV逾25%"],
    "TWLO": ["全年增長指引由14-15%上調至18-18.5%"],
    "SBET": ["撥$2億ETH予Lido做質押", "累計回購逾400萬股"],
    "PAYX": ["Citi升至$150"],
    "MAIN": ["每季加派0.3美元特別息"],
    "HALO": ["收入$4.81億升48%", "EPS $2.28大勝預期"],
    "INSP": ["EBITDA勝40.5%", "全年指引上調至8.55億"],
}
for sym, hot in HOT.items():
    e = news.get(sym)
    if not e or sym not in listed: continue
    if e["hot"] != hot:
        log.append(f"{sym}: hot {e['hot']} → {hot}"); e["hot"] = hot

# ---- 5. drop price-only hot spans (keep ≥1 span) ----
PRICE = re.compile(r"\d+(?:\.\d+)?%")
MOVE = re.compile(r"飆|彈|升|抽|反彈|漲|爆升|急升|新高|最佳")
EVENT = re.compile(r"收入|EPS|盈|利|指引|ARR|ASV|目標價|評級|回購|息|收購|合約|訂單|試驗|數據|批|銷|增長|量|ACV|EBITDA|毛利|現金流|派|流量|提價|價至|美元|億|萬|市佔|訂閱|客|ETH|BTC|勝|預期|按年|按季|同店|部門|開單|幣|勁績|業績|財報|Repatha")
dropped_spans = []
for sym in listed:
    e = news.get(sym)
    if not e or len(e["hot"]) < 2: continue
    keep = [h for h in e["hot"] if not (PRICE.search(h) and MOVE.search(h) and not EVENT.search(h))]
    if keep and keep != e["hot"]:
        dropped_spans.append((sym, [h for h in e["hot"] if h not in keep])); e["hot"] = keep

# ---- 4. confidence capped by the sources ----
QUOTE = re.compile(r"stockanalysis\.com|cnbc\.com/quotes|macrotrends|tradingview\.com/symbols|investing\.com/equities|google\.com/finance|finance\.yahoo\.com/quote", re.I)
ORDER = {"低": 0, "中": 1, "高": 2}
conf_changes = []
for sym in listed:
    e = news.get(sym)
    if not e: continue
    src = e.get("sources") or []
    urls = [u for u in src if re.match(r"https?://", u)]
    titles = [u for u in src if not re.match(r"https?://", u)]
    art = [u for u in urls if not QUOTE.search(u)]
    cap = "高" if len(art) >= 2 else ("中" if (art or titles) else "低")
    if ORDER[cap] < ORDER[e["confidence"]]:
        conf_changes.append(f"{sym} {e['confidence']}→{cap}"); e["confidence"] = cap

# ---- 6. deal flags: TXNM (delayed take-private), VOYA (activist pressure) ----
if "TXNM" in listed:
    c = listed["TXNM"]["close"]; off = 61.25
    review["ticker_flags"]["TXNM"] = {
        "badge": f"併購目標 · 距作價+{(off / c - 1) * 100:.1f}%",
        "text": f"Blackstone Infrastructure $61.25 現金私有化，協議已延至 2027-05-31（NMPRC 審批暫停）；現價 ${c:g} 折讓反映審批風險，走勢由交易進度而非基本面主導。",
    }
if "VOYA" in listed:
    review["ticker_flags"]["VOYA"] = {
        "badge": "併購憧憬 · 迫售壓力",
        "text": "TOMS Capital（持股 4.5%）施壓推動出售或策略檢討，未有作價；反彈含併購憧憬成分，消息落空會令波幅跳升。",
    }

# ---- 7. notes for the ranking / content lenses (keyed by title → idempotent) ----
NOTES = [
    {"title": "[已修正] 總表斜率／MA 欄統一為 MA10（10 日）",
     "text": "R7 總表每行嘅斜率、MA 同「低於MA」沿用該股第一個出現嘅子頁（62 行係 5MA／5 日、6 行係 10MA／21 或 42 日），按斜率排序其實係將唔同窗口混埋比較。R8 總表統一用 MA10 較 10 日前嘅斜率（同 PAGE 3 一致），子頁維持各自時間框。"},
    {"title": "[已修正] 回升原因引用嘅價格變動改為收市對收市",
     "text": "13 行引用盤後／盤前或錯日數字（CAI「盤後飆15.26%」實為翌日收升 21.6%、RCEL「盤前飆21.7%」實為翌日 +63.6%、TWLO 15.7%→24.9%、WDAY 18%→12.1%、EPAM 盤前 −9%→收 −15.3%、GLOB −17%→−8.8%、NUE 8月24日「單日升4%」實為 +0.4%、PMTS 13%→兩日 22%、HALO 18%→20.2%、INSP 13.6%→22.8%、EFX、FCX、SBET），以及「52週低」而序列有更低收市嘅 VREX、ZBH、TW 用字，全部按 series4 收市重寫。",
     "tickers": ["CAI", "RCEL", "TWLO", "WDAY", "EPAM", "GLOB", "NUE", "PMTS", "HALO", "INSP", "EFX", "FCX", "SBET", "VREX", "ZBH", "TW"]},
    {"title": "[已修正] 過時「現價」用字",
     "text": "CXM「升返$8.16」（9月1日已跌 7.4% 至 $7.60）、TW「$108以上」（$106.71）、CHRD「$146」（$150.41）、SENEA「$196.50」（已升穿 $200）、SBET「$8.20」、A「盤後升3.17%」（其後三日跌穿 8月24日底）已改寫。",
     "tickers": ["CXM", "TW", "CHRD", "SENEA", "SBET", "A"]},
    {"title": "[已標記] 催化劑 badge 所指事件當日其實跌",
     "text": "JNJ、FCX、GLOB、HUBS、TRI、SXC、ATRC 嘅 badge 引用嘅係下跌原因同一份業績／公告（事件日收市跌 2.3%–19.1%），回升係其後嘅事。badge 加紅色「事件日 −X%」標記，唔刪除研究內容；FIVE、ANRO 改為引用真正推動回升嘅評級／目標價。",
     "tickers": ["JNJ", "FCX", "GLOB", "HUBS", "TRI", "SXC", "ATRC", "FIVE", "ANRO"]},
    {"title": "[已修正] 分析員評級另立「評級」類別；計劃／過時交易改名",
     "text": "ZS、FDS、NTSK、EFX、FIVE、ANRO、PAYX 嘅 badge 其實係目標價／評級變動而非公司事件，改為新類別「評級」（PAYX 原標「Paycor併購協同」——Paycor 2025 年已完成，非本次回升催化劑）；ANGO 由「業績」改「監管」（Medicare 覆蓋）；SLDB 改為已發生嘅安全數據（原標尚未發生嘅 FDA 商談）、MGTX 標明「擬」報批；HALO／PMTS badge 數字改正。",
     "tickers": ["ZS", "FDS", "NTSK", "EFX", "FIVE", "ANRO", "PAYX", "ANGO", "SLDB", "MGTX", "HALO", "PMTS"]},
    {"title": "[已修正] 信心標籤改由來源決定上限",
     "text": "R1 時期研究 85% 標「高」但只有 9/55 有一手來源；NDAQ 標「高」而來源只係兩個報價頁。R8 起：「高」需 ≥2 個可點擊嘅新聞／公告 URL，只有標題無 URL 嘅上限「中」，只有報價頁嘅降為「低」（唔會自動上調）。"},
    {"title": "[已修正] 熱炒 highlight 唔再標示股價反應本身",
     "text": "「單日飆18%」「盤後急升逾10%」呢類 span 係結果唔係催化劑，會令讀者以為有第二件事。凡仍有事件 span 嘅行，純價格 span 一律移除。"},
    {"title": "[備註] 回升原因未必解釋首個底部",
     "text": "內容審視發現 134 行有日期嘅回升原因中，58 行有 >60% 升幅發生喺所指催化劑之前（例如 EFX、A、TRI、MDB、S、WDAY），ACN、KFY、KMX、SRPT 嘅催化劑更早於首個底部。呢啲文字描述嘅係「最近一件事」而非「由底回升嘅原因」；R8 未逐行重寫（需要重新研究 58 隻），下一版研究 prompt 會要求以首個底部日期為錨。"},
    {"title": "[待你決定] 確定性三項（45% 權重）會被「一日小回」全數攞滿",
     "text": "當最後兩個底之間嘅中間高位只高過上一個底 <1%（總表 top 50 有 13 隻，例如 MAN、RRC、BIIB、MANH、SPSC），突破、回補、回撤遞減三項自動接近滿分（44.4–44.9／45），而一個真正 10% 基底回補 90% 只得約 27.5 分；同時 top 50 入面突破／均線／回補三項分別有 49／48／36 隻係 1.0，確定性排序實際上由守底日數同量比決定，並偏向已升離樞紐 5–15% 嘅股票。建議：突破需 ≥ 中間高位 ×1.01 並對超出 5% 者扣分；或去掉均線項（MA 上升門檻已隱含）重新加權。",
     "tickers": ["MAN", "RRC", "BIIB", "MANH", "SPSC"]},
    {"title": "[待你決定] 回撤遞減嘅「首段」只睇底部前 10 日",
     "text": "首段跌幅只用第一個底之前 10 個交易日嘅高位（README 規則⑥無此限制），總表 57/171 行喺 25 日內有高出 >3% 嘅高位：NDAQ 首段 2.4% 應為 9.1%（少計約 4.5 分）、DMLP／ARLP／GEL 嘅比率由 >1 變 <1。呢個上限承自 20MA R3，改動會令各版本唔可比，所以留俾你決定。",
     "tickers": ["NDAQ", "DMLP", "ARLP", "GEL"]},
    {"title": "[待你決定] MA 連升 3 日門檻無最低幅度",
     "text": "釘價股 VREX、QTWO、ITGR、OGN、BWMN 以 0.5–1.6 個基點嘅日升幅通過「MA 最後 3 日逐日上升」，總表 top 50 有 12 隻通過幅度 <5 個基點，令佢哋嘅時間框數目（總表每個時間框值 5 分）近乎隨機。建議：日升幅需 ≥0.01%，或直接剔除釘價股。",
     "tickers": ["VREX", "QTWO", "ITGR", "OGN", "BWMN"]},
]
by_title = {n["title"]: n for n in review["notes"]}
for n in NOTES:
    by_title[n["title"]] = n
# keep the original order, append new ones after the last [已修正]/[已標記] group
old_titles = [n["title"] for n in review["notes"]]
merged = [by_title[t] for t in old_titles]
new = [n for n in NOTES if n["title"] not in old_titles]
fixed = [n for n in new if n["title"].startswith(("[已修正]", "[已標記]", "[備註]"))]
asks = [n for n in new if n["title"].startswith("[待你決定]")]
# insert fixed notes before the first [紅色標記 / 待你決定] note, asks at the end
cut = next((i for i, n in enumerate(merged) if n["title"].startswith(("[紅色標記", "[待你決定]"))), len(merged))
review["notes"] = merged[:cut] + fixed + merged[cut:] + asks

# augment the existing VCP-gap / coverage notes with the lens's numbers (idempotent)
for n in review["notes"]:
    if n["title"].startswith("[待你決定] VCP 獎勵") and "中位數少 12.9 分" not in n["text"]:
        n["text"] += " 審視量化：總表 top 50 有 16 隻嘅 VCP 靠分母窗口內一個 >15% 跳空日撐起，剔除該日後 VCP 中位數少 12.9 分（AGEN 76→52、HALO 73→50、XGN 50→24、NIQ 57→29）。"
    if n["title"].startswith("[待你決定] 覆蓋度同確定性") and "每多一個時間框值 6.25" not in n["text"]:
        n["text"] += " 審視量化：總表分數 = 0.8×綜合 + 5×時間框數，每多一個時間框值 6.25 個綜合分；top 20 入面 10 隻 3 個時間框嘅股票欠嘅都係 PAGE 2，而且全部只係差「5MA 最後 3 日逐日升」一項。BIIB（綜合 79.8）因此排喺 MANH（71.7）之後。"

rn = "R8 修正（唔改規則）：總表斜率／MA 統一用 MA10／10 日；回升原因嘅價格數字改為收市對收市；催化劑屬分析員評級者另立「評級」類別，事件日下跌者加紅色標記；信心標籤上限由來源決定。"
if rn not in review["rule_notes"]:
    review["rule_notes"].insert(2, rn)

# ---- optional: web fact-check results (agent) ----
EDITS_FACT = {}   # filled by the fact pass below when FACT exists (see apply_fact)
if os.path.exists(FACT):
    facts = {f["sym"]: f for f in json.load(open(FACT))}
    try:
        import sys as _sys; _sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from apply_review8_fact import apply_fact
        apply_fact(news, review, listed, facts, log, problems, ret_on, close_on)
    except ImportError:
        problems.append("apply_review8_fact.py not present; fact results not applied")

# ---- validate hot spans still occur ----
for sym in listed:
    e = news.get(sym)
    if not e: continue
    bad = [h for h in e["hot"] if h not in e["recovery_short"]]
    if bad:
        problems.append(f"{sym}: hot span not in text after edit -> {bad}")
        e["hot"] = [h for h in e["hot"] if h in e["recovery_short"]]
    if len(e["catalyst"]) > 14: problems.append(f"{sym}: catalyst too long -> {e['catalyst']}")

json.dump(news, open(f"{SCRATCH}/news8.json", "w"), ensure_ascii=False, indent=1)
json.dump(review, open(f"{SCRATCH}/review8.json", "w"), ensure_ascii=False, indent=1)
print(f"edits {len(log)} · confidence changes {len(conf_changes)} · price-only spans dropped {len(dropped_spans)} · "
      f"catalyst warnings {len(review['catalyst_warn'])} · notes {len(review['notes'])} · flags {len(review['ticker_flags'])}")
for l in log: print("  -", l)
print("confidence:", conf_changes)
print("dropped spans:", dropped_spans)
if problems:
    print(f"PROBLEMS ({len(problems)}):")
    for p in problems: print("  !", p)

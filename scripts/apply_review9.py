#!/usr/bin/env python3
"""Carry the review layer forward to R9 and re-derive everything price-dependent.

review8.json was written against the 09-01 close and the R8 list. For R9 the
data date moved to 09-03 and 57 tickers left the lists, so:

  * deal flags are kept only for tickers still listed, and the spread in each
    badge is recomputed from the new close (a stale "+2.3% 距作價" would be
    exactly the kind of thing the R8 content review flagged);
  * catalyst warnings ("the event this badge names closed down") are kept only
    for tickers still listed, with the day's return recomputed from the series;
  * notes are rewritten: the R8 fixes become one lineage note, the open
    user-decisions stay open, and the R9 items are added.

Everything here is presentation/annotation only — no screening rule changes.
"""
import json, os, pickle, re

SCRATCH = os.environ.get("WORK_DIR", "./data")
PREV_REVIEW = os.environ.get("PREV_REVIEW", "review8.json")
OUT = os.environ.get("OUT_REVIEW", "review9.json")
SERIES = os.environ.get("SERIES", "series5.pkl")

scr = json.load(open(f"{SCRATCH}/screen_results9.json"))
news = json.load(open(f"{SCRATCH}/news9.json"))
prev = json.load(open(f"{SCRATCH}/{PREV_REVIEW}"))
listed = {r["sym"]: r for r in scr["page1"]}
d = pickle.load(open(f"{SCRATCH}/{SERIES}", "rb"))
CAL, SER = d["cal"], d["series"]
IDX = {c: i for i, c in enumerate(CAL)}

# cash offers we have verified (source: the entry's own research text / fact-check)
OFFERS = {"VREX": 18.90, "ITGR": 127.0, "BWMN": 43.0, "OGN": 14.0, "NATH": 102.0,
          "GBTG": 9.50, "TXNM": 61.25, "SMTI": 35.0}
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

# every listed ticker whose research says 併購 is a candidate for a flag
for sym in listed:
    e = news.get(sym) or {}
    if e.get("ckind") != "併購":
        continue
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
    elif sym not in flags:
        # an acquirer is not pinned; only tag rows whose own text says the company is the target
        t = (e.get("decline_short", "") + e.get("recovery_short", "") + e.get("catalyst", ""))
        if re.search(r"被收購|收購價|私有化|獲.{0,6}收購|要約|合併獲通過|換股收購", t):
            c = listed[sym]["close"]
            flags[sym] = {"deal": True, "badge": "併購目標",
                          "text": f"研究文字顯示本身係被收購／私有化目標（現價 ${c:g}）：走勢受交易進度牽制，"
                                  "突破同收縮指標量度緊價差而唔係基本面；如果現價已高於作價，市場係喺度賭加價。"}
for sym in RUMOURS:
    if sym in listed and sym not in flags:
        flags[sym] = {"deal": True, "badge": "併購傳聞", "text": RUMOURS[sym]}
for sym, fl in flags.items():          # flags carried from the previous revision
    if "deal" not in fl:
        fl["deal"] = any(k in fl.get("badge", "") for k in ("釘價", "併購", "合併", "作價"))

warns = {}
for sym, w in (prev.get("catalyst_warn") or {}).items():
    if sym not in listed or sym not in SER:
        continue
    day = "2026-" + w["day"].replace("/", "-")
    if day in IDX:
        fi, cs, vs, ff = SER[sym]; j = IDX[day] - fi
        if 0 < j < len(cs):
            w = dict(w, ret=round((cs[j] / cs[j - 1] - 1) * 100, 1))
    warns[sym] = w

KEEP_TITLES = ("[紅色標記", "[待你決定]", "[備註]", "[已加標記]")
open_notes = [n for n in (prev.get("notes") or []) if n["title"].startswith(KEEP_TITLES)]
for n in open_notes:
    n["title"] = n["title"].replace("[紅色標記 · 待你決定]", "[已標記 · 待你決定]")
    n["text"] = n["text"].replace("已加紅色標記", "已加標記").replace("紅色標記", "標記")

last = scr["meta"]["last_date"]
n_new = len([s for s in listed if s not in json.load(open(f"{SCRATCH}/screen_results8.json")) or True])  # placeholder, set below
prev_syms = {r["sym"] for r in json.load(open(f"{SCRATCH}/screen_results8.json"))["page1"]}
n_new = len([s for s in listed if s not in prev_syms])
n_out = len([s for s in prev_syms if s not in listed])

r9_notes = [
    {"title": "[本版做法] 更新內容唔再高亮",
     "text": "R8 將所有相對上一版嘅改動塗紅，睇落太刺眼。R9 起：新上榜、排名升跌、分數變動、文字改動一律只用灰色小字（▲▼、+x%）標示，唔再有紅色、底色或邊框；"
             "「只顯示有實質更新嘅行」掣照用。紅色喺全份報告已經冇咗 —— 剩低嘅顏色只有綠色（達標）同琥珀色（警示：併購釘價、跌穿底、未達標項目）。"},
    {"title": "[本版新增] 催化欄",
     "text": "每隻股票新增一欄，一句講清楚「喺咩催化之下先至由底回升」：日期 · 事件 · 效果。內容由該股自己嘅新聞研究濃縮（新上榜嘅逐隻搜尋，沿用嘅由文字摘要），"
             "純粹跟大市嘅寫「無個股催化 · 隨大市／板塊回升」，可按「有催化先排」排序。"},
    {"title": "[本版新增] 淺色／深色主題掣",
     "text": "頂欄加「淺色／深色」掣，選擇記喺瀏覽器；未揀過就跟你系統設定。兩套配色都經對比度檢查（正文 ≥12:1，灰色更新字 ≥4.7:1）。"},
    {"title": "[已修正] 09-02 冇收市快照：價格照用，成交量當缺失",
     "text": f"鏡像 9月2日嘅 commit 喺美東時間 10:33（開市中途），冇任何 09-02 收市快照。R9 用 09-03 快照嘅官方 net-change 反推每隻股票嘅 09-02 收市價（精確到仙），"
             "但當日成交量完全冇數據，記為 0 並自動歸類為「price-only 日」——唔計入量比、VCP 成交量項同流動性中位數。價格係真實嘅，成交量係缺失嘅，分開處理，"
             "唔會好似補值日咁製造假嘅平盤。"},
    {"title": "[已修正] APH 1 拆 2 重算歷史",
     "text": "Amphenol 喺 9月3日 1 拆 2（鏡像開市中途價 $158.8 → $79.6，反推 09-02 收市 $80.04）。因為冇同日重疊可以對賬，R9 改用鏡像開市中途價做支點檢查兩段比率，"
             "只有「至少減半／翻倍 + 合乎 n:1 比例 + 本身夠流動性上榜」先自動重算歷史 —— 今次只有 APH 一隻。FCUV 等 20–50% 嘅一日波幅視為真實走勢，唔會當拆股改寫歷史。"},
    {"title": f"[本版數據] 更新至 {last} 收盤",
     "text": f"新增 09-02、09-03 兩個交易日（合共 {scr['meta']['n_days']} 日）。總表 {len(listed)} 隻：{n_new} 隻新上榜、{n_out} 隻跌出。"
             "新上榜嘅板塊分佈：醫療保健 15、金融 11、非必需消費 9、工業 8、能源 4；市值分佈：細價 31、大型 15、中型 15；"
             "催化劑 43 隻係季績。跌出嘅 57 隻全部係市場原因（55 隻 MA 條件唔再成立、2 隻一底高於一底破咗），冇一隻因為數據問題。"},
    {"title": "[備註] R8 修正繼續生效",
     "text": "補值日唔製造底部、成交量不完整日唔入量比／VCP、universe 剔除基金／信託／優先股、S&P 500 用 GICS 類別、總表斜率統一 MA10、"
             "分析員評級另立「評級」類別、信心標籤上限由來源決定、催化劑事件日下跌者加標記 —— 全部照舊。"},
]

review = {
    "headline": (
        f"R9 建基於 {last} 收盤（新增 09-02、09-03 兩日）。呢兩日聯儲 Waller 暗示 9 月可以按兵不動、10 年期息率由 4.818% 回落，"
        f"標普兩日累升 1.5%。總表 {n_new} 隻新上榜、{n_out} 隻跌出，跌出嘅 55 隻係四個時間框嘅 MA 條件全部唔再成立、2 隻一底高於一底破咗，冇一隻因為數據問題。"
        "新上榜以醫療保健（15）、金融（11）、非必需消費（9）同工業（8）為主，能源得 4 隻，六成係細價股；"
        "催化劑 43/61 係季績。呢批新股 09-02 至 09-03 兩日中位數升 2.0%（全體合資格股中位數 +0.6%），"
        "但唔好當成「資金轉入油服」——被點名嘅油服股嗰兩日其實回吐（HP −2.6%、TDW −1.6%、BKR 0.0%），佢哋上榜靠嘅係 7–8 月嗰段升幅。"
        "介面方面，所有更新標示改為灰色小字（唔再用紅色高亮）、加咗淺色／深色掣，同埋加咗「催化」欄一句講清楚每隻股票係喺咩事件下先至由底回升。"
        "數據方面最需要留意：09-02 冇收市快照，收市價由 09-03 嘅 net-change 反推（真實），但當日成交量完全缺失（唔入任何成交量指標）。"),
    "notes": r9_notes + open_notes,
    "rule_notes": [
        "R9 修正（唔改規則）：09-02 收市價由 09-03 快照嘅 net-change 反推，當日成交量缺失（記為 0）並自動排除喺量比、VCP 成交量項同流動性中位數之外；"
        "公司行動用鏡像開市中途價做支點，只自動重算「至少減半／翻倍且合乎 n:1 比例」嘅拆股（今次只有 APH）。",
        "R9 介面（唔改規則）：更新內容改用灰色小字，全份報告冇紅色；新增催化欄同淺色／深色主題掣。",
    ] + [r for r in (prev.get("rule_notes") or []) if "待你決定" in r],
    "ticker_flags": flags,
    "catalyst_warn": warns,
}
json.dump(review, open(f"{SCRATCH}/{OUT}", "w"), ensure_ascii=False, indent=1)
print(f"wrote {SCRATCH}/{OUT} · flags {len(flags)} (dropped {len(dropped_flags)}: {dropped_flags}) · "
      f"catalyst warnings {len(warns)} · notes {len(review['notes'])} · new {n_new} · out {n_out}")
print("flags:", {k: v["badge"] for k, v in flags.items()})

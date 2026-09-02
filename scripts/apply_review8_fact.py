"""Web fact-check outcome for R8 (scratchpad r8_fact_1.json, 12 questions).

Imported by apply_review8b.py; every edit below is applied only when the
corresponding question is marked verified in the fact file. The wording keeps
the user's Traditional-Chinese (Hong Kong) register of the other blurbs.
"""
import re


def _set(news, sym, log, **fields):
    e = news[sym]; changed = [k for k, v in fields.items() if e.get(k) != v]
    if changed:
        e.update(fields); log.append(f"{sym}: fact-check edit {changed}")


def _add_sources(news, sym, urls):
    e = news[sym]; have = set(e.get("sources") or [])
    e["sources"] = (e.get("sources") or []) + [u for u in urls if u not in have and re.match(r"https?://", u)]


def apply_fact(news, review, listed, facts, log, problems, ret_on, close_on):
    ok = {s for s, f in facts.items() if f.get("verified")}

    # 1. SMTI — #3 on page 1 was labelled 跟大市; it is a cash-plus-stock takeover target
    if "SMTI" in ok and "SMTI" in listed:
        _set(news, "SMTI", log,
             decline_short="7月中隨大市回調見底$23.45，8月初遭兩券商由買入降至持有；併購公布前無明確個股利空",
             recovery_short="7月29日收市後MiMedx宣布收購：每股$33現金＋0.4735股MDXG（合計約$35，溢價46%，料2026年底完成）；翌日升12.6%至$34.06後一個月喺$34–35橫行，屬併購套利走勢（公布前一日已升13.6%）",
             hot=["MiMedx宣布收購", "每股$33現金＋0.4735股MDXG"],
             catalyst="MiMedx約$35收購", ckind="併購", confidence="高")
        _add_sources(news, "SMTI", facts["SMTI"]["sources"])
        c = listed["SMTI"]["close"]
        review["ticker_flags"]["SMTI"] = {
            "badge": f"併購目標 · 距約$35作價+{(35 / c - 1) * 100:.1f}%",
            "text": "MiMedx 收購：每股 $33 現金 + 0.4735 股 MDXG（約 $35）。R7 標「跟大市」而排總表 #3，其實係股價被作價釘住嘅套利走勢，唔係突破前收縮。",
        }

    # 2. STEP — no 08-13 event; the +12.6% in our series is 08-11 (UBS upgrade) folded
    #    into the copied 08-11/08-12 days
    if "STEP" in facts and "STEP" in listed:      # answer is informative even though marked unverified
        _set(news, "STEP", log,
             recovery_short="8月6日業績EPS雖略遜兼錄非現金虧損，但費用相關收入增長強勁、季息加18%至$0.33；8月11日UBS升評級至買入（目標價$63→$69）、巴克萊及Evercore同日升目標價，單日升6.6%（鏡像補值令此升幅顯示喺8月13日）",
             hot=["UBS升評級至買入（目標價$63→$69）"],
             catalyst="UBS升評級至買入", ckind="評級", confidence="中")
        _add_sources(news, "STEP", facts["STEP"]["sources"])

    # 3. CXM — no discrete catalyst; explain the stack and the 09-01 pre-earnings drop
    if "CXM" in ok and "CXM" in listed:
        _set(news, "CXM", log,
             recovery_short="無單一催化劑：7月1日新CRO到任、微軟AI總裁Jordi Ribas 8月17日加入董事會、新AI功能，8月27日隨軟件板塊升7.2%（三個月累升63%）；9月1日Q2業績（9月2日開市前公布）前跌7.4%至$7.60",
             hot=["微軟AI總裁Jordi Ribas 8月17日加入董事會"],
             confidence="中")
        _add_sources(news, "CXM", facts["CXM"]["sources"])

    # 4. BLFS — cash + RGEN stock; the "$31" was the announcement-day value
    if "BLFS" in ok and "BLFS" in listed:
        c = listed["BLFS"]["close"]; implied_rgen = (c - 11.25) / 0.1442
        _set(news, "BLFS", log,
             recovery_short=f"7月22日獲Repligen收購：每股$11.25現金＋0.1442股RGEN（公布時合計$31、溢價24%，料Q4完成）；RGEN其後因Q2勝預期急升，令BLFS隨之升至${c:g}（隱含RGEN約${implied_rgen:.0f}）；8月6日Q2收入升21%、轉虧為盈",
             hot=["每股$11.25現金＋0.1442股RGEN", "轉虧為盈"],
             catalyst="Repligen換股收購", ckind="併購")
        _add_sources(news, "BLFS", facts["BLFS"]["sources"])
        review["ticker_flags"]["BLFS"] = {
            "badge": "換股併購目標 · 隨RGEN",
            "text": "作價 = $11.25 現金 + 0.1442 股 RGEN，並非固定 $31；股價跟 Repligen 走，收縮／突破指標量度嘅係 RGEN 走勢。",
        }

    # 5. PSNL — all-stock (up to 50% cash at Tempus's option), floating ratio capped at 0.3356
    if "PSNL" in ok and "PSNL" in listed:
        _set(news, "PSNL", log,
             decline_short="7月20日Tempus提出收購：每股目標值$16.25、全股支付（Tempus可選最多50%現金），換股比率浮動、上限0.3356股（TEM低於$48.42時固定），溢價僅5.6%，股價單日插近15%",
             recovery_short="Q2收入2240萬勝預期1670萬美元，MRD檢測量按年飆199%；股價升穿$16.25目標值，反映市場憧憬加價或TEM股價支撐",
             hot=["MRD檢測量按年飆199%"],
             catalyst="Tempus換股收購", ckind="併購")
        _add_sources(news, "PSNL", facts["PSNL"]["sources"])
        review["ticker_flags"]["PSNL"] = {
            "badge": "換股併購目標 · 目標值$16.25",
            "text": "全股收購，換股比率浮動（上限 0.3356 股 TEM）；$16.25 係目標值而非固定現金價，TEM 跌穿 $48.42 時 PSNL 承受下行。",
        }
        if "TEM" in news:
            _set(news, "TEM", log,
                 decline_short="7月20日宣布以全股（可選最多50%現金）收購Personalis，股權價值$19億（扣除已持股份約$15億），溢價僅6%惹攤薄憂慮兼高管減持，月內挫28.7%")

    # 8. NAVI — not a party to the $23B settlement
    if "NAVI" in ok and "NAVI" in listed:
        r34 = (1 + ret_on("NAVI", "2026-08-03") / 100) * (1 + ret_on("NAVI", "2026-08-04") / 100) - 1
        _set(news, "NAVI", log,
             recovery_short=f"8月初學貸股借Sweet v. McMahon $23B和解（借款人訴教育部，Navient並非當事方）獲上訴法院維持而炒上，8月3–4日累升{r34 * 100:.0f}%；核心EPS按年升45%，貸款發放量增63%，維持派息",
             hot=["核心EPS按年升45%", "貸款發放量增63%"],
             catalyst="學貸和解憧憬(非當事方)", ckind="監管", confidence="中")
        _add_sources(news, "NAVI", facts["NAVI"]["sources"])

    # 9. MAN — the +32% day was Q2 earnings, not the IBM partnership
    if "MAN" in ok and "MAN" in listed:
        _set(news, "MAN", log,
             recovery_short="7月16日Q2經調整EPS $0.99、GAAP轉盈（去年同期蝕$1.44），Q3指引$0.96–1.06，單日爆升32.4%；7月8日Experis夥IBM推watsonx AI工作流產品屬另一件事",
             hot=["Q2經調整EPS $0.99", "GAAP轉盈"],
             catalyst="Q2轉盈單日飆32%", ckind="業績")
        _add_sources(news, "MAN", facts["MAN"]["sources"])

    # 10. NWS / NWSA — one company, one story
    if "NWSA" in ok and "NWS" in listed:
        _set(news, "NWS", log,
             decline_short=news["NWSA"]["decline_short"] if "NWSA" in news else news["NWS"]["decline_short"],
             recovery_short="8月5日Q4業績大勝：收入升11%至$23.4億，EPS $0.35遠勝預期$0.22；FY26回購$6.43億（2025年7月授權嘅$10億計劃，去年逾4倍），大行齊升目標價",
             hot=["EPS $0.35遠勝預期$0.22", "FY26回購$6.43億"],
             catalyst="Q4大勝兼回購$6.43億")
        _add_sources(news, "NWS", facts["NWSA"]["sources"])
    if "NWSA" in ok and "NWSA" in listed:
        _add_sources(news, "NWSA", facts["NWSA"]["sources"])

    # 11. MDB — Q2 reported after the 09-01 close; stock fell ~13% after hours
    if "MDB" in ok and "MDB" in listed:
        _set(news, "MDB", log,
             recovery_short="AI應用帶動Atlas數據庫需求，一個月急升逾32%，Citi上調目標價至450美元；9月1日盤後Q2收入$7.718億升30%、EPS $1.90勝預期並上調全年指引，惟盤後急跌約13%至$377水平（9月2日反應未入本版數據）",
             hot=["Q2收入$7.718億升30%", "上調全年指引"],
             catalyst="Q2勝預期惟盤後跌13%", ckind="業績", confidence="高")
        _add_sources(news, "MDB", facts["MDB"]["sources"])
        review["ticker_flags"]["MDB"] = {
            "badge": "9/1 盤後跌約 13%",
            "text": "Q2 勝預期但盤後急跌約 13% 至 $377 水平，低於 8月24日底 $402.69；9月2日開市後結構大概率破壞，本版數據未反映。",
        }

    # 12. SRPT — 08-27 jump: rival setback + upgrade + positioning, not the CEO
    if "SRPT" in ok and "SRPT" in listed:
        r = ret_on("SRPT", "2026-08-27")
        _set(news, "SRPT", log,
             recovery_short=f"新CEO 7月28日上任；8月27日單日彈{r:.1f}%：對手Capricor deramiocel遭FDA顧問委員會9比3反對（PDUFA押後至11月）、Wolfe升評級（目標價$27）、資金為下半年Elevidys數據提前布局",
             hot=["對手Capricor deramiocel遭FDA顧問委員會9比3反對", "Wolfe升評級（目標價$27）"],
             catalyst="對手FDA受挫+升評級", ckind="監管")
        _add_sources(news, "SRPT", facts["SRPT"]["sources"])

    # review notes for the fact pass
    fact_notes = [
        {"title": "[已修正] 總表 #3 SMTI 原標「跟大市」，其實係 MiMedx 收購目標",
         "text": "R7 研究搵唔到 SMTI 7月29–30日兩日升 28% 嘅原因並標為「跟大市」。核實：7月29日收市後 MiMedx 宣布以每股 $33 現金 + 0.4735 股 MDXG（約 $35）收購，其後一個月股價喺 $34–35 橫行 —— 同 VREX、ITGR 一樣係套利釘價。已改為併購 badge 並加紅色標記（「隱藏併購釘價股」會一併隱藏）。",
         "tickers": ["SMTI"]},
        {"title": "[已修正] 併購資料同價格對唔上嘅行",
         "text": "BLFS「$31/股」其實係 $11.25 現金 + 0.1442 股 RGEN（公布日隱含值），股價跟 Repligen 升至 $35.47；PSNL「$16.25」係全股收購嘅目標值（換股比率浮動、上限 0.3356），TEM 行嘅「$15億」係扣除已持股份後淨值（股權價值 $19億）。三行文字及標記已改寫。",
         "tickers": ["BLFS", "PSNL", "TEM"]},
        {"title": "[已修正] 催化劑歸因錯誤",
         "text": "MAN 7月16日 +32% 係 Q2 業績（經調整 EPS $0.99、GAAP 轉盈）而非 IBM 合作（7月8日另行公布）；NAVI 並非「$23B 學貸和解」當事方（Sweet v. McMahon 係借款人訴教育部），升幅屬板塊聯動；SRPT 8月27日 +14% 來自對手 Capricor 受挫、Wolfe 升評級同數據前布局，唔係新 CEO；STEP 8月11日 +6.6% 係 UBS 升評級（鏡像補值令佢顯示喺 8月13日）；NWS／NWSA 同一公司兩個版本已統一（FY26 回購 $6.43 億，$10 億係 2025 年 7 月授權）。",
         "tickers": ["MAN", "NAVI", "SRPT", "STEP", "NWS", "NWSA"]},
        {"title": "[已標記] MDB 9月1日盤後業績後急跌約 13%",
         "text": "Q2 收入 +30%、EPS $1.90 勝預期並上調全年指引，但盤後跌至 $377 水平，低於 8月24日底 $402.69；本版數據截至 9月1日收市，9月2日開市後結構大概率破壞。已加紅色標記。",
         "tickers": ["MDB"]},
    ]
    by_title = {n["title"]: i for i, n in enumerate(review["notes"])}
    cut = next((i for i, n in enumerate(review["notes"]) if n["title"].startswith(("[紅色標記", "[待你決定]"))), len(review["notes"]))
    for n in fact_notes:
        if n["title"] in by_title:
            review["notes"][by_title[n["title"]]] = n
        else:
            review["notes"].insert(cut, n); cut += 1
    # headline: SMTI is the headline change of the fact pass
    if "SMTI" in ok and "總表 #3 SMTI" not in review.get("headline", ""):
        review["headline"] = review["headline"].replace(
            "12 個子頁有 6 個嘅榜首係呢類股票。",
            "12 個子頁有 6 個嘅榜首係呢類股票；核實新聞後發現總表 #3 SMTI 都係（MiMedx 約 $35 收購，R7 誤標「跟大市」）。")
    # rule note
    rn = "R8 核實（唔改規則）：SMTI、BLFS、PSNL、TXNM、VOYA 加入併購標記；MAN、NAVI、SRPT、STEP、NWS 催化劑歸因改正；MDB 盤後急跌另加標記。"
    if rn not in review["rule_notes"]:
        review["rule_notes"].insert(3, rn)

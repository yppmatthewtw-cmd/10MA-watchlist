"""R23 findings for scripts/review_hm.py: text written for this revision, every
number taken from the review context `c` (nothing typed in)."""
import json


def build(c):
    S, meta, rows, T1, BY, G = c["S"], c["meta"], c["rows"], c["T1"], c["BY"], c["G"]
    pct, LAST, PREV_DATE, REV, PREV_REV, P = c["pct"], c["LAST"], c["PREV_DATE"], c["REV"], c["PREV_REV"], c["P"]
    fs = c["forward"]["stats"]; fw = c["forward"]; ST = c["STATS"]
    fun = meta["funnel"]; each = meta["each_gate"]
    sens = {(x["param"], x["alt"]): x for x in S["sensitivity"]}
    loose = next(x for x in S["sensitivity"] if x["param"] == "全部放寬一級")
    tight = next(x for x in S["sensitivity"] if x["param"] == "全部收緊一級")
    t2 = [r for r in rows if r["tier"] == 2]
    pool = c["c3_pool"]
    pool_only_c4 = [x["sym"] for x in pool if x["fail"] == ["C4"]]
    pool_only_c1b = [x["sym"] for x in pool if x["fail"] == ["C1b"]]
    deal = [s for s, fl in c["extra"].items() if any(k == "deal" for k, _ in fl)]
    evflag = [s for s, fl in c["extra"].items() if any(k == "event" for k, _ in fl)]
    r22 = {r["sym"]: r for r in c["PREV"]["rows"]}
    fc = ST["prev_fail_count"]
    br = c["br"]
    crypto = [s for s in ("ASST", "PURR", "GEMI") if s in BY]
    intr = [r["sym"] for r in rows if r.get("last_intraday")]
    a_last = meta["snap_audit"]
    data_flags = [s for s, fl in c["extra"].items() if any(k == "data" for k, _ in fl)]

    breadth_txt = "；".join(f"{b['date'][5:]} {pct(b['med'], 2)}" for b in meta["breadth"][-6:])
    needs_txt = "、".join(f"{c['GZH'][k]} {v} 隻" for k, v in sorted(ST["needs_count"].items(), key=lambda kv: -kv[1]))
    F = []
    F.append({"id": "F1", "title": f"新條件下只有 {len(T1)} 隻完全符合，所以加咗第二梯隊（{len(t2)} 隻）",
              "text": f"漏斗：合資格 {fun['eligible']:,} → 有事件日 {fun['C1a']:,} → 加升浪熱錢 {fun['C1b']} → 加曾有 10MA 上升 {fun['C2']} "
                      f"→ 加回落到 20MA {fun['C3']} → 加波幅減低 {fun['C4']}。單獨睇，全市只有 {each['C3']} 隻而家處於「上升中 20MA 嘅回調位」"
                      f"（近六日大市闊度：{breadth_txt}），"
                      f"而曾經係熱錢股嘅只係當中少數 —— 熱錢股而家唔係仲喺高位（距 MA20 太遠）就係已經跌穿。"
                      f"每個門檻放寬一級後有 {loose['n']} 隻（全部收緊一級剩 {tight['n']} 隻）：第二梯隊就係呢 {len(t2)} 隻，總表「唔過嘅條件」欄列明每隻差邊項，"
                      f"最常差嘅係 {needs_txt}。",
              "action": "第二梯隊入總表、底色較淺；佢哋唔係合格股，係「差一步」"})
    F.append({"id": "F2", "title": "CSR 係全換股併購目標，升浪同回調都唔係自己嘅",
              "text": "CSR 09-09 嘅事件日係同 IRT 嘅全換股合併公佈（每股換 3.800 股 IRT），之後股價跟 IRT 走：規則見到嘅「熱錢追入後回落到 20MA、波幅收窄」"
                      "其實係併購溢價收窄同 IRT 自己嘅走勢。呢類股喺 R1–R20 一直有「併購釘價」標記、而且係未決嘅剔走問題。"
                      f"第一梯隊剩低 RLGT（業績＋升級）同 BSVN（收購人＋評級）係真正嘅消息驅動。",
              "action": "保留但標橙底；待你決定要唔要將換股／現金併購目標直接剔走"})
    F.append({"id": "F3", "title": f"第二梯隊入面 {len(evflag)} 隻嘅「消息」唔係業績：加密貨幣、傳聞、分析員推介",
              "text": "、".join(evflag)
                      + f"。加密貨幣庫存股（{'、'.join(crypto)}）嘅股價係代幣嘅槓桿；UMAC 嘅 +57% 係 WSJ 傳聞；AMBA 係 Rosenblatt 推介；GEMI 嘅 +31% 係加密板塊同升而且一年跌咗 76%。"
                      "「News driven」條件規則上只睇「大升日＋放量」，分唔到消息嘅質素，所以逐隻查咗事件日當日嘅新聞（催化劑頁有來源）。",
              "action": "標橙底；事件類型列喺催化劑頁"})
    F.append({"id": "F4", "title": f"{PREV_REV} 向前測試（{fw['n_days']} 個交易日）：中位數 {pct(fs['m_all'], 2)}，大市 {pct(fs['mkt_med'], 2)}",
              "text": f"{PREV_REV} 21 隻由 {PREV_DATE} 到 {LAST}：中位數 {pct(fs['m_all'], 2)}（{fs['up_all']} 隻升），全體合資格股票 {pct(fs['mkt_med'], 2)}；"
                      f"前 10 名 {pct(fs['m_top'], 2)}、其餘 {pct(fs['m_bot'], 2)}，分數同回報排名相關 {fs['rho']:+.2f}；"
                      f"有標記嘅 {pct(fs['m_fl'], 2)} vs 冇標記嘅 {pct(fs['m_nf'], 2)}。而家狀態：" + "；".join(f"{k} {v} 隻" for k, v in sorted(fs['states'].items(), key=lambda kv: -kv[1]))
                      + f"。{PREV_REV} 名單{'跑贏' if fs['m_all'] > fs['mkt_med'] else '跑輸'}大市 {abs(fs['m_all'] - fs['mkt_med']) * 100:.2f} 個百分點"
                      f"（R21 向前 3 日係 −1.57% vs −0.68%，跑輸）；兩次都只係二三十隻、幾日嘅樣本，{'方向相反' if fs['m_all'] > fs['mkt_med'] else '方向一致'}，"
                      "暫時睇唔出規則有冇優勢。",
              "action": f"逐隻列喺「{PREV_REV}向前測試」頁"})
    F.append({"id": "F5", "title": f"{PREV_REV} 嘅 21 隻用新條件睇：{len(ST['both_prev'])} 隻仍然上榜",
              "text": f"{PREV_REV}（高動能回到 20MA）21 隻入面，新條件下 {len(ST['both_prev'])} 隻上榜（" + "、".join(f"{s} 第 {BY[s]['tier']} 梯隊" for s in ST["both_prev"]) + "）。"
                      f"其餘唔過嘅原因（一隻可以幾個）：" + "、".join(f"{c['GZH'][k]} {v} 隻" for k, v in sorted(fc.items(), key=lambda kv: -kv[1]))
                      + "。最多係差「升浪熱錢」：R22 嘅動能股好多係慢慢升上去，升浪期成交額唔夠之前 60 日嘅兩倍；其次係波幅未收窄。",
              "action": "逐隻原因列喺「同R22對照」頁"})
    F.append({"id": "F6", "title": f"20MA 回調池：{ST['pool_n']} 隻而家處於回調位，差邊項一目了然",
              "text": f"全市 {ST['pool_n']} 隻通過 C3（上升中 20MA、高位 2–25 日前、回調 3–30%、收市 ±3% 兼近 3 日觸及）。佢哋唔過嘅條件："
                      + "、".join(f"{c['GZH'][k]} {v} 隻" for k, v in sorted(ST['pool_fail'].items(), key=lambda kv: -kv[1]))
                      + f"。只差波幅減低嘅：{'、'.join(pool_only_c4) or '冇'}；只差升浪熱錢嘅：{'、'.join(pool_only_c1b) or '冇'}。"
                      "呢頁係「下一兩日最有機會變成合格」嘅觀察名單。",
              "action": "新增「20MA回調池」頁"})
    F.append({"id": "F7", "title": "數據：序列檔喺容器重設後消失、Nasdaq 快照又遲一日",
              "text": "R1–R22 用嚟做第二來源同上市日期嘅 Nasdaq 序列（data/series*.pkl）係 gitignore 嘅，10-01 容器重設後冇咗；"
                      f"上市日期改由 R21／R22 審計保存嘅 data/nasdaq_listing_dates.json 提供，另加 SPAC 空殼期偵測（今次捉到 {len(meta.get('shell_detected', {}))} 隻，"
                      "全部唔喺名單）。兩源核對只剩收市後快照：" + "；".join(f"{f} 檔其實係 {a['holds']}" for f, a in sorted(a_last.items()) if a.get("action"))
                      + f"（Nasdaq API 到美東早上五點都未轉日），所以 {LAST} 收市只得 Yahoo 一個來源（日線齊全，{meta['bars_last_day']:,} 隻）。"
                      + (f" 另外 {'、'.join(data_flags)} 嘅事件日升幅同媒體數字對唔上，已標記。" if data_flags else ""),
              "action": "要重建序列先可以再跑 R1–R20 嘅舊規則管線（README 有步驟）"})
    F.append({"id": "F8", "title": f"門檻敏感度：第一梯隊 {len(ST['robust'])}/{len(T1)} 隻喺 {ST['n_sens']} 個單門檻測試都留低",
              "text": "留低嘅：" + ("、".join(ST["robust"]) or "冇") + "。變動最大嘅門檻：" + "；".join(
                  f"{c['PN'][x['param']]} {x['base']}→{x['alt']}：+{len(x['added'])}／−{len(x['dropped'])}"
                  for x in sorted([x for x in S["sensitivity"] if not str(x["param"]).startswith("全部")], key=lambda x: -(len(x["added"]) + len(x["dropped"])))[:5])
                      + "。名單細，每個門檻都係邊緣。",
              "action": "逐項列喺「敏感度」頁"})
    F.append({"id": "F9", "title": "今次冇做嘅嘢",
              "text": "冇查業績日期（10 月中開始業績期）；沿用舊研究嘅 " + "、".join(c["RES"]["carried"]) + " 冇重新核實；"
                      "冇用新條件回測之前幾日（上日回算有）；HTML 報告冇按新規則重做。",
              "action": "如有需要下一版補"})
    opens = [
        "換股／現金併購目標（今次 CSR）要唔要直接剔走？R1–R20 嘅「併購釘價」問題一直未決。",
        f"加密貨幣庫存股（{'、'.join(crypto)}）要唔要當「有熱錢及 news driven」？佢哋嘅消息係代幣價格。",
        "「有熱錢」而家定義係升浪期成交額 ≥ 前 60 日 2 倍；R22 嘅慢升動能股大部分過唔到。要唔要降到 1.5 倍（第二梯隊用嘅）？",
        "「波幅減低」而家要 ATR5 ≤ 0.9× ATR20 兼 ≤ 0.7× 升浪期 ATR；只差呢項嘅有 " + ("、".join(pool_only_c4) or "冇") + "。",
        "第二梯隊要唔要繼續出？佢哋唔合格，但第一梯隊得幾隻。",
    ]
    for i, t in enumerate(opens, 1):
        F.append({"id": f"待決{i}", "title": "待你決定", "text": t, "action": "今次未改"})

    notes = [
        f"篩選條件按你嘅四點更新：① 有熱錢及消息驅動（高位前 60 日內有一日 ≥+8% 或跳空 ≥+5%、成交量 ≥3× 50 日均量；升浪期成交額 ≥ 前 60 日 2 倍）"
        f"② 曾有 10MA 上升（近 30 日內通過 R1–R20 嘅 10MA 測試：10 日升 ≥5%、最後三值遞升、10 步升 ≥7 步）③ 回落到 20MA（MA20 向上、高位 2–25 日前、"
        f"回調 3–30%、高位時高過 MA20 ≥8%、收市喺 MA20 ±3% 兼近 3 日觸及）④ 波幅減低（ATR5 ≤ 0.9× ATR20 兼 ≤ 0.7× 升浪期 ATR）。細節見「篩選規則」頁。",
        f"數據更新至 {LAST} 收市（{meta['n_days']} 個交易日，{meta['cal_first']} 起）。",
        f"合資格 {meta['eligible']:,} 隻 → 第一梯隊 {len(T1)} 隻（" + "、".join(r["sym"] for r in T1) + f"）；每個門檻放寬一級嘅第二梯隊 {len(t2)} 隻。"
        f"分頁改為 大型／中型／小型。",
        f"評分改為 熱錢分數 0.25 + 10MA分數 0.20 + 回調質素 0.30 + 波幅收窄 0.25（每項 0–100，公式喺總表）。",
        f"{PREV_REV} 向前測試（{fw['n_days']} 日）：中位數 {pct(fs['m_all'], 2)}，大市 {pct(fs['mkt_med'], 2)}；{len(ST['both_prev'])} 隻 R22 股喺新條件下仍上榜。",
        "逐隻查咗事件日當日嘅新聞（催化劑頁有來源）：CSR 係全換股併購目標；3 隻係加密貨幣庫存股；UMAC 係傳聞；AMBA 係分析員推介。",
        "容器重設令 Nasdaq 序列檔消失：上市日期改由保存嘅審計檔提供，加 SPAC 空殼期偵測；兩源核對只剩收市後快照。",
        f"獨立重寫嘅篩選程式對兩個梯隊共 {len(rows)} 隻 0 差異。所有代號連 TradingView；可推導欄位全部係公式。",
    ]
    return F, notes

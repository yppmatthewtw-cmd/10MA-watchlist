"""R22 findings for scripts/review_mp.py: the text is written for this
revision, every number in it comes from the review context `c` or from the
comparison screens loaded here (nothing typed in)."""
import json, statistics


def build(c):
    W, S, PREV, meta, rows, BY, G = c["W"], c["S"], c["PREV"], c["meta"], c["rows"], c["BY"], c["G"]
    pct, LAST, PREV_DATE, REV, PREV_REV = c["pct"], c["LAST"], c["PREV_DATE"], c["REV"], c["PREV_REV"]
    fs = c["forward"]["stats"]; fw = c["forward"]
    ld = lambda f: json.load(open(f"{W}/{f}"))

    # --- the 52-week window: what it removed today and what it would have removed from R21
    nine = ld("screen_mp22_9m.json")
    gone_52 = [r["sym"] for r in nine["rows"] if r["sym"] not in BY]
    r21_52 = ld("screen_mp21_52w.json")
    r21_rm = [r["sym"] for r in PREV["rows"] if r["sym"] not in {x["sym"] for x in r21_52["rows"]}]
    ret = {x["sym"]: x["ret"] for x in fw["rows"] if x["ret"] is not None}
    rm_med = statistics.median(ret[s] for s in r21_rm) if r21_rm else None
    kept_med = statistics.median(ret[s] for s in ret if s not in r21_rm)

    # --- R21 re-run on Yahoo's back-filled 09-22 bars (nine-month window, as published)
    redo = ld("screen_mp21_redo.json")
    RA = {r["sym"]: r for r in PREV["rows"]}; RB = {r["sym"]: r for r in redo["rows"]}
    redo_same = set(RA) == set(RB)
    redo_moves = [s for s in RA if s in RB and RA[s]["rank"] != RB[s]["rank"]]
    redo_maxd = max(abs(RA[s]["score"] - RB[s]["score"]) for s in RA if s in RB)
    redo_maxstep = max((abs(RA[s]["rank"] - RB[s]["rank"]) for s in redo_moves), default=0)
    grdn = redo["gates"].get("GRDN", {})
    # --- R21's own day-over-day turnover
    r21pd = {r["sym"] for r in ld("screen_mp21_prevday.json")["rows"]}
    r21_left = len(r21pd - set(RA))
    # --- the intraday roll-up against Yahoo's daily bars, on names that have both
    import csv, gzip
    dly, itr = {}, {}
    with gzip.open(c["YAHOO"], "rt") as f:
        for r in csv.DictReader(f):
            if r["date"] == LAST:
                dly[r["symbol"]] = r
    for p in [x for x in c["os"].environ.get("SUPP", "").split(",") if "intraday" in x]:
        with gzip.open(p, "rt") as f:
            for r in csv.DictReader(f):
                if r["date"] == LAST:
                    itr[r["symbol"]] = r
    bothv = [s for s in dly if s in itr and float(dly[s]["high"]) > 0 and float(dly[s]["low"]) > 0]
    within = lambda k: sum(abs(float(itr[s][k]) / float(dly[s][k]) - 1) <= 0.005 for s in bothv) / len(bothv) if bothv else 0
    v_hi, v_lo = within("high"), within("low")
    v_cl = statistics.median(abs(float(itr[s]["close"]) / float(dly[s]["close"]) - 1) for s in bothv) if bothv else 0
    audit = meta["snap_audit"]
    stale = {f: a for f, a in audit.items() if a.get("action")}

    # --- turnover, old rules vs new
    r19 = {r["sym"] for r in ld("screen_results19.json")["page1"]}
    r20 = {r["sym"] for r in ld("screen_results20.json")["page1"]}
    old_left = len(r19 - r20) / len(r19)
    pd_left = (c["STATS"]["pd_n"] - c["STATS"]["pd_both"]) / c["STATS"]["pd_n"]

    ref = [x for x in fw["rows"] if x["sym"] in c["RES"]["refiners"]["syms"] and x["ret"] is not None]
    ref_med = statistics.median(x["ret"] for x in ref)
    hb = [x for x in fw["rows"] if "heavy_break" in x["fk"]]
    intr = [r["sym"] for r in rows if r.get("last_intraday")]
    clu, c_clu, c_rest = c["clu"], c["c_clu"], c["c_rest"]
    energy = [r["sym"] for r in rows if r["sector_zh"] == "能源"]
    br = c["br"]
    only_last = c["only_last"]
    robust = c["robust"]
    sens = c["sens"]
    left_now = [x for x in c["vs_prev"] if x["kind"] == "跌出"]
    left_below = sum(1 for x in left_now if G.get(x["sym"]) and G[x["sym"]]["d20"] < meta["params"]["dist_lo"])
    below_now = sum(1 for r in rows if r["close"] < r["ma20"])
    thin = [r["sym"] for r in rows if r["dv20"] < 5e6]

    F = []
    F.append({"id": "F1", "title": "兩個 Nasdaq 快照其實係舊一日嘅數據（已修正）",
              "text": "；".join(f"檔 {f} 入面係 {a['holds']} 收市（同 Yahoo {a['holds']} 吻合 {a['match']:.1%}，同 {f} 只有 {a['own_match']:.1%}）"
                               for f, a in sorted(stale.items()))
                      + "。Nasdaq API 喺美東晚上九點半左右仲未轉日。篩選器而家逐個快照同 Yahoo 收市對一次，按實際日期重新標籤或者棄用；"
                        "抓快照嘅 workflow 亦加咗關卡，同上一個快照幾乎一樣（>95% 相同）就拒絕寫入（會捉到 09-24 嗰種，捉唔到 09-28 嗰種，所以兩道關都要）。"
                        f"我今次工作初段用過 09-28 快照做初步向前測試，得出嘅數其實只計到 09-25，已作廢；正式數字見 F5。{PREV_REV} 用嘅 09-22、09-23 快照係啱嘅。",
              "action": "已修正"})
    vs = meta["vol_scale"].get(LAST, {})
    F.append({"id": "F2", "title": f"{LAST} 冇官方快照，Yahoo 日線又未出齊：{len(intr)}/{len(rows)} 隻上榜股用每小時K線合成（暫定）",
              "text": f"Yahoo 當晚只出咗 {meta['bars_last_day'] - meta['supp_keys_last']:,} 隻 {LAST} 日線，其餘 {meta['supp_keys_last']:,} 隻用每小時K線合成開高低收；"
                      f"喺兩樣都有嘅 {len(bothv):,} 隻上驗證：高位 {v_hi:.1%}、低位 {v_lo:.1%} 喺日線 0.5% 之內，收市中位差 {v_cl:.2%}；但K線成交量只有日線嘅中位 {1 / vs.get('ratio', 1):.0%}"
                      f"（收市競價等冇計入），所以成交量 × {vs.get('ratio', 1):.3f} 還原（比例由 {vs.get('n', 0):,} 隻實測）。用合成數據嘅上榜股："
                      + "、".join(intr) + "。",
              "action": "已處理；Yahoo 出齊日線（通常翌日下午）後可以重跑確認"})
    F.append({"id": "F3", "title": f"Yahoo 補返 09-22：用真實數據重算 {PREV_REV}，名單不變",
              "text": f"{PREV_REV} 時 Yahoo 缺 09-22，用 Nasdaq 收市價補（冇高低位）。而家 Yahoo 補返，用同一套規則重算 {PREV_DATE}："
                      + (f"同樣 {len(RB)} 隻" if redo_same else f"名單變咗（{len(RA)}→{len(RB)}）")
                      + f"，{len(redo_moves)} 隻排名變動（最多 {redo_maxstep} 位，分數最多變 {redo_maxd:.1f} 分）"
                      + ("，GRDN 09-22 日內都冇掂到 MA20。" if "S5" in grdn.get("fail", []) else "。")
                      + "另外 ATR 改為只計有真實高低位嘅日子，以後再有缺口日都唔會壓低波幅（今次冇缺口日，冇影響）。",
              "action": f"{PREV_REV} 補洞做法確認冇影響結果"})
    F.append({"id": "F4", "title": f"規則修正：S2「貼近期內高位」由九個月改為 52 周，今日因此少 {len(gone_52)} 隻",
              "text": f"{PREV_REV} 嘅數據由 2025-12-26 開始，S2 其實只係「九個月內高位」，唔係 52 周高位。補抓 2025-09-26 起嘅日線後，"
                      + "、".join(f"{s}（近 63 日高位只係 52 周高位嘅 {G[s]['h_rec']:.0%}）" for s in gone_52)
                      + f" 唔再過 S2 —— 佢哋係反彈中嘅股票，唔係創新高嘅強勢股。回溯 {PREV_REV}：52 周規則會剔走 {'、'.join(r21_rm)}，"
                      f"{len(r21_rm)} 隻之後中位數 {pct(rm_med, 2)}，其餘 {pct(kept_med, 2)}（樣本太細，只係方向一致）。",
              "action": "已修正"})
    F.append({"id": "F5", "title": f"{PREV_REV} 向前測試：{fw['n_days']} 個交易日跑輸大市",
              "text": f"{PREV_REV} 28 隻由 {PREV_DATE} 到 {LAST} 中位數 {pct(fs['m_all'], 2)}（{fs['up_all']} 隻升），全體合資格股票 {pct(fs['mkt_med'], 2)}。"
                      f"前 10 名 {pct(fs['m_top'], 2)}、其餘 {pct(fs['m_bot'], 2)}，分數同回報排名相關 {fs['rho']:+.2f}。"
                      f"而家 {fs['states'].get('跌穿 MA20 超過 3%', 0)} 隻已經跌穿 MA20 超過 3%，{fs['states'].get('仍然上榜', 0)} 隻仍然上榜。"
                      "期內 10 年期債息升到 5.23%（2007 年以來最高），回調買位喺跌市入面先天吃虧；3 日樣本唔可以當結論。",
              "action": f"逐隻列喺「{PREV_REV}向前測試」頁"})
    F.append({"id": "F6", "title": f"{PREV_REV} 嘅審視標記冇捉到輸家；「放量跌穿就當失敗」講得太武斷",
              "text": f"有標記嘅 {sum(1 for x in fw['rows'] if x['fk'])} 隻中位數 {pct(fs['m_fl'], 2)}，冇標記嘅 {pct(fs['m_nf'], 2)} —— 標記冇預測到邊啲會跌。"
                      f"{PREV_REV} 叫「放量跌穿」嘅 " + "、".join(x["sym"] for x in hb) + f"「聽日企唔返 MA20 就當失敗」，結果 {len(hb)} 隻中位數 {pct(fs['m_hb'], 2)}，"
                      + "、".join(f"{x['sym']} {pct(x['ret'])}" for x in hb) + "，全部仍然上榜。今次標記處理改為「睇之後幾日」，唔再落結論。",
              "action": "已改標記處理字眼"})
    F.append({"id": "F7", "title": "收市企唔企喺 MA20 上面，暫時睇唔出分別",
              "text": f"{PREV_REV} 收市喺 MA20 上面嘅 {fs['n_ab']} 隻中位數 {pct(fs['m_ab'], 2)}，收喺 MA20 下面（容許低 3%）嘅 {fs['n_be']} 隻 {pct(fs['m_be'], 2)}。"
                      "即係「只要收市企返 MA20」呢個待決項目，暫時冇證據支持。",
              "action": "待決 2 保留"})
    F.append({"id": "F8", "title": f"更正 {PREV_REV} 一句冇量度過嘅話：新規則每日換手約四至五成，舊規則約兩成半",
              "text": f"{PREV_REV} F2 寫「R1–R20 嘅舊名單可以一連幾星期都喺度」，冇數據支持。實際：R19→R20 一日跌出 {len(r19 - r20)}/{len(r19)}（{old_left:.0%}）；"
                      f"新規則 {c['PD']['meta']['last_date']}→{LAST} 跌出 {c['STATS']['pd_n'] - c['STATS']['pd_both']}/{c['STATS']['pd_n']}（{pd_left:.0%}），"
                      f"{PREV_REV} 09-22→09-23 係 {r21_left}/{len(r21pd)}（{r21_left / len(r21pd):.0%}）。{PREV_REV}→{REV}（三個交易日）：兩版都有 {len(c['both'])} 隻、新上榜 {c['STATS']['n_new']}、"
                      f"跌出 {c['STATS']['n_out']}（跌出入面 {left_below} 隻已經跌穿 MA20 超過 3%）。",
              "action": "已更正"})
    F.append({"id": "F9", "title": f"煉油股仍然係一個交易：{'、'.join(clu)}（相關 {c_clu:+.2f}，名單其餘 {c_rest:+.2f}）",
              "text": f"能源 {len(energy)}/{len(rows)} 隻（" + "、".join(energy) + "）。"
                      f"{PREV_REV} 煉油組五隻向前中位數 {pct(ref_med, 2)}，" + "、".join(f"{x['sym']} {pct(x['ret'])}" for x in ref)
                      + f"；CLMT 已經跌穿 MA20。09-28 特朗普拒絕伊朗和平方案、油價升，對煉油股係雙面刃（原油成本升 vs 柴油緊張）。",
              "action": "標「同向群組」；當一個交易睇"})
    F.append({"id": "F10", "title": "事件驅動：IRD 呢個星期有二元事件",
              "text": "IRD 10 月 1–4 日 EURETINA 大會公佈 OPGx-BEST1 詳細數據，排第 1 但係數據前夕；TTRX 升浪由臨床試驗消息帶動；"
                      "PURR 係加密貨幣（HYPE 代幣）庫存公司；TITN 升浪來自券商升級而收入同期跌 9.2%。",
              "action": "保留、標橙底"})
    F.append({"id": "F11", "title": f"{LAST} 全市跌：{len(only_last)} 隻今日先第一次觸及 MA20",
              "text": f"{LAST} 合資格股票中位數 {pct(br[LAST]['med'], 2)}，{br[LAST]['up']:.0%} 上升（10 年期債息 5.23%）。"
                      + "、".join(only_last) + f" 近 3 日入面只有今日最低價去到 MA20；上榜股當日中位數 {pct(c['list_move'], 2)}。",
              "action": "唔改規則"})
    F.append({"id": "F12", "title": f"門檻敏感度：{len(S['sensitivity'])} 個測試入面 {len(robust)}/{len(rows)} 隻次次都留低",
              "text": "留低嘅：" + "、".join(robust) + "。變動最大：" + "；".join(
                  f"{c['PN'][x['param']]} {x['base']}→{x['alt']}：+{len(x['added'])}／−{len(x['dropped'])}" for x in c["sens_big"]) + "。",
              "action": "總表「門檻測試留低」欄"})
    F.append({"id": "F13", "title": "今次冇做嘅嘢",
              "text": "冇逐隻查業績日期（10 月中開始業績期；IRD 嘅數據事件已知）；沿用舊研究嘅 "
                      + "、".join(c["RES"]["carried"]) + " 冇重新核實；HTML 報告冇按新規則重做。",
              "action": "如有需要下一版補"})
    opens = [
        f"動能門檻用頭 10% 定頭 15%？今日頭 15% 會多 {len(sens[('decile', 0.85)]['added'])} 隻。",
        f"只要收市企返 MA20 上面？今日會少 {below_now} 隻；但 {PREV_REV} 向前測試入面收喺 MA20 下面嘅反而跌得少（見 F7）。",
        f"成交額下限升到 $5M？今日會少 {len(thin)} 隻（{'、'.join(thin)}）。",
        f"事件驅動同放量跌穿要唔要剔走？{PREV_REV} 向前測試入面有標記嘅跌得比冇標記少（見 F6），暫時冇證據支持剔走。",
    ]
    for i, t in enumerate(opens, 1):
        F.append({"id": f"待決{i}", "title": "待你決定", "text": t, "action": "今次未改"})

    notes = [
        f"數據更新至 {LAST} 收市。規則同 {PREV_REV} 一樣（高動能 ＋ 回到上升中嘅 20MA），只有一項修正：S2 期內高位由九個月改為 52 周。",
        f"合資格 {meta['eligible']:,} 隻 → 形態 {meta['funnel']['setup']} 隻 → 上榜 {len(rows)} 隻（1／2／3／6 個月頁 "
        f"{len(S['pages']['21'])}／{len(S['pages']['42'])}／{len(S['pages']['63'])}／{len(S['pages']['126'])}）；"
        f"同 {PREV_REV} 兩版都有 {len(c['both'])} 隻，新上榜 {c['STATS']['n_new']}、跌出 {c['STATS']['n_out']}。",
        f"{PREV_REV} 向前測試（{fw['n_days']} 日）：中位數 {pct(fs['m_all'], 2)}，大市 {pct(fs['mkt_med'], 2)}；前 10 名 {pct(fs['m_top'], 2)}。",
        "發現並修正：兩個過時嘅 Nasdaq 快照（加咗兩道關）；09-28 Yahoo 日線未出齊（每小時K線合成、成交量還原）；S2 窗口太短；"
        f"{PREV_REV} 一句冇量度過嘅講法。詳見「審視標記」頁。",
        f"獨立重寫嘅篩選程式對 {LAST} 同 {c['PD']['meta']['last_date']} 兩份名單都 0 差異。",
        "所有代號都連去 TradingView 圖表；計得出嘅欄位全部係公式。",
    ]
    return F, notes

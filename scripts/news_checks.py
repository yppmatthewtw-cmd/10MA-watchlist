#!/usr/bin/env python3
"""Consistency checks for the news layer (news*.json) against the price series.

The R7 content review found that nothing gated the research text: after-hours
percentages presented as daily moves, catalysts whose event day closed down,
sources that were titles rather than URLs, "跟大市" rows with a +13% day nobody
explained, and 併購 badges quoting a price the stock already trades above.
merge_news8.py calls run_checks() and prints the findings as warnings (the
merge still completes); standalone use:

    WORK_DIR=./data python3 scripts/news_checks.py news8.json screen_results8.json
"""
import json, os, pickle, re, sys

# a *stock* move phrase: "單日飆18%", "翌日收升21.6%", "股價插5.3%", "盤後急升逾10%"
MOVE = re.compile(r"(\d{1,2})月(\d{1,2})日[^。；;，]{0,30}?"
                  r"(?:股價|單日|當日|翌日|盤後|盤前|收市|收)?(?:急|暴|狂)?"
                  r"(升|飆|彈|抽|漲|瀉|挫|跌|插)(?:逾|近|約|超)?(\d+(?:\.\d+)?)%")
OTHER = re.compile(r"原油|油價|以太幣|比特幣|銅價|金價|指數|標普|納指|Progressive|同業|板塊|對手|競爭"
                   r"|年內|今年|年初至今|一年|月內|一個月|一週|週內|30日|三日|兩日|以來")
METRIC = re.compile(r"收入|EPS|盈|利潤|指引|ARR|ASV|銷|按年|按季|同店|EBITDA|毛利|現金流|流量|訂閱|出貨|存款|貸款|價至|美元|億|萬")
PRICE_IN_BADGE = re.compile(r"\$(\d+(?:\.\d+)?)(?![\d\.]*(?:億|萬|B|M|bn|m))")


def run_checks(news, need, series_path, screen=None):
    """Return a list of warning strings. `need` = listed tickers."""
    warns = []
    if not os.path.exists(series_path):
        return [f"series not found ({series_path}); price checks skipped"]
    d = pickle.load(open(series_path, "rb")); CAL, SER = d["cal"], d["series"]
    IDX = {c: i for i, c in enumerate(CAL)}
    year = CAL[-1][:4]
    hl = {r["sym"]: r.get("hl") or [] for r in (screen or {}).get("page1", [])}
    copied = set((screen or {}).get("meta", {}).get("copied_days") or [])   # mirror had no snapshot; close copied

    def day_index(m, dd):
        key = f"{year}-{int(m):02d}-{int(dd):02d}"
        if key in IDX: return IDX[key]
        return next((i for i, c in enumerate(CAL) if c > key), None)

    def ret(sym, i):
        fi, cs, vs, ff = SER[sym]; j = i - fi
        return (cs[j] / cs[j - 1] - 1) * 100 if 0 < j < len(cs) else None

    for sym in need:
        e = news.get(sym)
        if not e or sym not in SER: continue
        fi, cs, vs, ff = SER[sym]
        # (a) dated stock-move percentages must match the series on that day or the next two
        for fld in ("decline_short", "recovery_short"):
            for m in MOVE.finditer(e[fld]):
                mo, dd, verb, pct = m.groups(); pct = float(pct)
                clause = m.group(0); head = clause.rsplit(verb, 1)[0]
                if METRIC.search(head) or "累" in head or OTHER.search(head):
                    continue  # "收入升11%", "累跌39%", "原油飆5%" are not this stock's daily move
                i = day_index(mo, dd)
                if i is None: continue
                sign = -1 if verb in "瀉挫跌插" else 1
                days = [k for k in range(i, min(i + 6, len(CAL))) if CAL[k] not in copied][:3]
                if any(CAL[k] in copied for k in range(i, min(i + 3, len(CAL)))):
                    days = [k for k in range(i, min(i + 6, len(CAL)))]   # the move shows on the first real day after the copies
                cands = [ret(sym, k) for k in days]
                ok = any(r is not None and r * sign > 0 and abs(abs(r) - pct) <= max(0.4 * pct, 1.5) for r in cands)
                if not ok:
                    got = ", ".join(f"{CAL[k][5:]} {ret(sym, k):+.1f}%" for k in days if ret(sym, k) is not None)
                    warns.append(f"{sym}: «{clause}» not in series (close-to-close: {got})")
        # (b) sources must be URLs; ≥1 non-quote article for 高
        src = e.get("sources") or []
        bad = [s for s in src if not re.match(r"https?://", s)]
        if bad: warns.append(f"{sym}: {len(bad)} source(s) are titles, not URLs")
        if e.get("confidence") == "高" and not any(re.match(r"https?://", s) and not re.search(r"stockanalysis\.com|cnbc\.com/quotes|macrotrends|investing\.com/equities", s) for s in src):
            warns.append(f"{sym}: 信心高 without an article URL")
        # (c) 跟大市 rows with an unexplained ≥8% day since the first bottom
        if not (e.get("catalyst") or "").strip() and hl.get(sym):
            b0 = IDX.get(hl[sym][0][0])
            if b0 is not None:
                big = [(CAL[k][5:], ret(sym, k)) for k in range(b0 + 1, len(CAL)) if (ret(sym, k) or 0) >= 8]
                if big: warns.append(f"{sym}: 跟大市 but {len(big)} day(s) ≥ +8% since first bottom: " + ", ".join(f"{d_} {r:+.1f}%" for d_, r in big))
        # (d) 併購 badge price versus close
        if e.get("ckind") == "併購":
            pm = PRICE_IN_BADGE.search(e.get("catalyst") or "")
            if pm:
                offer = float(pm.group(1)); last = cs[-1]
                if last > offer * 1.05:
                    warns.append(f"{sym}: 併購 badge quotes ${offer:g} but close {last:g} is {(last / offer - 1) * 100:+.1f}% above it (stock deal or stale price?)")
        # (e) hot spans must sit in the recovery text and name an event, not just the move
        for h in e.get("hot") or []:
            if h not in e["recovery_short"]: warns.append(f"{sym}: hot span not in text «{h}»")
    return warns


if __name__ == "__main__":
    SCRATCH = os.environ.get("WORK_DIR", "./data")
    news_file = sys.argv[1] if len(sys.argv) > 1 else "news8.json"
    screen_file = sys.argv[2] if len(sys.argv) > 2 else "screen_results8.json"
    news = json.load(open(f"{SCRATCH}/{news_file}"))
    scr = json.load(open(f"{SCRATCH}/{screen_file}"))
    need = [r["sym"] for r in scr["page1"]]
    ws = run_checks(news, need, f"{SCRATCH}/{os.environ.get('SERIES', 'series4.pkl')}", scr)
    print(f"{len(ws)} warning(s) over {len(need)} listed tickers")
    for w in ws: print("  -", w)

#!/usr/bin/env python3
"""Build the 10MA R8 report (dark-only) with every change since the previous
revision highlighted in red.

Inputs (env): SCREEN_JSON / NEWS_JSON (current), PREV_SCREEN / PREV_NEWS
(previous revision to diff against), PREV_REV (label), REV (this revision),
optional REVIEW_JSON (data/review8.json — findings from the critical review:
headline, notes, rule_notes, ticker_flags).

What turns red, and why only that:
- a ticker new to a page (row badge), one that dropped off (strip above the table),
  and rank moves (arrow next to #) — membership is what a reader compares first;
- any cell whose DISPLAYED content differs from the previous revision — text,
  catalyst badge, evidence states, bottoms, chips — flagged by class, so unchanged
  cells stay quiet and the red is meaningful;
- numeric scores show a small red delta rather than turning red themselves;
- review-driven notes and per-ticker flags (e.g. deal-pinned) render red;
- market-card sentences/factors that were not in the previous revision.
A nav toggle hides rows with no change at all.
"""
import re, datetime, html, json, os

SCRATCH = os.environ.get("WORK_DIR", "./data")
O = json.load(open(f"{SCRATCH}/{os.environ.get('SCREEN_JSON', 'screen_results8.json')}"))
N = json.load(open(f"{SCRATCH}/{os.environ.get('NEWS_JSON', 'news9.json')}"))
PREV = json.load(open(f"{SCRATCH}/{os.environ['PREV_SCREEN']}")) if os.environ.get("PREV_SCREEN") else None
PN = json.load(open(f"{SCRATCH}/{os.environ['PREV_NEWS']}")) if os.environ.get("PREV_NEWS") else {}
PREV_REV = os.environ.get("PREV_REV", "上一版")
REV = os.environ.get("REV", "R9.00")
_rv = f"{SCRATCH}/{os.environ.get('REVIEW_JSON', 'review9.json')}"
REVIEW = json.load(open(_rv)) if os.path.exists(_rv) else {}
MKT = json.load(open(f"{SCRATCH}/market.json")) if os.path.exists(f"{SCRATCH}/market.json") else None
PMKT = json.load(open(f"{SCRATCH}/{os.environ['PREV_MARKET']}")) if os.environ.get("PREV_MARKET") else None
M = O["meta"]
RNAME = REV.split(".")[0]

now_hkt = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=8)
STAMP = now_hkt.strftime("%m.%d_%H%M")
BUILD_TS = now_hkt.strftime("%Y-%m-%d %H:%M HKT")
MODEL_TAG = os.environ.get("MODEL_TAG", "claudeopus5xhigh")
OUTNAME = f"10MA_uptrend_watchlistGit_{REV}_{MODEL_TAG}_{STAMP}.html"

TF = [("2", "1星期", "5MA · 5個交易日"), ("3", "2星期", "10MA · 10個交易日"),
      ("4", "1個月", "10MA · 21個交易日"), ("5", "2個月", "10MA · 42個交易日")]
CAPS = [("a", "大型股", "Big cap ≥$10B"), ("b", "中型股", "Mid cap $2–10B"),
        ("c", "小型股", "Small cap &lt;$2B")]
CAP_SHORT = {"a": "大型", "b": "中型", "c": "小型", "x": "未分類"}
SUBS = [f"{t}{c}" for t, _, _ in TF for c, _, _ in CAPS]

def esc(s): return html.escape(str(s), quote=True)

# ---------------- previous-revision index ----------------
PREV_PAGE = {}     # pid -> {sym: (rank, row)}
PREV_P1 = {}
if PREV:
    for pid, pg in PREV["pages"].items():
        PREV_PAGE[pid] = {r["sym"]: (i, r) for i, r in enumerate(pg["rows"], 1)}
    PREV_P1 = {r["sym"]: (i, r) for i, r in enumerate(PREV["page1"], 1)}

def prev_of(pid, sym):
    src = PREV_P1 if pid == "1" else PREV_PAGE.get(pid, {})
    return src.get(sym, (None, None))

def news_prev(sym): return PN.get(sym) or {}
def news_cur(sym): return N.get(sym) or {}

def chg_cls(changed, base=""):
    return f'{base} chg'.strip() if changed else base

# ---------------- cells ----------------
def spark_svg(sp):
    cs = sp["closes"]; ma = sp["ma"]; bots = dict(sp["bots"])
    W, H, P = 150, 40, 3
    lo = min(cs); hi = max(cs)
    vals = [v for v in ma if v is not None]
    if vals: lo = min(lo, min(vals)); hi = max(hi, max(vals))
    rng = (hi - lo) or 1.0
    def xy(i, v):
        x = P + i * (W - 2 * P) / (len(cs) - 1)
        y = H - P - (v - lo) * (H - 2 * P) / rng
        return f"{x:.1f},{y:.1f}"
    pl_c = " ".join(xy(i, v) for i, v in enumerate(cs))
    seg, segs = [], []
    for i, v in enumerate(ma):
        if v is None:
            if seg: segs.append(seg); seg = []
        else:
            seg.append(xy(i, v))
    if seg: segs.append(seg)
    ma_polys = "".join(f'<polyline points="{" ".join(s)}" fill="none" stroke="var(--seq)" stroke-width="1.3" opacity=".9"/>'
                       for s in segs if len(s) > 1)
    dots = "".join('<circle cx="{}" cy="{}" r="2.4" fill="var(--good)"/>'.format(*xy(i, v).split(","))
                   for i, v in bots.items())
    return (f'<svg viewBox="0 0 {W} {H}" width="{W}" height="{H}" aria-label="60日走勢">'
            f'<polyline points="{pl_c}" fill="none" stroke="var(--ink2)" stroke-width="1"/>'
            f'{ma_polys}{dots}</svg>')

def delta_tag(cur, prev, fmt="{:+.1f}", eps=0.05):
    if prev is None or abs(cur - prev) < eps: return ""
    return f' <span class="chg dlt">{fmt.format(cur - prev)}</span>'

def meter_cell(val, prev_val=None, cls=""):
    return (f'<div class="vcpb{" " + cls if cls else ""}"><div class="meter"><i style="width:{val:.0f}%"></i></div>'
            f'<b>{val:.1f}</b>{delta_tag(val, prev_val)}</div>')

def score_cell(r, pr):
    pv = pr["score"] if pr else None
    cov_chg = bool(pr) and pr["hits"] != r["hits"]
    return (f'<div class="vcpb score"><div class="meter"><i style="width:{r["score"]:.0f}%"></i></div>'
            f'<b>{r["score"]:.1f}</b>{delta_tag(r["score"], pv)}</div>'
            f'<div class="subsc {chg_cls(cov_chg)}">覆蓋 <b>{r["hits"]}/4</b></div>')

def rank_cell(i, pr_rank):
    if pr_rank is None or pr_rank == i:
        return f'<td class="rk">{i}</td>'
    d = pr_rank - i
    arrow = f'<span class="chg dlt">{"▲" if d > 0 else "▼"}{abs(d)}</span>'
    return f'<td class="rk">{i}{arrow}</td>'

def cat_cell(sym):
    e = news_cur(sym); p = news_prev(sym)
    cat = (e.get("catalyst") or "").strip(); kind = (e.get("ckind") or "無").strip()
    pcat = (p.get("catalyst") or "").strip(); pkind = (p.get("ckind") or "無").strip()
    changed = bool(p) and (cat != pcat or kind != pkind)
    flag = (REVIEW.get("ticker_flags") or {}).get(sym)
    flag_html = f'<span class="rflag" title="{esc(flag.get("text", ""))}">{esc(flag["badge"])}</span>' if flag else ""
    warn = (REVIEW.get("catalyst_warn") or {}).get(sym)
    warn_html = (f'<span class="cwarn" title="{esc(warn["text"])}">事件日 {warn["ret"]:+.1f}% <i>{esc(warn["day"])}</i></span>'
                 if warn else "")
    if not cat:
        body = '<span class="nocat">跟大市</span>'
    else:
        low = e.get("confidence") == "低"
        cls = "catb" + (" chgb" if changed else "") + (" lowc" if low else "") + (" soldc" if warn else "")
        ttl = ' title="信心低：未有個股新聞來源"' if low else ""
        body = f'<span class="{cls}"{ttl}><i>{esc(kind)}</i>{esc(cat)}</span>'
    return body + warn_html + flag_html

CATL_DATE = re.compile(r"^(\d{1,2}/\d{1,2})\s+")

def cat_line_cell(sym):
    """One line answering 「喺咩催化之下先至由底回升」 — date, event, effect.

    The badge next door is a label (<=14 chars, no date); this column is the
    sentence: what happened, when, and what it did to the price. The text comes
    from the research layer (news*.json -> cat_line), never composed here."""
    e = news_cur(sym); p = news_prev(sym)
    line = (e.get("cat_line") or "").strip()
    if not line:
        return '<div class="catl none">—</div>'
    # the column is new in R9: a previous revision that never carried cat_line is
    # not evidence that the line "changed", so those rows render as normal text
    changed = bool(p) and bool((p.get("cat_line") or "").strip()) and line != p["cat_line"].strip()
    none_cls = " none" if line.startswith("無個股催化") else ""
    m = CATL_DATE.match(line)
    date_html = f'<i class="dt">{esc(m.group(1))}</i>' if m else ""
    body = line[m.end():] if m else line
    if "→" in body:
        ev, eff = body.split("→", 1)
        body_html = f'<b>{esc(ev.strip())}</b> <span class="eff">→ {esc(eff.strip())}</span>'
    else:
        body_html = f'<b>{esc(body)}</b>'
    return f'<div class="catl{none_cls} {chg_cls(changed)}">{date_html}{body_html}</div>'

def c7_cells(r, pr):
    def parts(row):
        c = row["cert_c"]
        retr = c["retrace_pct"]
        if retr >= 100: retr_s = "100%+"
        elif retr < 0:
            below = (row["close"] / c.get("pL", row["close"]) - 1) * 100 if c.get("pL") else None
            retr_s = (f'<span class="flagt">跌穿底 {below:+.1f}%</span>' if below is not None
                      else '<span class="flagt">跌穿底</span>')
        else: retr_s = f"{retr:.0f}%"
        maf = sum(c["ma_flags"])
        return {
            "brk": ('<span class="cok">✓突破</span>' if c["broke"] else '<span class="cno">未突破</span>'),
            "retr": retr_s,
            "held": f'{c["d_held"]}日' + ('<span class="cwarn">⚠曾破</span>' if c["undercut"] else ""),
            "dvr": (f'{c["dv_ratio"]:.2f}', c["dv_ratio"] < 0.85),
            "contr": (f'{c["contr"]:.2f}', c["contr"] < 0.6),
            "rs": (f'{c["rs21_pct"]:+.1f}%', c["rs21_pct"] > 0),
            "maf": (f'{maf}/3', maf == 3),
            "title": f'中間高位 {c["H_mid"]:g} · 其後高位 {c["post_high"]:g}',
        }
    a = parts(r); b = parts(pr) if pr else None
    def td(key, extra=""):
        v = a[key]; txt, ok = (v if isinstance(v, tuple) else (v, False))
        changed = b is not None and a[key] != b[key]
        cls = "nums c7" + (" cokt" if ok else "") + (" chg" if changed else "")
        return f'<td class="{cls}"{extra}>{txt}</td>'
    return (td("brk", f' title="{esc(a["title"])}"') + td("retr") + td("held")
            + td("dvr") + td("contr") + td("rs") + td("maf"))

CATL_TH = '<th class="srt" data-k="catl">催化 Catalyst<span class="thn">點解由底回升</span></th>'

C7_HEADS = (
    '<th class="srt" data-k="brk">突破<span class="thn">中間高位 · 25%</span></th>'
    '<th class="srt" data-k="retr">回補<span class="thn">最後跌幅 · 10%</span></th>'
    '<th class="srt" data-k="held">守底<span class="thn">未破日數 · 15%</span></th>'
    '<th class="srt" data-k="dvr">量比<span class="thn">跌/升日量 · 15%</span></th>'
    '<th class="srt" data-k="contr">遞減<span class="thn">末/首段跌幅 · 10%</span></th>'
    '<th class="srt" data-k="rs">RS<span class="thn">21日對中位 · 10%</span></th>'
    '<th class="srt" data-k="maf">均線<span class="thn">三項結構 · 15%</span></th>')

def row_attrs(r, changed, is_new, extra=""):
    c = r["cert_c"]; s = c["s"]
    e = news_cur(r["sym"])
    has_cat = 1 if (e.get("catalyst") or "").strip() else 0
    catl = (e.get("cat_line") or "").strip()
    has_catl = 0 if (not catl or catl.startswith("無個股催化")) else 1
    flag = (REVIEW.get("ticker_flags") or {}).get(r["sym"]) or {}
    deal = 1 if ("釘價" in flag.get("badge", "") or "併購目標" in flag.get("badge", "") or "合併目標" in flag.get("badge", "")) else 0
    newcls = ' class="rownew"' if is_new else ""
    return (f'data-vcp="{r["vcp"]}" data-cert="{r["cert"]}" data-brk="{s["break"]}"'
            f' data-retr="{c["retrace_pct"]}" data-held="{c["d_held"]}" data-dvr="{c["dv_ratio"]}"'
            f' data-contr="{c["contr"]}" data-rs="{c["rs21_pct"]}" data-maf="{sum(c["ma_flags"])}"'
            f' data-slope="{r["slope"]}" data-cat="{has_cat}" data-catl="{has_catl}" data-mcap="{r["mcap"]}"'
            f' data-chg="{1 if (changed or is_new) else 0}" data-deal="{deal}"{newcls}{extra}')

def why_decline(sym):
    e = news_cur(sym); p = news_prev(sym)
    changed = bool(p) and e.get("decline_short") != p.get("decline_short")
    return f'<div class="why {chg_cls(changed)}">{esc(e.get("decline_short", "—"))}</div>'

def why_recovery(sym):
    e = news_cur(sym); p = news_prev(sym)
    out = esc(e.get("recovery_short", "—"))
    for h in sorted(set(e.get("hot") or []), key=len, reverse=True):
        eh = esc(h)
        if eh and eh in out:
            out = out.replace(eh, f'<mark class="hot">{eh}</mark>', 1)
    conf = e.get("confidence", "低")
    src = e.get("sources") or []
    tip = (" · ".join(src)) if src else "未有個股新聞來源，只反映大市背景"
    text_chg = bool(p) and (e.get("recovery_short") != p.get("recovery_short") or (e.get("hot") or []) != (p.get("hot") or []))
    conf_chg = bool(p) and conf != p.get("confidence")
    return (f'<div class="why {chg_cls(text_chg)}">{out} '
            f'<span class="conf c{conf}{" chg" if conf_chg else ""}" title="來源：{esc(tip)}">信心{esc(conf)}</span></div>')

def sector_cell(r, pr):
    sub = r["gsub"] if (r["sp500"] and r.get("gsub")) else r["industry"]
    gtag = f'<i class="gics">GICS·{esc(r["gsec"])}</i>' if (r["sp500"] and r.get("gsec")) else ""
    changed = bool(pr) and (pr["sector_zh"], pr["industry"]) != (r["sector_zh"], r["industry"])
    src = r.get("sec_src")
    stag = f'<i class="gics">{esc(src)}</i>' if (src and not gtag) else ""
    return (f'<div class="sect {chg_cls(changed)}"><b>{esc(r["sector_zh"])}</b> <span>{esc(r["sector"])}</span>'
            f'{gtag}{stag}<em>{esc(sub)}</em></div>')

def mcap_txt(v):
    if v >= 1000: return f"${v/1000:.2f}T"
    if v >= 1: return f"${v:.1f}B"
    return f"${v*1000:.0f}M"

def tv_url(r):
    sym = r["sym"].replace("/", ".").lower()
    if r["exch"] != "—":
        return f'https://www.tradingview.com/chart/Q1c5VWwD/?symbol={r["exch"].lower()}%3A{esc(sym)}'
    return f'https://www.tradingview.com/chart/Q1c5VWwD/?symbol={esc(sym)}'

def same_basis(r, pr):
    """False when the previous revision's row used another MA window (page 1 in R7
    inherited the first sub-page's window), so MA / slope deltas would be apples
    to oranges and are not painted red."""
    return bool(pr) and (pr.get("L"), pr.get("W")) == (r.get("L"), r.get("W"))

def tick_cell(r, pr, L=None):
    sp = '<span class="badge">S&amp;P500</span>' if r["sp500"] else ""
    warn_now = r["below_ma"]; warn_prev = pr["below_ma"] if same_basis(r, pr) else warn_now
    warn = (f' <span class="warn{" chg" if warn_now != warn_prev else ""}">⚠低於MA</span>' if warn_now
            else (' <span class="chg">（已重上MA）</span>' if warn_prev else ""))
    ml = f'MA{L}' if L else "MA"
    newb = '' if pr or not PREV else '<span class="newb">新</span>'
    cap_chg = bool(pr) and pr["cap"] != r["cap"]
    cuts = M.get("cap_cuts_b", [10.0, 2.0])
    near = any(abs(r["mcap"] - cut) / cut <= 0.05 for cut in cuts)
    near_tag = '<i class="near" title="市值距分組界線 5% 以內，換日可能轉組">近界</i>' if near else ""
    cap = (f'<span class="capb{" chg" if cap_chg else ""}">{CAP_SHORT[r["cap"]]} {mcap_txt(r["mcap"])}'
           f'{near_tag}</span>')
    nm = r["name"]
    px_d = ""
    if pr and pr["close"] != r["close"]:
        px_d = f' <span class="chg dlt">({(r["close"] / pr["close"] - 1) * 100:+.1f}%)</span>'
    ma_d = delta_tag(r["ma"], pr["ma"] if same_basis(r, pr) else None, fmt="{:+.2f}", eps=0.005)
    return (f'<div class="tk"><a href="{tv_url(r)}" target="_blank" rel="noopener">{esc(r["sym"])}</a>'
            f'<span class="ex">{esc(r["exch"])}</span>{sp}{newb}'
            f'<em title="{esc(nm)}">{esc(nm if len(nm) <= 34 else nm[:33] + "…")}</em>'
            f'<span class="pxl nums">{r["close"]:g}{px_d} <span class="mut">/ {ml} {r["ma"]:g}</span>{ma_d}{warn}</span>'
            f'{cap}</div>')

def spark_cell(r, pr):
    sl_chg = same_basis(r, pr) and pr["slope"] != r["slope"]
    return (f'{spark_svg(r["spark"])}'
            f'<div class="subsc nums slope{" chg" if sl_chg else ""}">MA{r["L"]} {r["slope"]:+.2f}% <span class="mut">/{r["W"]}日</span></div>')

def bottoms_chain(hl, prev_hl):
    parts = [f'<span class="bot">{d[5:]}<i>@{p:g}</i></span>' for d, p in hl[-4:]]
    pre = '<span class="arr">…→</span>' if len(hl) > 4 else ""
    chain = '<span class="arr">→</span>'.join(parts)
    changed = prev_hl is not None and prev_hl != hl
    return f'<div class="botwrap {chg_cls(changed)}">{pre}{chain}</div>'

# Revisions that add trading days move every close and nudge every percentile;
# only a revision built on the same data date can treat those as updates.
NEW_TRADING_DAY = bool(PREV) and PREV["meta"]["last_date"] != M["last_date"]
# What counts as an "update" depends on what the revision did. A revision built
# on the SAME data date should move almost nothing, so a 2-point score shift is
# news. A revision that adds trading days moves everything — between R8 and R9
# the median row shifted 5.2 VCP points and 2.65 certainty points on two
# sessions — so the bar rises to a move that stands out from that background.
MATERIAL_PTS = 8.0 if NEW_TRADING_DAY else 2.0
MATERIAL_RANK = 10 if NEW_TRADING_DAY else 5

def row_changed(r, pr, pid):
    """A *material* difference vs the previous revision's row — the criterion
    behind the 只顯示有實質更新嘅行 toggle and the 有更新 counts.

    A rescan shifts every percentile-based score by a few tenths (median |ΔVCP|
    0.7, |Δ確定性| 1.2 between R7 and R8), and those small deltas are still
    painted red in the cell; but a row only counts as updated when something a
    reader would act on changed: the text / badge / confidence, a review flag,
    the bottom sequence, the cap bucket, the sector, MA status (same window),
    a score move of ≥2 points, or a page-1 rank move of ≥5 places."""
    if pr is None: return False
    sym = r["sym"]
    e = news_cur(sym); p = news_prev(sym)
    if p and any(e.get(k) != p.get(k) for k in ("decline_short", "recovery_short", "catalyst", "ckind", "confidence", "hot")):
        return True
    if sym in (REVIEW.get("ticker_flags") or {}) or sym in (REVIEW.get("catalyst_warn") or {}):
        return True
    keys = ["cap", "hl", "sector_zh", "industry"]
    if not NEW_TRADING_DAY:      # same data date: a moved close really is news
        keys.append("close")
    for k in keys:
        if pr.get(k) != r.get(k): return True
    if same_basis(r, pr) and pr.get("below_ma") != r.get("below_ma"): return True
    if abs(pr["vcp"] - r["vcp"]) >= MATERIAL_PTS or abs(pr["cert"] - r["cert"]) >= MATERIAL_PTS: return True
    if pid == "1":
        if pr.get("hits") != r.get("hits") or abs(pr.get("score", 0) - r.get("score", 0)) >= MATERIAL_PTS: return True
    return False

def sector_chips(rows):
    cnt = {}
    for r in rows:
        cnt[(r["sector_zh"], r["sector"])] = cnt.get((r["sector_zh"], r["sector"]), 0) + 1
    chips = "".join(f'<span class="chip"><b>{esc(z)}</b> {esc(e)} <i>{n}</i></span>'
                    for (z, e), n in sorted(cnt.items(), key=lambda x: -x[1]))
    return f'<div class="chips">{chips}</div>'

def cat_chips(rows):
    cnt = {}
    for r in rows:
        e = news_cur(r["sym"])
        k = (e.get("ckind") or "無") if (e.get("catalyst") or "").strip() else "無"
        cnt[k] = cnt.get(k, 0) + 1
    n_hot = sum(v for k, v in cnt.items() if k != "無")
    parts = "".join(f'<span class="chip cat"><b>{esc(k)}</b> <i>{v}</i></span>'
                    for k, v in sorted(cnt.items(), key=lambda x: -x[1]) if k != "無")
    tail = f'<span class="chip"><b>跟大市</b> <i>{cnt.get("無", 0)}</i></span>'
    return (f'<div class="chips"><span class="chip lead">有熱炒催化劑 <i>{n_hot}</i>/{len(rows)}</span>'
            f'{parts}{tail}</div>')

def dropped_strip(pid, cur_rows):
    if not PREV: return ""
    prev = PREV_P1 if pid == "1" else PREV_PAGE.get(pid, {})
    cur = {r["sym"] for r in cur_rows}
    gone = sorted(((rk, s) for s, (rk, _) in prev.items() if s not in cur))
    if not gone: return ""
    items = " ".join(f'<b>{esc(s)}</b><i>#{rk}</i>' for rk, s in gone)
    return f'<div class="dropped"><span class="dlab">跌出本頁（對比 {esc(PREV_REV)}）{len(gone)} 隻：</span>{items}</div>'

def table_sub(pid):
    pg = O["pages"][pid]
    L = pg["L"]
    head = (f'<tr><th>#<span class="thn">綜合排名</span></th><th>Ticker · 現價/MA{L} · 市值</th>'
            f'<th class="srt" data-k="cat">主要催化劑<span class="thn">熱炒 news-driven</span></th>'
            f'{CATL_TH}'
            f'<th class="srt" data-k="vcp">VCP<span class="thn">收縮指數</span></th>'
            f'<th class="srt" data-k="cert">確定性<span class="thn">7項合成</span></th>'
            f'{C7_HEADS}'
            f'<th class="srt" data-k="slope">60日走勢 · 斜率</th>'
            f'<th>底部序列<span class="thn">45日內 · 遞升</span></th>'
            f'<th>下跌原因<span class="thn">濃縮</span></th>'
            f'<th>回升原因<span class="thn">熱炒 highlight · 附信心</span></th><th>類別</th></tr>')
    rows = []; n_new = n_chg = 0
    for i, r in enumerate(pg["rows"], 1):
        pr_rank, pr = prev_of(pid, r["sym"])
        is_new = PREV is not None and pr is None
        changed = row_changed(r, pr, pid) or (pr_rank is not None and abs(pr_rank - i) >= MATERIAL_RANK)
        n_new += is_new; n_chg += (changed and not is_new)
        rows.append(
            f'<tr data-rk="{i}" {row_attrs(r, changed, is_new)}>{rank_cell(i, pr_rank)}<td>{tick_cell(r, pr, r.get("L") or L)}</td>'
            f'<td class="catc">{cat_cell(r["sym"])}</td>'
            f'<td class="catlc">{cat_line_cell(r["sym"])}</td>'
            f'<td>{meter_cell(r["vcp"], pr["vcp"] if pr else None)}</td>'
            f'<td>{meter_cell(r["cert"], pr["cert"] if pr else None, "certm")}</td>'
            f'{c7_cells(r, pr)}'
            f'<td>{spark_cell(r, pr)}</td>'
            f'<td class="bots">{bottoms_chain(r["hl"], pr["hl"] if pr else None)}</td>'
            f'<td class="whyc">{why_decline(r["sym"])}</td>'
            f'<td class="whyc">{why_recovery(r["sym"])}</td>'
            f'<td>{sector_cell(r, pr)}</td></tr>')
    return head, "".join(rows), pg, n_new, n_chg

def table_page1():
    head = (f'<tr><th>#<span class="thn">爆發排名</span></th><th>Ticker · 現價/MA · 市值</th>'
            f'<th class="srt" data-k="cat">主要催化劑<span class="thn">熱炒 news-driven</span></th>'
            f'{CATL_TH}'
            f'<th class="srt" data-k="score">爆發潛力分數<span class="thn">0.4×VCP + 0.4×確定性 + 0.2×覆蓋</span></th>'
            '<th class="srt" data-k="vcp">VCP<span class="thn">收縮指數</span></th>'
            '<th class="srt" data-k="cert">確定性<span class="thn">7項合成</span></th>'
            '<th>達標時間框<span class="thn">同組市值頁內排名</span></th>'
            f'{C7_HEADS}'
            '<th class="srt" data-k="slope">60日走勢 · 斜率</th>'
            '<th>下跌原因<span class="thn">濃縮</span></th>'
            '<th>回升原因<span class="thn">熱炒 highlight · 附信心</span></th><th>類別</th></tr>')
    labels = {"2": "1週", "3": "2週", "4": "1月", "5": "2月"}
    rows = []; n_new = n_chg = 0
    for i, r in enumerate(O["page1"], 1):
        pr_rank, pr = prev_of("1", r["sym"])
        is_new = PREV is not None and pr is None
        changed = row_changed(r, pr, "1") or (pr_rank is not None and abs(pr_rank - i) >= MATERIAL_RANK)
        n_new += is_new; n_chg += (changed and not is_new)
        frames = []
        for t, _, _ in TF:
            pid = f'{t}{r["cap"]}'
            cur_rk = r["ranks"].get(pid)
            prv_rk = pr["ranks"].get(f'{t}{pr["cap"]}') if pr else cur_rk
            fc = " chg" if (pr and cur_rk != prv_rk) else ""
            if cur_rk:
                frames.append(f'<span class="fr on{fc}">{labels[t]}<i>#{cur_rk}</i></span>')
            else:
                frames.append(f'<span class="fr{fc}">{labels[t]}</span>')
        attrs = row_attrs(r, changed, is_new, ' data-score="{}"'.format(r["score"]))
        rows.append(
            f'<tr data-rk="{i}" {attrs}>{rank_cell(i, pr_rank)}<td>{tick_cell(r, pr, r["L"])}</td>'
            f'<td class="catc">{cat_cell(r["sym"])}</td>'
            f'<td class="catlc">{cat_line_cell(r["sym"])}</td>'
            f'<td>{score_cell(r, pr)}</td>'
            f'<td>{meter_cell(r["vcp"], pr["vcp"] if pr else None)}</td>'
            f'<td>{meter_cell(r["cert"], pr["cert"] if pr else None, "certm")}</td>'
            f'<td class="frs">{"".join(frames)}</td>'
            f'{c7_cells(r, pr)}'
            f'<td>{spark_cell(r, pr)}</td>'
            f'<td class="whyc">{why_decline(r["sym"])}</td>'
            f'<td class="whyc">{why_recovery(r["sym"])}</td>'
            f'<td>{sector_cell(r, pr)}</td></tr>')
    return head, "".join(rows), n_new, n_chg

c = M["counts"]; cc = M["cap_counts"]
UNIVERSE_LINE = (f'Universe：全美上市普通股掃描 — 快照涵蓋 {c["total"]:,} 隻 · 存續至 {M["last_date"][5:]} 有報價 {c["current"]:,} 隻 · '
                 f'歷史 ≥90 交易日 {c["hist"]:,} 隻 · 價格 ≥$2 {c["price"]:,} 隻 · '
                 f'流動性達標（20日中位成交額 ≥$1M）{c["liq"]:,} 隻合資格'
                 f'（大型 {cc["a"]:,} · 中型 {cc["b"]:,} · 小型 {cc["c"]:,} · 無市值資料 {cc["x"]:,}）')

css = """
/* Light is the base palette; dark is the same tokens redefined, once for the
   viewer's system setting and once for the explicit [data-theme] the 淺色/深色
   button writes, so the button wins in both directions.
   --chg marks "changed since the previous revision" and is deliberately a
   muted grey in both themes: the deltas stay readable without the page
   shouting. --flag (amber) is for warnings that are about the STOCK — a deal
   pinning the price, a broken bottom — not about our own diff. */
:root{color-scheme:light;
 --pg:#f7f6f2;--sf:#ffffff;--ink:#141413;--ink2:#4b4a45;--mut:#75736c;
 --grid:#e5e3db;--axis:#c3c1b8;--ring:rgba(0,0,0,.13);
 --seq:#1a5fd0;--link:#1552bd;--good:#12752a;--warn:#8a5b00;--bad:#b3261e;
 --hl:#eef3fb;--meter:#dbe5f4;--okbg:#e7f4e3;--nobg:#fbeceb;
 --hotbg:#fff3d3;--hotink:#6b4700;--hotbd:#d9ac42;--capbg:#f3f2ed;
 --chg:#6f6d66;--chgbd:rgba(0,0,0,.16);--flag:#8a5b00}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){color-scheme:dark;
 --pg:#0d0d0d;--sf:#1a1a19;--ink:#ffffff;--ink2:#c3c2b7;--mut:#93918a;
 --grid:#2c2c2a;--axis:#383835;--ring:rgba(255,255,255,.10);
 --seq:#5b9dea;--link:#6da7ec;--good:#2fbf2f;--warn:#d99a2b;--bad:#e06c6c;
 --hl:#16202d;--meter:#25303e;--okbg:#15230f;--nobg:#2a1c1c;
 --hotbg:#4a3512;--hotink:#ffd479;--hotbd:#a8791f;--capbg:#232322;
 --chg:#9d9b93;--chgbd:rgba(255,255,255,.16);--flag:#d99a2b}}
:root[data-theme="dark"]{color-scheme:dark;
 --pg:#0d0d0d;--sf:#1a1a19;--ink:#ffffff;--ink2:#c3c2b7;--mut:#93918a;
 --grid:#2c2c2a;--axis:#383835;--ring:rgba(255,255,255,.10);
 --seq:#5b9dea;--link:#6da7ec;--good:#2fbf2f;--warn:#d99a2b;--bad:#e06c6c;
 --hl:#16202d;--meter:#25303e;--okbg:#15230f;--nobg:#2a1c1c;
 --hotbg:#4a3512;--hotink:#ffd479;--hotbd:#a8791f;--capbg:#232322;
 --chg:#9d9b93;--chgbd:rgba(255,255,255,.16);--flag:#d99a2b}
*{box-sizing:border-box}
body{margin:0;background:var(--pg);color:var(--ink);font:14px/1.5 system-ui,-apple-system,"Segoe UI","Noto Sans TC",sans-serif}
.wrap{max-width:1800px;margin:0 auto;padding:26px 20px 60px}
h1{font-size:21px;margin:0 0 4px}
.sub{color:var(--ink2);font-size:12.5px;margin-bottom:14px}
.card{background:var(--sf);border:1px solid var(--ring);border-radius:10px;padding:14px 16px;margin-bottom:14px}
h2{font-size:13px;margin:0 0 8px;color:var(--ink2);font-weight:600}
.rules{font-size:12.5px;color:var(--ink2);line-height:1.65}
.rules b{color:var(--ink)}
.mkt{font-size:12.5px;color:var(--ink2);line-height:1.7}
.mkt b{color:var(--ink)}
.mkt .mf{margin-top:6px}
.mkt .mf span{display:inline-block;background:var(--hl);border:1px solid var(--ring);border-radius:12px;
 padding:2px 9px;margin:2px 4px 2px 0;font-size:11.5px}
.mkt .mf span.chg{border-style:dashed}
/* the revision-delta card: same surface as every other card */
.upd h2{color:var(--ink2)}
.upd .ul{font-size:12.5px;color:var(--ink2);line-height:1.7}
.upd .ul b{color:var(--ink)}
.upd .ul li{margin:2px 0}
.upd .ul ul{margin:2px 0 6px 18px;padding:0}
.upd .k{color:var(--ink);font-weight:700}
/* the only mark an update carries: its numbers go grey. No fills, no borders,
   no colour — the change is there to be read, not to grab the eye. */
.chg{color:var(--chg)!important}
.chg b,.chg i,.chg em{color:var(--chg)!important}
.dlt{font-size:10px;font-weight:600;margin-left:3px;white-space:nowrap;color:var(--chg)}
.catb.chgb{border-style:dashed}
.newb{display:inline-block;font-size:9px;font-weight:600;color:var(--mut);background:transparent;
 border:1px solid var(--ring);border-radius:6px;padding:1px 5px;margin-left:6px;vertical-align:1px}
.flagt{color:var(--flag)!important;font-weight:600}
.rflag{display:inline-block;margin-top:4px;font-size:9.5px;font-weight:600;color:var(--flag);border:1px dashed var(--flag);
 border-radius:7px;padding:1px 6px;white-space:nowrap}
.dropped{font-size:11.5px;color:var(--ink2);border:1px dashed var(--ring);border-radius:8px;padding:6px 10px;margin-bottom:10px;
 line-height:1.9}
.dropped .dlab{color:var(--mut);font-weight:700;margin-right:4px}
.dropped b{color:var(--ink2);margin-left:8px}
.dropped i{font-style:normal;color:var(--mut);font-size:10px;margin-left:2px}
.nav{position:sticky;top:0;z-index:5;background:var(--pg);padding:10px 0 8px;
 border-bottom:1px solid var(--grid);margin-bottom:14px}
.navrow{display:flex;gap:6px;flex-wrap:wrap;align-items:center}
.navrow+.navrow{margin-top:7px}
.nav button{font:600 13px/1 system-ui,"Noto Sans TC",sans-serif;color:var(--ink2);background:var(--sf);
 border:1px solid var(--ring);border-radius:20px;padding:9px 14px;cursor:pointer}
.nav button .s{display:block;font-weight:400;font-size:10.5px;color:var(--mut);margin-top:3px}
.nav button.on{color:var(--pg);background:var(--ink);border-color:var(--ink)}
.nav button.on .s{color:var(--pg);opacity:.75}
.nav .sep{width:1px;align-self:stretch;background:var(--grid);margin:0 4px}
.nav .slab{font-size:10.5px;color:var(--mut)}
.nav button.sbtn{border-style:dashed;padding:7px 12px;font-size:12px}
.nav button.sbtn.on{border-style:solid}
.nav button.cbtn{border:1px solid var(--ring);color:var(--ink2);padding:7px 12px;font-size:12px}
.nav button.cbtn.on{background:var(--seq);color:var(--pg);border-color:var(--seq)}
.navrow.caps[hidden]{display:none}
.pghead{display:flex;flex-wrap:wrap;gap:8px 18px;align-items:baseline;margin:2px 0 10px;font-size:12.5px;color:var(--ink2)}
.pghead b{font-size:15px;color:var(--ink)}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:12px}
.chip{font-size:11.5px;color:var(--ink2);background:var(--sf);border:1px solid var(--ring);
 border-radius:14px;padding:4px 10px}
.chip b{color:var(--ink)}
.chip i{font-style:normal;font-weight:700;color:var(--seq)}
.chip.lead{background:var(--hotbg);border-color:var(--hotbd);color:var(--hotink)}
.chip.lead i{color:var(--hotink)}
.chip.cat b{color:var(--hotink)}
.chip.red{border-style:dashed;color:var(--ink2)}
.chip.red i{color:var(--ink)}
.tblwrap{overflow-x:auto;background:var(--sf);border:1px solid var(--ring);border-radius:10px}
table{border-collapse:collapse;width:100%;min-width:2320px;font-size:12.5px}
th{position:sticky;top:0;text-align:left;font-size:11px;color:var(--mut);font-weight:600;
 padding:9px 8px;border-bottom:1px solid var(--grid);background:var(--sf);white-space:nowrap;z-index:1;
 -webkit-user-select:none;user-select:none}
th.srt{cursor:pointer}
th.srt:hover{color:var(--ink)}
th.srt.sd::after{content:" ▼";color:var(--seq);font-size:9px}
th.srt.sa::after{content:" ▲";color:var(--seq);font-size:9px}
.rz{position:absolute;top:0;right:0;width:8px;height:100%;cursor:col-resize;z-index:2}
.rz:hover{background:linear-gradient(to right,transparent 4px,var(--seq) 4px,var(--seq) 6px,transparent 6px)}
.thn{display:block;font-weight:400;font-size:10px}
td{padding:8px 8px;border-bottom:1px solid var(--grid);vertical-align:middle;overflow:hidden}
tr:last-child td{border-bottom:0}
tr:hover td{background:var(--hl)}
tr[data-chg="0"].quiet{display:none}
tr[data-deal="1"].dealhide{display:none}
.catb.lowc{opacity:.55;border-style:dashed}
.catb.soldc{border-color:var(--flag);border-style:dashed}
.cwarn{display:block;margin-top:3px;font-size:9.5px;font-weight:600;color:var(--flag);white-space:nowrap}
.cwarn i{font-style:normal;font-weight:500;opacity:.8}
.capb .near{font-style:normal;color:var(--warn);margin-left:4px;font-weight:700}
.rk{color:var(--mut);font-weight:600;white-space:nowrap}
.nums{font-variant-numeric:tabular-nums;white-space:nowrap}
.mut{color:var(--mut)}
.tk a{color:var(--link);font-weight:700;text-decoration:none;font-size:13.5px}
.tk a:hover{text-decoration:underline}
.tk .ex{font-size:10px;color:var(--mut);margin-left:6px}
.tk em{display:block;font-style:normal;font-size:10.5px;color:var(--mut);max-width:180px;
 overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.tk .pxl{display:block;font-size:11px;margin-top:2px}
.capb{display:inline-block;margin-top:3px;font-size:9.5px;color:var(--ink2);background:var(--capbg);
 border:1px solid var(--ring);border-radius:8px;padding:1px 6px;font-variant-numeric:tabular-nums;white-space:nowrap}
.badge{font-size:9px;font-weight:700;color:var(--seq);border:1px solid var(--seq);
 border-radius:8px;padding:1px 5px;margin-left:6px;vertical-align:1px;white-space:nowrap}
.catc{max-width:150px}
.catlc{max-width:230px}
.catl{font-size:11.5px;line-height:1.5;color:var(--ink2)}
.catl b{color:var(--ink);font-weight:600}
.catl .dt{font-style:normal;color:var(--mut);font-variant-numeric:tabular-nums;margin-right:4px;font-weight:700}
.catl .eff{color:var(--mut)}
.catl.none,.catl.none b{color:var(--mut);font-weight:400}
.catb{display:inline-block;background:var(--hotbg);color:var(--hotink);border:1px solid var(--hotbd);
 border-radius:7px;padding:3px 8px;font-size:12px;font-weight:700;line-height:1.35}
.catb i{display:block;font-style:normal;font-size:9px;font-weight:600;opacity:.8;letter-spacing:.04em}
.nocat{font-size:11px;color:var(--mut)}
.vcpb{display:flex;align-items:center;gap:6px;min-width:86px}
.vcpb .meter{flex:1;height:6px;border-radius:3px;background:var(--meter);min-width:44px}
.vcpb .meter i{display:block;height:100%;border-radius:3px;background:var(--seq)}
.vcpb b{font-variant-numeric:tabular-nums;font-size:12.5px}
.score .meter i{background:var(--good)}
.certm .meter i{background:var(--warn)}
.subsc{font-size:10.5px;color:var(--mut);margin-top:3px;white-space:nowrap}
.subsc b{color:var(--ink2)}
/* the slope line is a .subsc too, so it needs the higher specificity to stay green */
.slope,.subsc.slope{color:var(--good);font-weight:600}
.subsc.slope.chg{color:var(--chg)}
.c7{font-size:11.5px;white-space:nowrap}
.c7 .cok{color:var(--good);font-weight:600}
.c7 .cno{color:var(--flag)}
.c7 .cwarn{color:var(--warn);font-size:9.5px;margin-left:3px}
.c7.cokt{color:var(--good);font-weight:600}
.bots{max-width:190px}
.botwrap{display:flex;flex-wrap:wrap;align-items:baseline;gap:2px 4px;max-width:190px}
.bot{white-space:nowrap;font-variant-numeric:tabular-nums;font-size:11px}
.bot i{font-style:normal;color:var(--mut);font-size:10px}
.arr{color:var(--axis);margin:0 3px}
.warn{color:var(--warn);font-size:10.5px;white-space:nowrap}
.whyc{min-width:165px;max-width:235px}
.why{font-size:11.5px;line-height:1.5;color:var(--ink2)}
mark.hot{background:var(--hotbg);color:var(--hotink);font-weight:700;border-radius:3px;padding:0 3px}
.why.chg mark.hot{color:var(--chg)}
.conf{display:inline-block;font-size:9.5px;border-radius:8px;padding:1px 6px;margin-left:2px;
 border:1px solid var(--ring);color:var(--mut);white-space:nowrap}
.conf.c高{color:var(--good);border-color:var(--good)}
.conf.c中{color:var(--warn);border-color:var(--warn)}
.conf.chg{color:var(--chg)!important;border-color:var(--chg)}
.sect b{font-size:12px}
.sect span{font-size:10.5px;color:var(--mut);margin-left:4px}
.sect em{display:block;font-style:normal;font-size:10.5px;color:var(--ink2)}
.gics{display:inline-block;font-style:normal;font-size:9px;color:var(--seq);border:1px solid var(--ring);
 border-radius:7px;padding:0 4px;margin-left:5px;vertical-align:1px}
.frs{white-space:nowrap}
.fr{display:inline-block;font-size:10.5px;color:var(--mut);border:1px dashed var(--axis);
 border-radius:9px;padding:2px 7px;margin-right:4px}
.fr.on{color:var(--ink);border:1px solid var(--seq);background:var(--hl)}
.fr.on i{font-style:normal;color:var(--seq);font-weight:700;margin-left:2px}
.fr.chg{border-color:var(--chg);color:var(--chg)}
.fr.chg i{color:var(--chg)}
.legend{display:flex;gap:16px;flex-wrap:wrap;font-size:11.5px;color:var(--ink2);margin:8px 2px 0}
.legend .sw{display:inline-block;width:14px;height:3px;vertical-align:3px;margin-right:5px;border-radius:2px}
.foot{font-size:11.5px;color:var(--ink2);line-height:1.7}
.foot b{color:var(--ink)}
section[hidden]{display:none}
@media (prefers-reduced-motion:no-preference){.nav button{transition:background .15s,color .15s}}
"""

# ---------------- cards ----------------
rule_notes = "".join(f'<br><span class="chg">✎ {esc(n)}</span>' for n in (REVIEW.get("rule_notes") or []))
rules_html = f"""
<div class="card rules">
<h2>篩選規則（10MA {RNAME} · 數據更新至 {int(M["last_date"][5:7])}月{int(M["last_date"][8:])}日收盤；每個時間框再分大／中／小型股，共 12 個子頁）</h2>
① <b>{esc(UNIVERSE_LINE)}</b>。<br>
② <b>市值分頁</b>：<b>a = 大型股 ≥$100億</b>、<b>b = 中型股 $20–100億</b>、<b>c = 小型股 &lt;$20億</b>；每個時間框各自取三組嘅 top 50（每組合資格數不足 50 就全部列出）。市值取自 Nasdaq 快照；無市值資料嘅（主要係封閉式基金）唔會硬塞入任何一組，改為喺各頁標示數目。<br>
③ <b>MA 上升</b>：PAGE 2a/b/c：<b>5 天 MA</b> 較 <b>5 個交易日</b>前高；PAGE 3/4/5（a/b/c）：<b>10 天 MA</b> 分別較 <b>10 / 21 / 42 個交易日</b>前高；且 MA 最後 3 日逐日上升、期內 ≥70% 日子上升。<br>
④ <b>「底」</b>（用戶原話：「大約跌了三天，然後見底回升了大約三天」）：某日收盤係 ±3 日內最低，且 3 日前收盤高過佢、3 日後收盤高過佢；相鄰 ≤3 日去重。 ⑤ <b>一底高於一底</b>：45 個交易日內 ≥2 個底逐個遞升，最近一個底喺 25 日內。<br>
⑥ <b>VCP 指數（0–100）</b>：10日/前30日波幅（35%）＋近10日區間佔價（25%）＋近10日/前30日成交量（20%）＋近15日/前30–45日區間（20%），全體合資格股票百分位合成。<br>
⑦ <b>確定性分數（0–100，7 項量化，逐項分欄）</b>：<b>突破</b>（最近兩個底之間高位已被升穿？25%）· <b>回補</b>（收復最後一段跌幅%，10%）· <b>守底</b>（最後一個底已守日數，15 日滿分；曾跌穿×0.25，15%）· <b>量比</b>（近15日跌日/升日成交量比，百分位，越低越好，15%）· <b>遞減</b>（末段÷首段跌幅，百分位，越低越好，10%）· <b>RS</b>（21日回報 − 全體中位數，百分位，10%）· <b>均線</b>（價&gt;20MA ＋ 20MA&gt;50MA ＋ 50MA向上，15%）。<br>
⑧ <b>排名</b>：12 個子頁按綜合分數（0.5×VCP ＋ 0.5×確定性）排；PAGE 1 總表 = 12 個名單嘅union，按爆發潛力分數（0.4×VCP ＋ 0.4×確定性 ＋ 0.2×覆蓋度）排。<br>
⑨ <b>主要催化劑欄</b>：每隻股票嘅<mark class="hot">市場熱炒 news-driven 主要催化劑</mark>以醒目 badge 精簡標出，並標明類型；純粹跟大市反彈、冇個股新聞嘅標「跟大市」。點欄標題可將有催化劑嘅排最前。<br>
⑨b <b>催化欄（新）</b>：一句講清楚「<b>喺咩催化之下，隻股先至由底回升</b>」——日期 · 事件 · 效果，例如「8/5 Q2收入升11%、EPS勝預期 → 業績後累升12%」；純粹跟大市嘅寫「無個股催化 · 隨大市／板塊回升」。內容全部由該股嘅新聞研究濃縮，唔會憑空生成。<br>
⑩ <b>操作</b>：頂欄第一行揀時間框、第二行揀市值組別；「按VCP排列／按確定性排列／按催化劑排列／預設排名」對當前頁生效；欄標題可點擊排序（先降後升）；<b>欄寬</b>可拖曳欄標題右邊界調整；<b>「只顯示有實質更新嘅行」</b>只留低同 {esc(PREV_REV)} 相比有實質分別嘅行（新上榜、文字／badge／信心、審視標記、底部序列、市值組、MA 狀態、VCP／確定性／分數變動 ≥{MATERIAL_PTS:.0f} 分、排名變動 ≥{MATERIAL_RANK} 位{"；本版加咗兩個交易日，門檻按大市自然波動調高" if NEW_TRADING_DAY else ""}）；分數嘅細微變動仍以灰色小字顯示但唔算「有實質更新」。<b>「淺色／深色」</b>掣可切換主題，選擇會記喺瀏覽器（唔揀就跟系統設定）。<br>
⑪ <b>下跌 / 回升原因</b>：AI 代理逐隻搜尋（<a href="https://bigdata.com" target="_blank" rel="noopener">Bigdata.com</a> 金融新聞索引＋公開網頁）後濃縮；信心：<b>高</b>＝明確個股消息；<b>中</b>＝板塊/部分證據；<b>低</b>＝只反映大市背景。{rule_notes}
</div>"""

def sentences(t): return [s for s in t.replace("。", "。\n").split("\n") if s.strip()]
mkt_html = ""
if MKT:
    prev_sum = PMKT["summary_zh"] if PMKT else MKT["summary_zh"]
    prev_periods = {f["period"] for f in (PMKT or MKT).get("factors", [])}
    ps = set(sentences(prev_sum))
    body = "".join(f'<span class="chg">{esc(s)}</span>' if s not in ps else esc(s) for s in sentences(MKT["summary_zh"]))
    factors = "".join(
        f'<span class="{"chg" if f["period"] not in prev_periods else ""}"><b>{esc(f["period"])}</b> {esc(f["factor_zh"])}</span>'
        for f in MKT.get("factors", []))
    mkt_html = (f'<div class="card mkt"><h2>2026年6–9月 市場背景（底部成因的共同分母）</h2>'
                f'{body}<div class="mf">{factors}</div></div>')

LEGEND = ('<div class="legend"><span><i class="sw" style="background:var(--ink2)"></i>收盤</span>'
          '<span><i class="sw" style="background:var(--seq)"></i>MA（頁面各自 5/10 天）</span>'
          '<span><i class="sw" style="background:var(--good);height:8px;width:8px;border-radius:50%"></i>底部（最後60個交易日）</span>'
          '<span><span class="catb" style="padding:1px 6px;font-size:10px"><i>類型</i>主要催化劑</span> = 市場熱炒 news-driven 動力</span>'
          f'<span><span class="chg">紅色</span> = 相對 {esc(PREV_REV)} 有更新（<span class="newb" style="margin:0">新</span> 新上榜 · ▲▼ 排名變動 · 紅字/紅底 = 該格內容有變 · 小紅字 = 數值變動幅度）</span>'
          '<span># 欄固定顯示預設排名；點欄標題排序（▼降序 ▲升序）；拖欄邊調闊度；量比、遞減越低越好</span></div>')

secs = []; totals = {"new": 0, "chg": 0, "dropped": 0}
head1, body1, n_new, n_chg = table_page1()
totals["new"] += n_new; totals["chg"] += n_chg
cap_n = {b: sum(1 for r in O["page1"] if r["cap"] == b) for b in ("a", "b", "c")}
drop1 = dropped_strip("1", O["page1"]); totals["dropped"] += drop1.count("<b>")
p1_flags = f'<span class="chip red">新上榜 <i>{n_new}</i> · 有更新 <i>{n_chg}</i></span>' if PREV else ""
pghead1 = (f'<div class="pghead"><b>總表 · 爆發潛力排名</b>'
           f'<span>12 個子頁名單合共 <b>{len(O["page1"])}</b> 隻不重複股票'
           f'（大型 {cap_n["a"]} · 中型 {cap_n["b"]} · 小型 {cap_n["c"]}）</span>'
           f'<span>排序 = 0.4×VCP + 0.4×確定性 + 0.2×覆蓋度</span>'
           f'<span>覆蓋度 = 通過該時間框 MA 條件嘅時間框數目（亮起 = 入咗同組市值該頁 top 50）</span>'
           f'<span>斜率／MA 欄統一為 MA10 較 10 日前（顯示口徑，唔一定係佢通過嘅時間框）</span>{p1_flags}</div>')
secs.append(f'''<section id="p1">
{pghead1}{mkt_html}{drop1}{cat_chips(O["page1"])}{sector_chips(O["page1"])}
<div class="tblwrap"><table><thead>{head1}</thead><tbody>{body1}</tbody></table></div>
{LEGEND}
</section>''')

for t, tlab, tsub in TF:
    for cb, clab, csub in CAPS:
        pid = f"{t}{cb}"
        head, body, pg, n_new, n_chg = table_sub(pid)
        totals["new"] += n_new; totals["chg"] += n_chg
        drop = dropped_strip(pid, pg["rows"]); totals["dropped"] += drop.count("<b>")
        flags = f'<span class="chip red">新上榜 <i>{n_new}</i> · 有更新 <i>{n_chg}</i></span>' if PREV else ""
        pghead = (f'<div class="pghead"><b>PAGE {pid} · {tlab} · {clab}</b>'
                  f'<span>{tsub} · {csub}</span>'
                  f'<span>合資格 <b>{pg["qualified"]}</b> 隻 → 按綜合分數（0.5×VCP＋0.5×確定性）'
                  f'取 top 50，本頁列出 <b>{len(pg["rows"])}</b> 隻</span>{flags}</div>')
        secs.append(f'''<section id="p{pid}" hidden>
{pghead}{drop}{cat_chips(pg["rows"])}{sector_chips(pg["rows"])}
<div class="tblwrap"><table><thead>{head}</thead><tbody>{body}</tbody></table></div>
{LEGEND}
</section>''')

# ---------------- update card (what changed vs previous revision) ----------------
upd_html = ""
if PREV:
    prev_date = PREV["meta"]["last_date"]
    date_line = (f'數據終點 <b>{M["last_date"]}</b>（{esc(PREV_REV)} 為 {prev_date}）' if prev_date != M["last_date"]
                 else f'數據終點 <b>{M["last_date"]}</b>，與 {esc(PREV_REV)} 相同 —— 本版變動全部來自審視後嘅修正，唔係新交易日')
    notes = REVIEW.get("notes") or []
    notes_html = "".join(
        f'<li><span class="k">{esc(n.get("title", ""))}</span> {esc(n.get("text", ""))}'
        + (f' <span class="mut">［{esc("、".join(n["tickers"]))}］</span>' if n.get("tickers") else "") + '</li>'
        for n in notes)
    headline = REVIEW.get("headline") or ""
    upd_html = f'''<div class="card upd">
<h2>本版更新 · {esc(REV)} 對比 {esc(PREV_REV)}（更新內容以灰色小字標示，唔再用高亮）</h2>
<div class="ul">{date_line}。<br>
新上榜 <span class="k">{totals["new"]}</span> 行 · 跌出 <span class="k">{totals["dropped"]}</span> 行 · 其他有更新 <span class="k">{totals["chg"]}</span> 行（跨 13 頁合計；同一股票喺多頁出現會重複計）。
{("<br><b>批判性審視結論：</b>" + esc(headline)) if headline else ""}
{("<br><b>獨立覆核：</b>" + esc(REVIEW["review_summary"])) if REVIEW.get("review_summary") else ""}
{("<ul>" + notes_html + "</ul>") if notes_html else ""}</div></div>'''

tf_btns = '<button data-t="1" class="on">PAGE 1 · 總表<span class="s">爆發潛力排名</span></button>' + "".join(
    f'<button data-t="{t}">PAGE {t} · {lab}<span class="s">{sub}</span></button>' for t, lab, sub in TF)
cap_btns = "".join(
    '<button data-c="{}"{}>{}<span class="s">{}</span></button>'.format(
        cb, ' class="on"' if cb == "a" else "", clab, csub)
    for cb, clab, csub in CAPS)
sort_btns = ('<span class="sep"></span><span class="slab">排序：</span>'
             '<button class="sbtn" data-sort="vcp">按 VCP 排列</button>'
             '<button class="sbtn" data-sort="cert">按 確定性 排列</button>'
             '<button class="sbtn" data-sort="cat">按 催化劑 排列</button>'
             '<button class="sbtn" data-sort="catl">有催化先排</button>'
             '<button class="sbtn" data-sort="rk">預設排名</button>'
             + (f'<span class="sep"></span><button class="cbtn" id="onlychg" title="新上榜、文字／badge／信心、審視標記、底部序列、市值組、MA 狀態、分數變動 ≥{MATERIAL_PTS:.0f} 分、排名變動 ≥{MATERIAL_RANK} 位">只顯示有實質更新嘅行</button>' if PREV else "")
             + '<button class="cbtn" id="hidedeal" title="隱藏被收購／換股合併釘住價格嘅目標公司">隱藏併購釘價股</button>'
             + '<span class="sep"></span><button class="cbtn" id="theme" title="淺色／深色主題（記住你嘅選擇）">深色</button>')

foot = f"""
<div class="card foot">
<h2>備註 · 數據 lineage</h2>
① 覆蓋範圍：可達數據源覆蓋美國上市普通股 {c["total"]:,} 隻（含 S&amp;P 500 全部 503 隻）；外國註冊而非 S&amp;P 500 嘅美國上市股（部分 ADR）未有完整歷史，未納入掃描。價格未除息調整。<br>
② 數據重建：GitHub 每日 Nasdaq 快照鏡像（zyhe16/top-us-stock-tickers）逐 commit 重建每日收盤序列，共 {M["n_days"]} 個交易日（{M["cal_first"]} → {M["cal_last"]}）；4 日無快照以前值填補；08-27 收盤以官方 net-change 校正。<br>②b <b>最新交易日</b>：鏡像未及時出快照時，由本 repo 嘅 GitHub Actions runner 直接抓取同一個 Nasdaq screener 來源並回傳，逐日接駁上序列；接駁前以「當日收盤減官方 net-change」反推前收同序列對賬（08-31、09-01 兩步中位偏差均 0.000%）。偏差 &gt;20% 者為公司行動：比例乾淨嘅拆股／合股按比例重算歷史股數基準（價格乘比例、成交量除比例，成交額不變）而保留；唔似拆股嘅整隻剔除。當日無報價嘅失去「存續至最新交易日」資格。<span class="chg">09-01 bar 嘅成交量已用鏡像 28 分鐘後嘅完整版本補齊（價格 7,153/7,153 完全相同；29 隻細價股成交量上調，無一隻係上榜股）。</span><br>
②c <b>數據修正（R8 起）</b>：(1) 鏡像補值嘅四日唔會成為「底」，底部嘅 ±3 日比較用真實收盤（窗口同守底日數仍按交易日計）；(2) 成交量不完整日同補值日唔計入量比及 VCP 成交量項；(3) universe 剔除封閉式基金／信託／優先股／票據，REIT、BDC、MLP、ADR 保留；(4) S&P 500 成份股類別改用 GICS。<br>②d <b>R9 新增</b>：09-02 冇任何收市快照（鏡像當日 commit 喺美東 10:33 開市中途），該日收市價由 09-03 快照嘅官方 net-change 反推（每隻股票精確到仙），成交量則<b>完全冇數據</b>（記為 0），因此 09-02 唔計入量比、VCP 成交量項同流動性中位數 —— 價格係真實嘅，成交量係缺失嘅，兩者分開處理。公司行動用鏡像 09-02 開市中途價做支點檢查：只有 APH（1 拆 2）達到「至少減半／翻倍且合乎 n:1 比例」嘅門檻而重算歷史；FCUV 等 20–50% 嘅一日波幅視為真實走勢，唔會當拆股改寫歷史。<br>
③ 市值：Nasdaq 快照 market cap（{M["cap_cuts_b"][0]:.0f}／{M["cap_cuts_b"][1]:.0f} 十億美元為界）；類別：Nasdaq 分類＋GICS（S&amp;P 500，klaywang24/market-chronicle）；交易所：irachex/open-stock-data。<br>
④ 確定性 7 項、VCP、排名經獨立代理人對抗性驗證；原因欄及催化劑由 AI 代理透過 <a href="https://bigdata.com" target="_blank" rel="noopener">Bigdata.com</a> 新聞索引及公開網頁逐隻搜尋、核實再濃縮 —— 內容係新聞摘要，可能有錯漏，請以原始公告為準。<br>
⑤ <b>數據終點 {M["last_date"]}，建置時間 {BUILD_TS}</b> · 快照只有收盤/成交量，VCP 及確定性以收盤序列計算 · 本表只係篩選工具，唔係投資建議。<br>
⑥ 連結格式：Ticker 點擊開 TradingView chart（https://www.tradingview.com/chart/Q1c5VWwD/?symbol=交易所%3Aticker）。
</div>"""

js = """
(function() {
  var tfb = document.querySelectorAll('.nav button[data-t]');
  var cpb = document.querySelectorAll('.nav button[data-c]');
  var sbtns = document.querySelectorAll('.nav button[data-sort]');
  var caprow = document.getElementById('caprow');
  var onlyBtn = document.getElementById('onlychg');
  var dealBtn = document.getElementById('hidedeal');
  var themeBtn = document.getElementById('theme');
  var hideDeal = false;
  var NAVKEY = 'ma10nav-' + (document.title.match(/R\\d+/) || ['x'])[0];
  var state = { t: '1', c: 'a' };
  var sortOf = {};
  var onlyChg = false;
  function pid() { return state.t === '1' ? '1' : state.t + state.c; }
  function syncSortBtns() {
    var cur = sortOf['p' + pid()] || 'rk';
    sbtns.forEach(function(b) { b.classList.toggle('on', b.dataset.sort === cur); });
  }
  function applyOnly() {
    document.querySelectorAll('tbody tr[data-chg="0"]').forEach(function(r) { r.classList.toggle('quiet', onlyChg); });
    if (onlyBtn) onlyBtn.classList.toggle('on', onlyChg);
  }
  function show() {
    var id = 'p' + pid();
    document.querySelectorAll('section[id^="p"]').forEach(function(s) { s.hidden = (s.id !== id); });
    tfb.forEach(function(b) { b.classList.toggle('on', b.dataset.t === state.t); });
    cpb.forEach(function(b) { b.classList.toggle('on', b.dataset.c === state.c); });
    caprow.hidden = (state.t === '1');
    syncSortBtns();
    try { localStorage.setItem(NAVKEY, JSON.stringify(state)); } catch (e) {}
  }
  tfb.forEach(function(b) { b.addEventListener('click', function() { state.t = b.dataset.t; show(); }); });
  cpb.forEach(function(b) { b.addEventListener('click', function() { state.c = b.dataset.c; show(); }); });
  if (onlyBtn) onlyBtn.addEventListener('click', function() { onlyChg = !onlyChg; applyOnly(); });
  if (dealBtn) dealBtn.addEventListener('click', function() {
    hideDeal = !hideDeal;
    document.querySelectorAll('tbody tr[data-deal="1"]').forEach(function(r) { r.classList.toggle('dealhide', hideDeal); });
    dealBtn.classList.toggle('on', hideDeal);
  });
  function sysDark() {
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  }
  function curTheme() {
    var set = document.documentElement.getAttribute('data-theme');
    return set === 'dark' || set === 'light' ? set : (sysDark() ? 'dark' : 'light');
  }
  function paintThemeBtn() {
    if (!themeBtn) return;
    var t = curTheme();
    themeBtn.textContent = t === 'dark' ? '☀ 淺色' : '☾ 深色';
    themeBtn.title = (t === 'dark' ? '而家係深色主題，撳一下轉淺色' : '而家係淺色主題，撳一下轉深色') + '（記住你嘅選擇）';
  }
  if (themeBtn) themeBtn.addEventListener('click', function() {
    var next = curTheme() === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    try { localStorage.setItem('ma10theme', next); } catch (e) {}
    paintThemeBtn();
  });
  if (window.matchMedia) {
    var mq = window.matchMedia('(prefers-color-scheme: dark)');
    var onSys = function() { if (!document.documentElement.getAttribute('data-theme')) paintThemeBtn(); };
    if (mq.addEventListener) mq.addEventListener('change', onSys);
    else if (mq.addListener) mq.addListener(onSys);
  }
  paintThemeBtn();

  try {
    var sv = JSON.parse(localStorage.getItem(NAVKEY) || 'null');
    if (sv && sv.t && sv.c && document.getElementById('p' + (sv.t === '1' ? '1' : sv.t + sv.c))) state = sv;
  } catch (e) {}
  show();

  function visTable() {
    var sec = document.querySelector('section[id^="p"]:not([hidden])');
    return sec ? sec.querySelector('table') : null;
  }
  function sortRows(tbl, key, dir) {
    var tb = tbl.tBodies[0];
    var rows = Array.prototype.slice.call(tb.rows);
    rows.sort(function(a, b) {
      var av = parseFloat(a.dataset[key]), bv = parseFloat(b.dataset[key]);
      if (isNaN(av)) av = -1e9;
      if (isNaN(bv)) bv = -1e9;
      if (av === bv) return (+a.dataset.rk) - (+b.dataset.rk);
      return dir === 'asc' ? av - bv : bv - av;
    });
    rows.forEach(function(r) { tb.appendChild(r); });
  }
  function markHead(tbl, key, dir) {
    tbl.querySelectorAll('th.srt').forEach(function(t) {
      t.classList.remove('sd', 'sa');
      if (key && t.dataset.k === key) t.classList.add(dir === 'asc' ? 'sa' : 'sd');
      if (!key || t.dataset.k !== key) delete t.dataset.dir;
    });
  }
  function secIdOf(tbl) { var s = tbl.closest('section'); return s ? s.id : ''; }
  document.querySelectorAll('th.srt').forEach(function(th) {
    th.addEventListener('click', function() {
      var tbl = th.closest('table');
      var dir = th.dataset.dir === 'desc' ? 'asc' : 'desc';
      th.dataset.dir = dir;
      sortRows(tbl, th.dataset.k, dir);
      markHead(tbl, th.dataset.k, dir);
      sortOf[secIdOf(tbl)] = (dir === 'desc') ? th.dataset.k : 'asc:' + th.dataset.k;
      syncSortBtns();
    });
  });
  sbtns.forEach(function(b) {
    b.addEventListener('click', function() {
      var tbl = visTable();
      if (!tbl) return;
      var k = b.dataset.sort;
      if (k === 'rk') { sortRows(tbl, 'rk', 'asc'); markHead(tbl, null); }
      else { sortRows(tbl, k, 'desc'); markHead(tbl, k, 'desc'); }
      sortOf[secIdOf(tbl)] = k;
      syncSortBtns();
    });
  });

  document.querySelectorAll('.tblwrap table').forEach(function(tbl) {
    var ths = tbl.querySelectorAll('thead th');
    function freeze() {
      if (tbl.dataset.frozen) return;
      var total = 0;
      ths.forEach(function(t) { t.style.width = t.offsetWidth + 'px'; total += t.offsetWidth; });
      tbl.style.tableLayout = 'fixed';
      tbl.style.minWidth = '0';
      tbl.style.width = total + 'px';
      tbl.dataset.frozen = '1';
    }
    ths.forEach(function(th) {
      var h = document.createElement('span');
      h.className = 'rz';
      h.title = '拖曳調整欄寬';
      th.appendChild(h);
      h.addEventListener('click', function(e) { e.stopPropagation(); });
      h.addEventListener('mousedown', function(e) {
        e.preventDefault(); e.stopPropagation();
        freeze();
        var startX = e.pageX, w0 = th.offsetWidth, t0 = tbl.offsetWidth;
        function mv(ev) {
          var w = Math.max(40, w0 + (ev.pageX - startX));
          th.style.width = w + 'px';
          tbl.style.width = (t0 + (w - w0)) + 'px';
        }
        function up() {
          document.removeEventListener('mousemove', mv);
          document.removeEventListener('mouseup', up);
        }
        document.addEventListener('mousemove', mv);
        document.addEventListener('mouseup', up);
      });
    });
  });
})();
"""

html_doc = f"""<title>10MA Uptrend Watchlist {RNAME}</title>
<style>{css}</style>
<script>
/* applied before first paint so a saved choice never flashes the other theme */
(function(){{try{{var t=localStorage.getItem('ma10theme');
if(t==='dark'||t==='light')document.documentElement.setAttribute('data-theme',t);}}catch(e){{}}}})();
</script>
<div class="wrap">
<h1>10MA Uptrend Watchlist {RNAME}（一底高於一底 × VCP × 底部確定性 · 大中小型股分頁）</h1>
<div class="sub">數據至 <b>{M["last_date"]}</b> 收盤 · 全美掃描 {c["liq"]:,} 隻合資格 · 13 頁：總表＋4 個時間框 × 大／中／小型股 · 新增<b>催化欄</b>（點解由底回升） · 頂欄可切換<b>淺色／深色</b> · 相對 {esc(PREV_REV)} 嘅更新以灰色小字標示，可一鍵只睇有更新嘅行 · VCP／確定性／7項證據可排序 · 欄寬可拖曳</div>
{upd_html}
{rules_html}
<nav class="nav">
<div class="navrow">{tf_btns}{sort_btns}</div>
<div class="navrow caps" id="caprow"><span class="slab">市值組別：</span>{cap_btns}</div>
</nav>
{"".join(secs)}
{foot}
</div>
<script>{js}</script>
"""

out_path = f"{SCRATCH}/{OUTNAME}"
open(out_path, "w", encoding="utf-8").write(html_doc)
print("wrote", out_path, f"{len(html_doc)/1024:.0f} KB", "| new", totals["new"], "changed", totals["chg"], "dropped", totals["dropped"])

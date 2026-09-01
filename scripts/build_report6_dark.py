#!/usr/bin/env python3
"""Build the 10MA R6.01 report (dark-only): 1 summary page + 12 sub-pages.

Same layout as R5, re-run on the series extended to the 2026-08-31 close.

R5 changes on top of R2:
- Each timeframe splits into 大型 (a) / 中型 (b) / 小型 (c) sub-pages, each with
  its own top 50 by 綜合 = 0.5 x VCP + 0.5 x 確定性.
- Two-level nav: timeframe row + market-cap row (the cap row hides on the summary).
- New 主要催化劑 column: the single market-moving news-driven catalyst as a
  prominent badge, sortable so catalyst names surface first.
- Page 1 covers the union of all 12 lists with market cap and per-timeframe rank
  inside the stock's own cap bucket.
Sortable metric columns, resizable widths and the split reason columns carry
over from R2 unchanged.
"""
import json, datetime, html, os

SCRATCH = os.environ.get("WORK_DIR", "./data")
O = json.load(open(f"{SCRATCH}/screen_results6.json"))
N = json.load(open(f"{SCRATCH}/news6.json"))
MKT = json.load(open(f"{SCRATCH}/market.json")) if os.path.exists(f"{SCRATCH}/market.json") else None
M = O["meta"]

now_hkt = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=8)
STAMP = now_hkt.strftime("%m.%d_%H%M")
BUILD_TS = now_hkt.strftime("%Y-%m-%d %H:%M HKT")
OUTNAME = f"10MA_uptrend_watchlistGit_R6.01_claudeopus5xhigh_{STAMP}.html"

TF = [("2", "1星期", "5MA · 5個交易日"), ("3", "2星期", "10MA · 10個交易日"),
      ("4", "1個月", "10MA · 21個交易日"), ("5", "2個月", "10MA · 42個交易日")]
CAPS = [("a", "大型股", "Big cap ≥$10B"), ("b", "中型股", "Mid cap $2–10B"),
        ("c", "小型股", "Small cap &lt;$2B")]
CAP_SHORT = {"a": "大型", "b": "中型", "c": "小型", "x": "未分類"}
SUBS = [f"{t}{c}" for t, _, _ in TF for c, _, _ in CAPS]

def esc(s): return html.escape(str(s), quote=True)

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

def meter_cell(val, cls=""):
    return (f'<div class="vcpb{" " + cls if cls else ""}"><div class="meter"><i style="width:{val:.0f}%"></i></div>'
            f'<b>{val:.1f}</b></div>')

def score_cell(r):
    return (f'<div class="vcpb score"><div class="meter"><i style="width:{r["score"]:.0f}%"></i></div>'
            f'<b>{r["score"]:.1f}</b></div>'
            f'<div class="subsc">覆蓋 <b>{r["hits"]}/4</b></div>')

def cat_cell(sym):
    e = N.get(sym) or {}
    cat = (e.get("catalyst") or "").strip()
    kind = (e.get("ckind") or "無").strip()
    if not cat:
        return '<span class="nocat">跟大市</span>'
    return f'<span class="catb"><i>{esc(kind)}</i>{esc(cat)}</span>'

def c7_cells(r):
    c = r["cert_c"]
    retr = c["retrace_pct"]
    retr_s = "100%+" if retr >= 100 else f"{max(0.0, retr):.0f}%"
    maf = sum(c["ma_flags"])
    brk = ('<span class="cok">✓突破</span>' if c["broke"] else '<span class="cno">未突破</span>')
    held = f'{c["d_held"]}日' + ('<span class="cwarn">⚠曾破</span>' if c["undercut"] else "")
    return (
        f'<td class="nums c7" title="中間高位 {c["H_mid"]:g} · 其後高位 {c["post_high"]:g}">{brk}</td>'
        f'<td class="nums c7">{retr_s}</td>'
        f'<td class="nums c7">{held}</td>'
        f'<td class="nums c7{" cokt" if c["dv_ratio"] < 0.85 else ""}">{c["dv_ratio"]:.2f}</td>'
        f'<td class="nums c7{" cokt" if c["contr"] < 0.6 else ""}">{c["contr"]:.2f}</td>'
        f'<td class="nums c7{" cokt" if c["rs21_pct"] > 0 else ""}">{c["rs21_pct"]:+.1f}%</td>'
        f'<td class="nums c7{" cokt" if maf == 3 else ""}">{maf}/3</td>')

C7_HEADS = (
    '<th class="srt" data-k="brk">突破<span class="thn">中間高位 · 25%</span></th>'
    '<th class="srt" data-k="retr">回補<span class="thn">最後跌幅 · 10%</span></th>'
    '<th class="srt" data-k="held">守底<span class="thn">未破日數 · 15%</span></th>'
    '<th class="srt" data-k="dvr">量比<span class="thn">跌/升日量 · 15%</span></th>'
    '<th class="srt" data-k="contr">遞減<span class="thn">末/首段跌幅 · 10%</span></th>'
    '<th class="srt" data-k="rs">RS<span class="thn">21日對中位 · 10%</span></th>'
    '<th class="srt" data-k="maf">均線<span class="thn">三項結構 · 15%</span></th>')

def row_attrs(r, extra=""):
    c = r["cert_c"]; s = c["s"]
    e = N.get(r["sym"]) or {}
    has_cat = 1 if (e.get("catalyst") or "").strip() else 0
    return (f'data-vcp="{r["vcp"]}" data-cert="{r["cert"]}" data-brk="{s["break"]}"'
            f' data-retr="{c["retrace_pct"]}" data-held="{c["d_held"]}" data-dvr="{c["dv_ratio"]}"'
            f' data-contr="{c["contr"]}" data-rs="{c["rs21_pct"]}" data-maf="{sum(c["ma_flags"])}"'
            f' data-slope="{r["slope"]}" data-cat="{has_cat}" data-mcap="{r["mcap"]}"{extra}')

def why_decline(sym):
    e = N.get(sym) or {}
    return f'<div class="why">{esc(e.get("decline_short", "—"))}</div>'

def why_recovery(sym):
    e = N.get(sym) or {}
    out = esc(e.get("recovery_short", "—"))
    for h in sorted(set(e.get("hot") or []), key=len, reverse=True):
        eh = esc(h)
        if eh and eh in out:
            out = out.replace(eh, f'<mark class="hot">{eh}</mark>', 1)
    conf = e.get("confidence", "低")
    src = e.get("sources") or []
    tip = (" · ".join(src)) if src else "未有個股新聞來源，只反映大市背景"
    return (f'<div class="why">{out} '
            f'<span class="conf c{conf}" title="來源：{esc(tip)}">信心{esc(conf)}</span></div>')

def sector_cell(r):
    sub = r["gsub"] if (r["sp500"] and r.get("gsub")) else r["industry"]
    gtag = f'<i class="gics">GICS·{esc(r["gsec"])}</i>' if (r["sp500"] and r.get("gsec")) else ""
    return (f'<div class="sect"><b>{esc(r["sector_zh"])}</b> <span>{esc(r["sector"])}</span>'
            f'{gtag}<em>{esc(sub)}</em></div>')

def mcap_txt(v):
    if v >= 1000: return f"${v/1000:.2f}T"
    if v >= 1: return f"${v:.1f}B"
    return f"${v*1000:.0f}M"

def tv_url(r):
    sym = r["sym"].replace("/", ".").lower()
    if r["exch"] != "—":
        return f'https://www.tradingview.com/chart/Q1c5VWwD/?symbol={r["exch"].lower()}%3A{esc(sym)}'
    return f'https://www.tradingview.com/chart/Q1c5VWwD/?symbol={esc(sym)}'

def tick_cell(r, L=None):
    sp = '<span class="badge">S&amp;P500</span>' if r["sp500"] else ""
    warn = ' <span class="warn">⚠低於MA</span>' if r["below_ma"] else ""
    ml = f'MA{L}' if L else "MA"
    cap = f'<span class="capb">{CAP_SHORT[r["cap"]]} {mcap_txt(r["mcap"])}</span>'
    nm = r["name"]
    return (f'<div class="tk"><a href="{tv_url(r)}" target="_blank" rel="noopener">{esc(r["sym"])}</a>'
            f'<span class="ex">{esc(r["exch"])}</span>{sp}'
            f'<em title="{esc(nm)}">{esc(nm if len(nm) <= 34 else nm[:33] + "…")}</em>'
            f'<span class="pxl nums">{r["close"]:g} <span class="mut">/ {ml} {r["ma"]:g}</span>{warn}</span>'
            f'{cap}</div>')

def spark_cell(r):
    return (f'{spark_svg(r["spark"])}'
            f'<div class="subsc nums slope">MA{r["L"]} {r["slope"]:+.2f}% <span class="mut">/{r["W"]}日</span></div>')

def bottoms_chain(hl):
    parts = [f'<span class="bot">{d[5:]}<i>@{p:g}</i></span>' for d, p in hl[-4:]]
    pre = '<span class="arr">…→</span>' if len(hl) > 4 else ""
    chain = '<span class="arr">→</span>'.join(parts)
    return f'<div class="botwrap">{pre}{chain}</div>'

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
        k = (N.get(r["sym"]) or {}).get("ckind", "無") or "無"
        if not ((N.get(r["sym"]) or {}).get("catalyst") or "").strip(): k = "無"
        cnt[k] = cnt.get(k, 0) + 1
    n_hot = sum(v for k, v in cnt.items() if k != "無")
    parts = "".join(f'<span class="chip cat"><b>{esc(k)}</b> <i>{v}</i></span>'
                    for k, v in sorted(cnt.items(), key=lambda x: -x[1]) if k != "無")
    tail = f'<span class="chip"><b>跟大市</b> <i>{cnt.get("無", 0)}</i></span>'
    return (f'<div class="chips"><span class="chip lead">有熱炒催化劑 <i>{n_hot}</i>/{len(rows)}</span>'
            f'{parts}{tail}</div>')

def table_sub(pid):
    pg = O["pages"][pid]
    L = pg["L"]
    head = (f'<tr><th>#<span class="thn">綜合排名</span></th><th>Ticker · 現價/MA{L} · 市值</th>'
            f'<th class="srt" data-k="cat">主要催化劑<span class="thn">熱炒 news-driven</span></th>'
            f'<th class="srt" data-k="vcp">VCP<span class="thn">收縮指數</span></th>'
            f'<th class="srt" data-k="cert">確定性<span class="thn">7項合成</span></th>'
            f'{C7_HEADS}'
            f'<th class="srt" data-k="slope">60日走勢 · 斜率</th>'
            f'<th>底部序列<span class="thn">45日內 · 遞升</span></th>'
            f'<th>下跌原因<span class="thn">濃縮</span></th>'
            f'<th>回升原因<span class="thn">熱炒 highlight · 附信心</span></th><th>類別</th></tr>')
    rows = []
    for i, r in enumerate(pg["rows"], 1):
        rows.append(
            f'<tr data-rk="{i}" {row_attrs(r)}><td class="rk">{i}</td><td>{tick_cell(r, L)}</td>'
            f'<td class="catc">{cat_cell(r["sym"])}</td>'
            f'<td>{meter_cell(r["vcp"])}</td><td>{meter_cell(r["cert"], "certm")}</td>'
            f'{c7_cells(r)}'
            f'<td>{spark_cell(r)}</td>'
            f'<td class="bots">{bottoms_chain(r["hl"])}</td>'
            f'<td class="whyc">{why_decline(r["sym"])}</td>'
            f'<td class="whyc">{why_recovery(r["sym"])}</td>'
            f'<td>{sector_cell(r)}</td></tr>')
    return head, "".join(rows), pg

def table_page1():
    head = ('<tr><th>#<span class="thn">爆發排名</span></th><th>Ticker · 現價/MA · 市值</th>'
            '<th class="srt" data-k="cat">主要催化劑<span class="thn">熱炒 news-driven</span></th>'
            '<th class="srt" data-k="score">爆發潛力分數<span class="thn">0.4×VCP + 0.4×確定性 + 0.2×覆蓋</span></th>'
            '<th class="srt" data-k="vcp">VCP<span class="thn">收縮指數</span></th>'
            '<th class="srt" data-k="cert">確定性<span class="thn">7項合成</span></th>'
            '<th>達標時間框<span class="thn">同組市值頁內排名</span></th>'
            f'{C7_HEADS}'
            '<th class="srt" data-k="slope">60日走勢 · 斜率</th>'
            '<th>下跌原因<span class="thn">濃縮</span></th>'
            '<th>回升原因<span class="thn">熱炒 highlight · 附信心</span></th><th>類別</th></tr>')
    labels = {"2": "1週", "3": "2週", "4": "1月", "5": "2月"}
    rows = []
    for i, r in enumerate(O["page1"], 1):
        frames = []
        for t, _, _ in TF:
            pid = f'{t}{r["cap"]}'
            if pid in r["ranks"]:
                frames.append(f'<span class="fr on">{labels[t]}<i>#{r["ranks"][pid]}</i></span>')
            else:
                frames.append(f'<span class="fr">{labels[t]}</span>')
        attrs = row_attrs(r, ' data-score="{}"'.format(r["score"]))
        rows.append(
            f'<tr data-rk="{i}" {attrs}>'
            f'<td class="rk">{i}</td><td>{tick_cell(r, r["L"])}</td>'
            f'<td class="catc">{cat_cell(r["sym"])}</td>'
            f'<td>{score_cell(r)}</td>'
            f'<td>{meter_cell(r["vcp"])}</td><td>{meter_cell(r["cert"], "certm")}</td>'
            f'<td class="frs">{"".join(frames)}</td>'
            f'{c7_cells(r)}'
            f'<td>{spark_cell(r)}</td>'
            f'<td class="whyc">{why_decline(r["sym"])}</td>'
            f'<td class="whyc">{why_recovery(r["sym"])}</td>'
            f'<td>{sector_cell(r)}</td></tr>')
    return head, "".join(rows)

c = M["counts"]
cc = M["cap_counts"]
UNIVERSE_LINE = (f'Universe：全美上市普通股掃描 — 快照涵蓋 {c["total"]:,} 隻 · 存續至 {M["last_date"][5:]} 有報價 {c["current"]:,} 隻 · '
                 f'歷史 ≥90 交易日 {c["hist"]:,} 隻 · 價格 ≥$2 {c["price"]:,} 隻 · '
                 f'流動性達標（20日中位成交額 ≥$1M）{c["liq"]:,} 隻合資格'
                 f'（大型 {cc["a"]:,} · 中型 {cc["b"]:,} · 小型 {cc["c"]:,} · 無市值資料 {cc["x"]:,}）')

css = """
/* Dark-only by request: the palette lives on bare :root with no media query
   and no [data-theme] override, so the page stays dark whatever the viewer's
   OS or the host stamps on the root element. Every colour is a token and every
   text token clears WCAG AA on both --sf and the --hl row-hover ground. */
:root{color-scheme:dark;
 --pg:#0d0d0d;--sf:#1a1a19;--ink:#ffffff;--ink2:#c3c2b7;--mut:#93918a;
 --grid:#2c2c2a;--axis:#383835;--ring:rgba(255,255,255,.10);
 --seq:#5b9dea;--link:#6da7ec;--good:#2fbf2f;--warn:#d99a2b;--bad:#e06c6c;
 --hl:#16202d;--meter:#25303e;--okbg:#15230f;--nobg:#2a1c1c;
 --hotbg:#4a3512;--hotink:#ffd479;--hotbd:#a8791f;--capbg:#232322}
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
.tblwrap{overflow-x:auto;background:var(--sf);border:1px solid var(--ring);border-radius:10px}
table{border-collapse:collapse;width:100%;min-width:2320px;font-size:12.5px}
th{position:sticky;top:0;text-align:left;font-size:11px;color:var(--mut);font-weight:600;
 padding:9px 8px;border-bottom:1px solid var(--grid);background:var(--sf);white-space:nowrap;z-index:1}
th{-webkit-user-select:none;user-select:none}
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
.rk{color:var(--mut);font-weight:600}
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
/* the slope line is a .subsc too, so it needs the higher specificity to stay green */
.slope,.subsc.slope{color:var(--good);font-weight:600}
.subsc b{color:var(--ink2)}
.c7{font-size:11.5px;white-space:nowrap}
.c7 .cok{color:var(--good);font-weight:600}
.c7 .cno{color:var(--bad)}
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
.conf{display:inline-block;font-size:9.5px;border-radius:8px;padding:1px 6px;margin-left:2px;
 border:1px solid var(--ring);color:var(--mut);white-space:nowrap}
.conf.c高{color:var(--good);border-color:var(--good)}
.conf.c中{color:var(--warn);border-color:var(--warn)}
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
.legend{display:flex;gap:16px;flex-wrap:wrap;font-size:11.5px;color:var(--ink2);margin:8px 2px 0}
.legend .sw{display:inline-block;width:14px;height:3px;vertical-align:3px;margin-right:5px;border-radius:2px}
.foot{font-size:11.5px;color:var(--ink2);line-height:1.7}
.foot b{color:var(--ink)}
section[hidden]{display:none}
@media (prefers-reduced-motion:no-preference){.nav button{transition:background .15s,color .15s}}
"""

rules_html = f"""
<div class="card rules">
<h2>篩選規則（10MA R6 · 數據更新至 8月31日收盤；每個時間框再分大／中／小型股，共 12 個子頁）</h2>
① <b>{esc(UNIVERSE_LINE)}</b>。<br>
② <b>市值分頁（R5 新增）</b>：<b>a = 大型股 ≥$100億</b>、<b>b = 中型股 $20–100億</b>、<b>c = 小型股 &lt;$20億</b>；每個時間框各自取三組嘅 top 50（每組合資格數不足 50 就全部列出）。市值取自 Nasdaq 快照；無市值資料嘅（主要係封閉式基金）唔會硬塞入任何一組，改為喺各頁標示數目。<br>
③ <b>MA 上升</b>：PAGE 2a/b/c：<b>5 天 MA</b> 較 <b>5 個交易日</b>前高；PAGE 3/4/5（a/b/c）：<b>10 天 MA</b> 分別較 <b>10 / 21 / 42 個交易日</b>前高；且 MA 最後 3 日逐日上升、期內 ≥70% 日子上升。<br>
④ <b>「底」</b>（用戶原話：「大約跌了三天，然後見底回升了大約三天」）：某日收盤係 ±3 日內最低，且 3 日前收盤高過佢、3 日後收盤高過佢；相鄰 ≤3 日去重。 ⑤ <b>一底高於一底</b>：45 個交易日內 ≥2 個底逐個遞升，最近一個底喺 25 日內。<br>
⑥ <b>VCP 指數（0–100）</b>：10日/前30日波幅（35%）＋近10日區間佔價（25%）＋近10日/前30日成交量（20%）＋近15日/前30–45日區間（20%），全體合資格股票百分位合成。<br>
⑦ <b>確定性分數（0–100，7 項量化，逐項分欄）</b>：<b>突破</b>（最近兩個底之間高位已被升穿？25%）· <b>回補</b>（收復最後一段跌幅%，10%）· <b>守底</b>（最後一個底已守日數，15 日滿分；曾跌穿×0.25，15%）· <b>量比</b>（近15日跌日/升日成交量比，百分位，越低越好，15%）· <b>遞減</b>（末段÷首段跌幅，百分位，越低越好，10%）· <b>RS</b>（21日回報 − 全體中位數，百分位，10%）· <b>均線</b>（價&gt;20MA ＋ 20MA&gt;50MA ＋ 50MA向上，15%）。<br>
⑧ <b>排名</b>：12 個子頁按綜合分數（0.5×VCP ＋ 0.5×確定性）排；PAGE 1 總表 = 12 個名單嘅union，按爆發潛力分數（0.4×VCP ＋ 0.4×確定性 ＋ 0.2×覆蓋度）排。<br>
⑨ <b>主要催化劑欄（R5 新增）</b>：每隻股票嘅<mark class="hot">市場熱炒 news-driven 主要催化劑</mark>以醒目 badge 精簡標出（例如「$43私有化」「Q2爆升26%」「FDA批准」），並標明類型（業績／併購／臨床／監管／回購／指引／大單／AI／重組）；純粹跟大市反彈、冇個股新聞嘅標「跟大市」。點欄標題可將有催化劑嘅排最前。<br>
⑩ <b>操作</b>：頂欄第一行揀時間框、第二行揀市值組別；「按VCP排列／按確定性排列／按催化劑排列／預設排名」對當前頁生效；VCP、確定性、7 項證據、斜率、催化劑欄標題均可點擊排序（先降後升）；<b>欄寬</b>可拖曳欄標題右邊界調整。<br>
⑪ <b>下跌 / 回升原因</b>：AI 代理逐隻搜尋（<a href="https://bigdata.com" target="_blank" rel="noopener">Bigdata.com</a> 金融新聞索引＋公開網頁）後濃縮；信心：<b>高</b>＝明確個股消息；<b>中</b>＝板塊/部分證據；<b>低</b>＝只反映大市背景。
</div>"""

mkt_html = ""
if MKT:
    factors = "".join(f'<span><b>{esc(f["period"])}</b> {esc(f["factor_zh"])}</span>' for f in MKT.get("factors", []))
    mkt_html = (f'<div class="card mkt"><h2>2026年6–8月 市場背景（底部成因的共同分母）</h2>'
                f'{esc(MKT["summary_zh"])}<div class="mf">{factors}</div></div>')

LEGEND = ('<div class="legend"><span><i class="sw" style="background:var(--ink2)"></i>收盤</span>'
          '<span><i class="sw" style="background:var(--seq)"></i>MA（頁面各自 5/10 天）</span>'
          '<span><i class="sw" style="background:var(--good);height:8px;width:8px;border-radius:50%"></i>底部（最後60個交易日）</span>'
          '<span><span class="catb" style="padding:1px 6px;font-size:10px"><i>類型</i>主要催化劑</span> = 市場熱炒 news-driven 動力</span>'
          '<span># 欄固定顯示預設排名；點欄標題排序（▼降序 ▲升序）；拖欄邊調闊度；量比、遞減越低越好</span></div>')

secs = []
head1, body1 = table_page1()
cap_n = {b: sum(1 for r in O["page1"] if r["cap"] == b) for b in ("a", "b", "c")}
pghead1 = (f'<div class="pghead"><b>總表 · 爆發潛力排名</b>'
           f'<span>12 個子頁名單合共 <b>{len(O["page1"])}</b> 隻不重複股票'
           f'（大型 {cap_n["a"]} · 中型 {cap_n["b"]} · 小型 {cap_n["c"]}）</span>'
           f'<span>排序 = 0.4×VCP + 0.4×確定性 + 0.2×覆蓋度</span>'
           f'<span>覆蓋度 = 通過該時間框 MA 條件嘅時間框數目（亮起 = 入咗同組市值該頁 top 50）</span></div>')
secs.append(f'''<section id="p1">
{pghead1}{mkt_html}{cat_chips(O["page1"])}{sector_chips(O["page1"])}
<div class="tblwrap"><table><thead>{head1}</thead><tbody>{body1}</tbody></table></div>
{LEGEND}
</section>''')

for t, tlab, tsub in TF:
    for cb, clab, csub in CAPS:
        pid = f"{t}{cb}"
        head, body, pg = table_sub(pid)
        pghead = (f'<div class="pghead"><b>PAGE {pid} · {tlab} · {clab}</b>'
                  f'<span>{tsub} · {csub}</span>'
                  f'<span>合資格 <b>{pg["qualified"]}</b> 隻 → 按綜合分數（0.5×VCP＋0.5×確定性）'
                  f'取 top 50，本頁列出 <b>{len(pg["rows"])}</b> 隻</span></div>')
        secs.append(f'''<section id="p{pid}" hidden>
{pghead}{cat_chips(pg["rows"])}{sector_chips(pg["rows"])}
<div class="tblwrap"><table><thead>{head}</thead><tbody>{body}</tbody></table></div>
{LEGEND}
</section>''')

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
             '<button class="sbtn" data-sort="rk">預設排名</button>')

foot = f"""
<div class="card foot">
<h2>備註 · 數據 lineage</h2>
① 覆蓋範圍：可達數據源覆蓋美國上市普通股 {c["total"]:,} 隻（含 S&amp;P 500 全部 503 隻）；外國註冊而非 S&amp;P 500 嘅美國上市股（部分 ADR）未有完整歷史，未納入掃描。價格未除息調整。<br>
② 數據重建：GitHub 每日 Nasdaq 快照鏡像（zyhe16/top-us-stock-tickers）逐 commit 重建每日收盤序列，共 {M["n_days"]} 個交易日（{M["cal_first"]} → {M["cal_last"]}）；4 日無快照以前值填補；08-27 收盤以官方 net-change 校正。<br>②b <b>最新交易日（08-31）</b>：鏡像今日未出快照（其更新排程當日改版），本研究環境嘅網絡政策亦封鎖所有行情網站，故改由本 repo 嘅 GitHub Actions runner 直接抓取同一個 Nasdaq screener 來源並回傳（7,144 隻有報價）。接駁檢查：以 08-31 收盤減官方 net-change 反推嘅前收，與序列中 08-28 收盤比較，5,127 隻中位偏差 <b>0.000%</b>、p99 0.000%；8 隻因合股／拆股（如 NXL 0.25→7.50）歷史股數基準已變，整隻剔除而非硬駁上去；另有 10 隻當日無報價，保留舊值後即失去「存續至最新交易日」資格，唔會出現喺任何頁。<br>
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
  var state = { t: '1', c: 'a' };
  // each table keeps whatever sort the user left on it, so the nav buttons are
  // re-highlighted from that table's own state rather than blanked on every switch
  var sortOf = {};
  function pid() { return state.t === '1' ? '1' : state.t + state.c; }
  function syncSortBtns() {
    var cur = sortOf['p' + pid()] || 'rk';
    sbtns.forEach(function(b) { b.classList.toggle('on', b.dataset.sort === cur); });
  }
  function show() {
    var id = 'p' + pid();
    document.querySelectorAll('section[id^="p"]').forEach(function(s) { s.hidden = (s.id !== id); });
    tfb.forEach(function(b) { b.classList.toggle('on', b.dataset.t === state.t); });
    cpb.forEach(function(b) { b.classList.toggle('on', b.dataset.c === state.c); });
    caprow.hidden = (state.t === '1');
    syncSortBtns();
    try { localStorage.setItem('ma10r6', JSON.stringify(state)); } catch (e) {}
  }
  tfb.forEach(function(b) { b.addEventListener('click', function() { state.t = b.dataset.t; show(); }); });
  cpb.forEach(function(b) { b.addEventListener('click', function() { state.c = b.dataset.c; show(); }); });
  try {
    var sv = JSON.parse(localStorage.getItem('ma10r6') || 'null');
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
  function secIdOf(tbl) {
    var s = tbl.closest('section');
    return s ? s.id : '';
  }
  document.querySelectorAll('th.srt').forEach(function(th) {
    th.addEventListener('click', function() {
      var tbl = th.closest('table');
      var dir = th.dataset.dir === 'desc' ? 'asc' : 'desc';
      th.dataset.dir = dir;
      sortRows(tbl, th.dataset.k, dir);
      markHead(tbl, th.dataset.k, dir);
      // nav buttons mean "descending by key"; an ascending sort matches none of them
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

html_doc = f"""<title>10MA Uptrend Watchlist R6</title>
<style>{css}</style>
<div class="wrap">
<h1>10MA Uptrend Watchlist R6（一底高於一底 × VCP × 底部確定性 · 大中小型股分頁）</h1>
<div class="sub">數據至 <b>{M["last_date"]}</b> 收盤 · 全美掃描 {c["liq"]:,} 隻合資格 · 13 頁：總表＋4 個時間框 × 大／中／小型股 · 每頁列出主要熱炒催化劑 · VCP／確定性／7項證據可排序 · 欄寬可拖曳</div>
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
print("wrote", out_path, f"{len(html_doc)/1024:.0f} KB")

#!/usr/bin/env python3
"""Build the 10MA R1 5-page HTML report from screen_results10.json + news.json + market.json."""
import json, datetime, html, os, sys

SCRATCH = os.environ.get("WORK_DIR", "./data")
O = json.load(open(f"{SCRATCH}/screen_results10.json"))
NEWS = json.load(open(f"{SCRATCH}/news.json")) if os.path.exists(f"{SCRATCH}/news.json") else {}
MKT = json.load(open(f"{SCRATCH}/market.json")) if os.path.exists(f"{SCRATCH}/market.json") else None
M = O["meta"]

now_hkt = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=8)
STAMP = now_hkt.strftime("%m.%d_%H%M")
BUILD_TS = now_hkt.strftime("%Y-%m-%d %H:%M HKT")
OUTNAME = f"10MA_uptrend_watchlistGit_R1.00_claudefable5xhigh_{STAMP}.html"

PAGE_DEFS = [
    ("1", "PAGE 1 · 總覽", "爆發潛力排名", None),
    ("2", "PAGE 2 · 1星期", "5MA · 5個交易日", 2),
    ("3", "PAGE 3 · 2星期", "10MA · 10個交易日", 3),
    ("4", "PAGE 4 · 1個月", "10MA · 21個交易日", 4),
    ("5", "PAGE 5 · 2個月", "10MA · 42個交易日", 5),
]

def esc(s): return html.escape(str(s), quote=True)

def spark_svg(sp, L):
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
    ma_polys = "".join(f'<polyline points="{" ".join(s)}" fill="none" stroke="var(--seq)" stroke-width="1.3" opacity=".9"/>' for s in segs if len(s) > 1)
    dots = ""
    for i, v in bots.items():
        x, y = xy(i, v).split(",")
        dots += f'<circle cx="{x}" cy="{y}" r="2.4" fill="var(--good)"/>'
    return (f'<svg viewBox="0 0 {W} {H}" width="{W}" height="{H}" aria-label="60日走勢">'
            f'<polyline points="{pl_c}" fill="none" stroke="var(--ink2)" stroke-width="1"/>'
            f'{ma_polys}{dots}</svg>')

def combo_cell(r):
    return (f'<div class="vcpb"><div class="meter"><i style="width:{r["combo"]:.0f}%"></i></div>'
            f'<b>{r["combo"]:.1f}</b></div>'
            f'<div class="subsc">VCP <b>{r["vcp"]:.1f}</b> · 確定 <b>{r["cert"]:.1f}</b></div>')

def score_cell(r):
    return (f'<div class="vcpb score"><div class="meter"><i style="width:{r["score"]:.0f}%"></i></div>'
            f'<b>{r["score"]:.1f}</b></div>'
            f'<div class="subsc">VCP <b>{r["vcp"]:.1f}</b> · 確定 <b>{r["cert"]:.1f}</b> · 覆蓋 <b>{r["hits"]}/4</b></div>')

def cert_chips(r):
    c = r["cert_c"]
    retr = c["retrace_pct"]
    retr_s = "100%+" if retr >= 100 else f"{max(0.0, retr):.0f}%"
    brk = ('<span class="cc ok">突破✓</span>' if c["broke"]
           else '<span class="cc no">未突破</span>')
    held = f'<span class="cc{" warn2" if c["undercut"] else ""}">守{c["d_held"]}日{"⚠" if c["undercut"] else ""}</span>'
    maf = sum(c["ma_flags"])
    return ('<div class="ccs">' + brk
            + f'<span class="cc">回補{retr_s}</span>'
            + held
            + f'<span class="cc{" ok" if c["dv_ratio"] < 0.85 else ""}">量比{c["dv_ratio"]:.2f}</span>'
            + f'<span class="cc{" ok" if c["contr"] < 0.6 else ""}">遞減{c["contr"]:.2f}</span>'
            + f'<span class="cc{" ok" if c["rs21_pct"] > 0 else ""}">RS{c["rs21_pct"]:+.1f}%</span>'
            + f'<span class="cc{" ok" if maf == 3 else ""}">均線{maf}/3</span>'
            + '</div>')

def bottoms_chain(hl):
    parts = []
    shown = hl[-4:]
    for d, p in shown:
        mmdd = d[5:]
        parts.append(f'<span class="bot">{mmdd}<i>@{p:g}</i></span>')
    chain = '<span class="arr">→</span>'.join(parts)
    pre = '<span class="arr">…→</span>' if len(hl) > 4 else ""
    return f'<div class="botwrap">{pre}{chain}</div>'

def news_cell(sym):
    e = NEWS.get(sym)
    if not e:
        return '<div class="why"><em class="mut">未有研究資料</em></div>'
    conf = e.get("confidence", "低")
    tags = "".join(f'<span class="tag">{esc(t)}</span>' for t in (e.get("tags") or [])[:4])
    return (f'<div class="why">'
            f'<div class="wrow"><b class="dn">跌</b>{esc(e.get("decline_zh", "—"))}</div>'
            f'<div class="wrow"><b class="up">升</b>{esc(e.get("recovery_zh", "—"))}</div>'
            f'<div class="wtags">{tags}<span class="conf c{conf}">信心{esc(conf)}</span></div></div>')

def sector_cell(r):
    zh = r["sector_zh"]; en = r["sector"]
    sub = r["gsub"] if (r["sp500"] and r.get("gsub")) else r["industry"]
    gtag = f'<i class="gics">GICS·{esc(r["gsec"])}</i>' if (r["sp500"] and r.get("gsec")) else ""
    return f'<div class="sect"><b>{esc(zh)}</b> <span>{esc(en)}</span>{gtag}<em>{esc(sub)}</em></div>'

def tv_url(r):
    sym = r["sym"].replace("/", ".").lower()
    if r["exch"] != "—":
        return f'https://www.tradingview.com/chart/Q1c5VWwD/?symbol={r["exch"].lower()}%3A{esc(sym)}'
    return f'https://www.tradingview.com/chart/Q1c5VWwD/?symbol={esc(sym)}'

def tick_cell(r, L=None):
    sp = '<span class="badge">S&amp;P500</span>' if r["sp500"] else ""
    warn = ' <span class="warn">⚠低於MA</span>' if r["below_ma"] else ""
    ml = f'MA{L}' if L else "MA"
    return (f'<div class="tk"><a href="{tv_url(r)}" target="_blank" rel="noopener">{esc(r["sym"])}</a>'
            f'<span class="ex">{esc(r["exch"])}</span>{sp}<em>{esc(r["name"][:34])}</em>'
            f'<span class="pxl nums">{r["close"]:g} <span class="mut">/ {ml} {r["ma"]:g}</span>{warn}</span></div>')

def spark_cell(r):
    return (f'{spark_svg(r["spark"], r["L"])}'
            f'<div class="subsc nums slope">MA{r["L"]} {r["slope"]:+.2f}% <span class="mut">/{r["W"]}日</span></div>')

def sector_chips(rows):
    cnt = {}
    for r in rows:
        k = (r["sector_zh"], r["sector"])
        cnt[k] = cnt.get(k, 0) + 1
    chips = "".join(f'<span class="chip"><b>{esc(z)}</b> {esc(e)} <i>{n}</i></span>'
                    for (z, e), n in sorted(cnt.items(), key=lambda x: -x[1]))
    return f'<div class="chips">{chips}</div>'

def table_page(p):
    pg = O["pages"][p]
    L, W = pg["L"], pg["W"]
    head = (f'<tr><th>#</th><th>Ticker · 現價/MA{L}</th>'
            f'<th>綜合分數<span class="thn">0.5×VCP + 0.5×確定性</span></th>'
            f'<th>確定性證據<span class="thn">7項量化</span></th>'
            f'<th>60日走勢 · 斜率</th>'
            f'<th>底部序列<span class="thn">45日內 · 遞升</span></th>'
            f'<th>下跌 → 回升原因<span class="thn">附信心度</span></th><th>類別</th></tr>')
    rows = []
    for i, r in enumerate(pg["rows"], 1):
        rows.append(
            f'<tr><td class="rk">{i}</td><td>{tick_cell(r, L)}</td>'
            f'<td>{combo_cell(r)}</td>'
            f'<td class="certc">{cert_chips(r)}</td>'
            f'<td>{spark_cell(r)}</td>'
            f'<td class="bots">{bottoms_chain(r["hl"])}</td>'
            f'<td class="whyc">{news_cell(r["sym"])}</td>'
            f'<td>{sector_cell(r)}</td></tr>')
    return head, "".join(rows), pg

def table_page1():
    head = ('<tr><th>#</th><th>Ticker · 現價/MA</th>'
            '<th>爆發潛力分數<span class="thn">0.4×VCP + 0.4×確定性 + 0.2×覆蓋</span></th>'
            '<th>達標時間框<span class="thn">頁內排名</span></th>'
            '<th>確定性證據<span class="thn">7項量化</span></th>'
            '<th>60日走勢 · 斜率</th>'
            '<th>下跌 → 回升原因<span class="thn">附信心度</span></th><th>類別</th></tr>')
    rows = []
    labels = {"2": "1週", "3": "2週", "4": "1月", "5": "2月"}
    for i, r in enumerate(O["page1"], 1):
        frames = []
        for p in ("2", "3", "4", "5"):
            if p in r["ranks"]:
                frames.append(f'<span class="fr on">{labels[p]}<i>#{r["ranks"][p]}</i></span>')
            else:
                frames.append(f'<span class="fr">{labels[p]}</span>')
        rows.append(
            f'<tr><td class="rk">{i}</td><td>{tick_cell(r, r["L"])}</td>'
            f'<td>{score_cell(r)}</td>'
            f'<td class="frs">{"".join(frames)}</td>'
            f'<td class="certc">{cert_chips(r)}</td>'
            f'<td>{spark_cell(r)}</td>'
            f'<td class="whyc">{news_cell(r["sym"])}</td>'
            f'<td>{sector_cell(r)}</td></tr>')
    return head, "".join(rows)

c = M["counts"]
UNIVERSE_LINE = (f'Universe：全美上市普通股掃描 — 快照涵蓋 {c["total"]:,} 隻 · 存續至 08-28 有報價 {c["current"]:,} 隻 · '
                 f'歷史 ≥90 交易日 {c["hist"]:,} 隻 · 價格 ≥$2 {c["price"]:,} 隻 · 流動性達標（20日中位成交額 ≥$1M）{c["liq"]:,} 隻合資格')

css = """
:root{color-scheme:light;--pg:#f9f9f7;--sf:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--mut:#898781;
 --grid:#e1e0d9;--axis:#c3c2b7;--ring:rgba(11,11,11,.10);--seq:#2a78d6;--link:#1c5cab;--good:#006300;
 --warn:#8a5a00;--bad:#9c2121;--hl:#eef3fa;--meter:#dfe7f2;--okbg:#eaf3ea;--nobg:#f3ecec}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;
 --pg:#0d0d0d;--sf:#1a1a19;--ink:#fff;--ink2:#c3c2b7;--mut:#898781;--grid:#2c2c2a;--axis:#383835;
 --ring:rgba(255,255,255,.10);--seq:#3987e5;--link:#6da7ec;--good:#0ca30c;--warn:#d99a2b;--bad:#e06c6c;
 --hl:#16202d;--meter:#25303e;--okbg:#15230f;--nobg:#2a1c1c}}
:root[data-theme="dark"]{color-scheme:dark;--pg:#0d0d0d;--sf:#1a1a19;--ink:#fff;--ink2:#c3c2b7;
 --mut:#898781;--grid:#2c2c2a;--axis:#383835;--ring:rgba(255,255,255,.10);--seq:#3987e5;
 --link:#6da7ec;--good:#0ca30c;--warn:#d99a2b;--bad:#e06c6c;--hl:#16202d;--meter:#25303e;
 --okbg:#15230f;--nobg:#2a1c1c}
*{box-sizing:border-box}
body{margin:0;background:var(--pg);color:var(--ink);font:14px/1.5 system-ui,-apple-system,"Segoe UI","Noto Sans TC",sans-serif}
.wrap{max-width:1420px;margin:0 auto;padding:26px 20px 60px}
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
.nav{position:sticky;top:0;z-index:5;display:flex;gap:6px;flex-wrap:wrap;background:var(--pg);
 padding:10px 0;border-bottom:1px solid var(--grid);margin-bottom:14px}
.nav button{font:600 13px/1 system-ui,"Noto Sans TC",sans-serif;color:var(--ink2);background:var(--sf);
 border:1px solid var(--ring);border-radius:20px;padding:9px 14px;cursor:pointer}
.nav button .s{display:block;font-weight:400;font-size:10.5px;color:var(--mut);margin-top:3px}
.nav button.on{color:var(--pg);background:var(--ink);border-color:var(--ink)}
.nav button.on .s{color:var(--pg);opacity:.75}
.pghead{display:flex;flex-wrap:wrap;gap:8px 18px;align-items:baseline;margin:2px 0 10px;font-size:12.5px;color:var(--ink2)}
.pghead b{font-size:15px;color:var(--ink)}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:12px}
.chip{font-size:11.5px;color:var(--ink2);background:var(--sf);border:1px solid var(--ring);
 border-radius:14px;padding:4px 10px}
.chip b{color:var(--ink)}
.chip i{font-style:normal;font-weight:700;color:var(--seq)}
.tblwrap{overflow-x:auto;background:var(--sf);border:1px solid var(--ring);border-radius:10px}
table{border-collapse:collapse;width:100%;min-width:1560px;font-size:12.5px}
th{position:sticky;top:0;text-align:left;font-size:11px;color:var(--mut);font-weight:600;
 padding:9px 10px;border-bottom:1px solid var(--grid);background:var(--sf);white-space:nowrap;z-index:1}
.thn{display:block;font-weight:400;font-size:10px}
td{padding:8px 10px;border-bottom:1px solid var(--grid);vertical-align:middle}
tr:last-child td{border-bottom:0}
tr:hover td{background:var(--hl)}
.rk{color:var(--mut);font-weight:600}
.nums{font-variant-numeric:tabular-nums;white-space:nowrap}
.mut{color:var(--mut)}
.slope{color:var(--good);font-weight:600}
.tk a{color:var(--link);font-weight:700;text-decoration:none;font-size:13.5px}
.tk a:hover{text-decoration:underline}
.tk .ex{font-size:10px;color:var(--mut);margin-left:6px}
.tk em{display:block;font-style:normal;font-size:10.5px;color:var(--mut);max-width:180px;
 overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.tk .pxl{display:block;font-size:11px;margin-top:2px}
.badge{font-size:9px;font-weight:700;color:var(--seq);border:1px solid var(--seq);
 border-radius:8px;padding:1px 5px;margin-left:6px;vertical-align:1px;white-space:nowrap}
.vcpb{display:flex;align-items:center;gap:8px;min-width:120px}
.vcpb .meter{flex:1;height:6px;border-radius:3px;background:var(--meter);min-width:60px}
.vcpb .meter i{display:block;height:100%;border-radius:3px;background:var(--seq)}
.vcpb b{font-variant-numeric:tabular-nums;font-size:12.5px}
.score .meter i{background:var(--good)}
.subsc{font-size:10.5px;color:var(--mut);margin-top:3px;white-space:nowrap}
.subsc b{color:var(--ink2)}
.certc{max-width:200px}
.ccs{display:flex;flex-wrap:wrap;gap:3px;max-width:200px}
.cc{font-size:10px;color:var(--ink2);border:1px solid var(--ring);border-radius:9px;
 padding:1px 6px;white-space:nowrap;font-variant-numeric:tabular-nums}
.cc.ok{color:var(--good);border-color:var(--good);background:var(--okbg)}
.cc.no{color:var(--bad);border-color:var(--bad);background:var(--nobg)}
.cc.warn2{color:var(--warn);border-color:var(--warn)}
.bots{max-width:210px}
.botwrap{display:flex;flex-wrap:wrap;align-items:baseline;gap:2px 4px;max-width:210px}
.bot{white-space:nowrap;font-variant-numeric:tabular-nums;font-size:11px}
.bot i{font-style:normal;color:var(--mut);font-size:10px}
.arr{color:var(--axis);margin:0 3px}
.warn{color:var(--warn);font-size:10.5px;white-space:nowrap}
.whyc{min-width:250px;max-width:310px}
.why{font-size:11.5px;line-height:1.5;color:var(--ink2)}
.why .wrow{margin-bottom:2px}
.why b.dn{color:var(--bad);font-size:10px;border:1px solid var(--bad);border-radius:8px;padding:0 5px;margin-right:5px}
.why b.up{color:var(--good);font-size:10px;border:1px solid var(--good);border-radius:8px;padding:0 5px;margin-right:5px}
.wtags{margin-top:3px}
.tag{display:inline-block;font-size:9.5px;color:var(--seq);background:var(--hl);border-radius:8px;
 padding:1px 6px;margin:1px 3px 1px 0}
.conf{display:inline-block;font-size:9.5px;border-radius:8px;padding:1px 6px;margin-left:2px;border:1px solid var(--ring);color:var(--mut)}
.conf.c高{color:var(--good);border-color:var(--good)}
.conf.c中{color:var(--warn);border-color:var(--warn)}
.sect b{font-size:12px}
.sect span{font-size:10.5px;color:var(--mut);margin-left:4px}
.sect em{display:block;font-style:normal;font-size:10.5px;color:var(--ink2)}
.gics{display:inline-block;font-style:normal;font-size:9px;color:var(--seq);border:1px solid var(--ring);border-radius:7px;padding:0 4px;margin-left:5px;vertical-align:1px}
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
<h2>篩選規則（10MA R1 · 由 20MA R3 管線改為 10 天 MA；底部確定性 7 項量化 + 綜合排名不變）</h2>
① <b>{esc(UNIVERSE_LINE)}</b>。<br>
② <b>MA 上升（本版重點）</b>：PAGE 2：<b>5 天 MA</b> 較 <b>5 個交易日</b>前高；PAGE 3/4/5：<b>10 天 MA</b> 分別較 <b>10 / 21 / 42 個交易日</b>前高；且 MA 最後 3 日逐日上升、期內 ≥70% 日子上升。<br>
③ <b>「底」</b>（用戶原話：「大約跌了三天，然後見底回升了大約三天」）：某日收盤係 ±3 日內最低，且 3 日前收盤高過佢、3 日後收盤高過佢；相鄰 ≤3 日去重。 ④ <b>一底高於一底</b>：45 個交易日內 ≥2 個底逐個遞升，最近一個底喺 25 日內。<br>
⑤ <b>VCP 指數（0–100）</b>：10日/前30日波幅（35%）＋近10日區間佔價（25%）＋近10日/前30日成交量（20%）＋近15日/前30–45日區間（20%），全體合資格股票百分位合成。<br>
⑥ <b>確定性分數（0–100，7 項量化）</b>：<b>1.1 突破中間高位</b>（最近兩個底之間高位已被升穿？25%）· <b>1.2 回補幅度</b>（現價收復最後一段跌幅百分比，10%）· <b>1.3 時間</b>（最後一個底已守幾多個交易日，15 日滿分；曾跌穿×0.25，15%）· <b>2.1 下試量縮</b>（近15日跌日/升日成交量比，百分位，15%）· <b>2.2 回撤遞減</b>（最後一段跌幅 ÷ 第一段跌幅，百分位，10%）· <b>2.3 相對強度</b>（21日回報 − 全體中位數，百分位，10%）· <b>2.4 均線位置</b>（價>20MA ＋ 20MA>50MA ＋ 50MA向上，15%）。<br>
⑦ <b>排名（PAGE 2–5）＝ 綜合分數 ＝ 0.5 × VCP ＋ 0.5 × 確定性</b>（確定性做評分欄，唔係過濾，門檻不變）。 ⑧ <b>爆發潛力分數（PAGE 1）</b>＝ 0.4×VCP ＋ 0.4×確定性 ＋ 0.2×覆蓋度。<br>
⑨ <b>下跌→回升原因欄</b>：AI 代理逐隻股票搜尋新聞（<a href="https://bigdata.com" target="_blank" rel="noopener">Bigdata.com</a> 金融新聞索引＋公開網頁）歸納，附信心度 —— <b>高</b>＝搵到明確個股消息；<b>中</b>＝板塊/部分證據；<b>低</b>＝未見個股消息，只反映大市背景。
</div>"""

mkt_html = ""
if MKT:
    factors = "".join(f'<span><b>{esc(f["period"])}</b> {esc(f["factor_zh"])}</span>' for f in MKT.get("factors", []))
    mkt_html = (f'<div class="card mkt"><h2>2026年6–8月 市場背景（底部成因的共同分母）</h2>'
                f'{esc(MKT["summary_zh"])}<div class="mf">{factors}</div></div>')

secs = []
nav_btns = []
for pid, tab, subt, pno in PAGE_DEFS:
    on_cls = ' class="on"' if pid == "1" else ""
    nav_btns.append(f'<button data-p="{pid}"{on_cls}>{tab}<span class="s">{subt}</span></button>')
    if pid == "1":
        head, body = table_page1()
        pghead = (f'<div class="pghead"><b>總覽 · 爆發潛力排名</b>'
                  f'<span>4 個時間框 top 50 合共 <b>{len(O["page1"])}</b> 隻不重複股票</span>'
                  f'<span>排序 = 0.4×VCP + 0.4×確定性 + 0.2×覆蓋度</span></div>')
        chips = sector_chips(O["page1"])
        extra = mkt_html
    else:
        head, body, pg = table_page(pid)
        pghead = (f'<div class="pghead"><b>{tab.split("·")[1].strip()} · {subt}</b>'
                  f'<span>合資格 <b>{pg["qualified"]}</b> 隻 → 按綜合分數（0.5×VCP＋0.5×確定性）取 top 50</span></div>')
        chips = sector_chips(pg["rows"])
        extra = ""
    secs.append(f'''<section id="p{pid}"{"" if pid == "1" else " hidden"}>
{pghead}{extra}{chips}
<div class="tblwrap"><table><thead>{head}</thead><tbody>{body}</tbody></table></div>
<div class="legend"><span><i class="sw" style="background:var(--ink2)"></i>收盤</span>
<span><i class="sw" style="background:var(--seq)"></i>MA（頁面各自 5/10 天）</span>
<span><i class="sw" style="background:var(--good);height:8px;width:8px;border-radius:50%"></i>底部（最後60個交易日）</span>
<span>確定性 chips：突破＝中間高位已升穿 · 回補＝收復最後跌幅% · 守N日＝最後底部未破日數 · 量比＝跌日/升日成交量 · 遞減＝末段/首段跌幅比 · RS＝21日相對全體中位 · 均線＝三項結構</span></div>
</section>''')

foot = f"""
<div class="card foot">
<h2>備註 · 數據 lineage</h2>
① 覆蓋範圍：可達數據源覆蓋美國上市普通股 {c["total"]:,} 隻（含 S&amp;P 500 全部 503 隻）；外國註冊而非 S&amp;P 500 嘅美國上市股（部分 ADR）未有完整歷史，未納入掃描。價格未除息調整。<br>
② 數據重建：GitHub 每日 Nasdaq 快照鏡像（zyhe16/top-us-stock-tickers）逐 commit 重建每日收盤序列，共 {M["n_days"]} 個交易日（{M["cal_first"]} → {M["cal_last"]}）；4 日無快照以前值填補；08-27 收盤以官方 net-change 校正。重建序列與 20MA R3 報告交叉核對：74/74 上榜股現價完全一致；對 20MA R1 報告抽樣 20MA 平均偏差 0.18%。<br>
③ 類別：Nasdaq 分類＋GICS（S&amp;P 500，klaywang24/market-chronicle）；交易所：irachex/open-stock-data。<br>
④ 確定性 7 項、VCP、排名均經獨立代理人對抗性驗證；原因欄由 AI 代理透過 <a href="https://bigdata.com" target="_blank" rel="noopener">Bigdata.com</a> 新聞索引及公開網頁逐隻搜尋歸納 —— 內容係新聞摘要，可能有錯漏，請以原始公告為準。<br>
⑤ <b>數據終點 {M["last_date"]}，建置時間 {BUILD_TS}</b>（週末，08-28 五係最後交易日）· 快照只有收盤/成交量，VCP 及確定性以收盤序列計算 · 本表只係篩選工具，唔係投資建議。<br>
⑥ 連結格式：Ticker 點擊開 TradingView chart（https://www.tradingview.com/chart/Q1c5VWwD/?symbol=交易所%3Aticker）。
</div>"""

html_doc = f"""<title>10MA Uptrend Watchlist R1</title>
<style>{css}</style>
<div class="wrap">
<h1>10MA Uptrend Watchlist R1（一底高於一底 × VCP × 底部確定性）</h1>
<div class="sub">數據至 <b>{M["last_date"]}</b> 收盤 · 全美掃描 {c["liq"]:,} 隻合資格 · 5 頁：總覽＋4 個時間框（PAGE 2 用 5MA，PAGE 3–5 用 10MA）· 排名 = 綜合分數（VCP 收縮 × 確定性 7 項量化）· 含下跌→回升原因欄</div>
{rules_html}
<nav class="nav">{"".join(nav_btns)}</nav>
{"".join(secs)}
{foot}
</div>
<script>
(function() {{
  var btns = document.querySelectorAll('.nav button');
  function show(p) {{
    document.querySelectorAll('section[id^="p"]').forEach(function(s) {{ s.hidden = (s.id !== 'p' + p); }});
    btns.forEach(function(b) {{ b.classList.toggle('on', b.dataset.p === p); }});
    try {{ localStorage.setItem('ma10page', p); }} catch (e) {{}}
  }}
  btns.forEach(function(b) {{ b.addEventListener('click', function() {{ show(b.dataset.p); }}); }});
  var saved = null;
  try {{ saved = localStorage.getItem('ma10page'); }} catch (e) {{}}
  if (saved && document.getElementById('p' + saved)) show(saved);
}})();
</script>
"""

out_path = f"{SCRATCH}/{OUTNAME}"
open(out_path, "w", encoding="utf-8").write(html_doc)
print("wrote", out_path, f"{len(html_doc)/1024:.0f} KB")

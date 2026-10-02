"""Charts for the macro-regime study, from data/macro_regimes.json:
  reports/macro/01_four_forces.png   four forces (liquidity, politics, technology, shocks) + real S&P, 1960-2026
  reports/macro/02_analogues.png     the analogue episodes around their anchor month vs 2026
  reports/macro/03_sectors.png       what led and lagged in each episode (excess return vs S&P)
  reports/macro/04_similarity.png    distance of every month since 1962 to 2026-10 on the regime features"""
import json, os, sys
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt, matplotlib.dates as mdates
from matplotlib.patches import Patch
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import macro_events as E
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = f"{REPO}/reports/macro"; os.makedirs(OUT, exist_ok=True)
plt.rcParams["font.family"] = ["WenQuanYi Zen Hei", "DejaVu Sans"]; plt.rcParams["axes.unicode_minus"] = False
J = json.load(open(f"{REPO}/data/macro_regimes.json"))
M = pd.to_datetime(J["months"]) + pd.offsets.MonthEnd(0)
F = pd.DataFrame({k: v for k, v in J["frame"].items()}, index=M).astype(float)
pm = lambda s: pd.Period(s, "M").to_timestamp("M")
NOW = pm(J["now_month"])
C = dict(hike="#d62728", cut="#2ca02c", rec="#bbbbbb", R="#f4b6b6", D="#b6c8f4", wave="#ffe8a8", bust="#d9d9d9", bear="#f0c0c0", oil="#8c564b", now="#111111")

def shade(ax, spans, color, alpha=0.35, zorder=0):
    for a, b in spans:
        ax.axvspan(pm(a), pm(b) if b else NOW, color=color, alpha=alpha, lw=0, zorder=zorder)

def four_forces():
    x0, x1 = pm("1960-01"), pm("2029-06")
    fig, axs = plt.subplots(5, 1, figsize=(18, 16), sharex=True, gridspec_kw=dict(height_ratios=[2.2, 0.9, 1.8, 2.0, 2.4], hspace=0.08))
    rec = [(a, b) for a, b in E.RECESSIONS]
    for ax in axs: shade(ax, rec, C["rec"], 0.5); ax.grid(axis="y", alpha=0.25); ax.set_xlim(x0, x1)
    # 1 liquidity
    ax = axs[0]
    shade(ax, [(a, b) for a, b, *_ in E.HIKE_CYCLES], C["hike"], 0.18, 1); shade(ax, E.CUT_CYCLES, C["cut"], 0.15, 1)
    ax.plot(F.index, F["irx"], color="#d62728", lw=1.3, label="3 個月國庫券息（政策利率代理）")
    ax.plot(F.index, F["y10"], color="#1f77b4", lw=1.3, label="10 年期美債息")
    ax.plot(F.index, F["cpi_yoy"], color="#ff7f0e", lw=1.0, ls="--", label="CPI 按年")
    ax.set_ylabel("%"); ax.set_ylim(-2, 20)
    for a, b, r0, r1, lab in E.HIKE_CYCLES:
        ax.text(pm(a), 18.6, lab, fontsize=7.5, rotation=90, va="top", ha="right", color="#8b0000")
    ax.legend(loc="upper right", fontsize=9, ncol=3, framealpha=0.9,
              handles=ax.get_legend_handles_labels()[0] + [Patch(color=C["hike"], alpha=0.4, label="加息周期"), Patch(color=C["cut"], alpha=0.4, label="減息周期"), Patch(color=C["rec"], alpha=0.6, label="NBER 衰退")])
    ax.set_title("① 宏觀流動性（息口）", loc="left", fontsize=12, fontweight="bold")
    # 2 politics
    ax = axs[1]
    for i, (m, name, party) in enumerate(E.PRESIDENTS):
        a = pm(m); b = pm(E.PRESIDENTS[i + 1][0]) if i + 1 < len(E.PRESIDENTS) else pm("2029-01")
        ax.axvspan(a, b, color=C[party], alpha=0.8, lw=0)
        ax.text(a + (b - a) / 2, 0.55, name, ha="center", va="center", fontsize=8.5)
    for y in E.MIDTERM_YEARS:
        ax.axvline(pm(f"{y}-11"), color="#444", lw=0.8, ls=":"); ax.text(pm(f"{y}-11"), 0.08, str(y), fontsize=6.5, ha="center", color="#333")
    ax.set_yticks([]); ax.set_ylim(0, 1)
    ax.set_title("② 政治周期（總統任期；虛線 = 中期選舉月）", loc="left", fontsize=12, fontweight="bold")
    # 3 technology
    ax = axs[2]
    shade(ax, [(a, b) for a, b, *_ in E.TECH_WAVES], C["wave"], 0.7, 1); shade(ax, E.TECH_BUSTS, C["bust"], 0.9, 1)
    rel = (F["ixic"] / F["sp"]); rel = rel / rel.dropna().iloc[0]
    ax.plot(rel.index, rel, color="#9467bd", lw=1.4, label="納指／標普 相對強弱（1971 = 1）")
    ax.set_yscale("log"); ax.set_ylabel("相對強弱 (log)")
    for i, (a, b, lab, lead) in enumerate(E.TECH_WAVES):
        ax.text(pm(a), ax.get_ylim()[1] * (0.92 if i % 2 == 0 else 0.72), lab, fontsize=7.5, rotation=0, va="top", ha="left", color="#5a3d00")
    ax.legend(loc="lower right", fontsize=9, handles=ax.get_legend_handles_labels()[0] + [Patch(color=C["wave"], alpha=0.9, label="產業／科技狂熱期"), Patch(color=C["bust"], label="爆破期")])
    ax.set_title("③ 技術革命／產業周期", loc="left", fontsize=12, fontweight="bold")
    # 4 shocks + oil
    ax = axs[3]
    ax.plot(F.index, F["wti"], color=C["oil"], lw=1.4, label="原油 名義 $/桶（1986 年前為官方牌價錨點內插）")
    ax.plot(F.index, F["oil_real"], color=C["oil"], lw=0.9, ls=":", label="原油 實質（2026 年物價）")
    ax.set_yscale("log"); ax.set_ylabel("$/桶 (log)"); ax.set_ylim(1, 400)
    ups = 0
    for m, lab, typ in E.SHOCKS:
        t = pm(m); v = F["wti"].get(t, np.nan)
        col = "#b22222" if "油" in typ or "中東" in typ else "#333"
        ax.plot([t], [v], marker="v" if "油" in typ or "中東" in typ else "o", color=col, ms=6, zorder=5)
        ax.annotate(lab, (t, v), xytext=(0, 12 + 11 * (ups % 4)), textcoords="offset points", fontsize=6.5, ha="center", color=col,
                    arrowprops=dict(arrowstyle="-", color=col, lw=0.5))
        ups += 1
    ax.legend(loc="upper left", fontsize=9)
    ax.set_title("④ 黑天鵝／地緣（▼ = 中東／油震）", loc="left", fontsize=12, fontweight="bold")
    # 5 S&P real
    ax = axs[4]
    for b in J["bears"]:
        ax.axvspan(pm(b["peak"]), pm(b["trough"]), color=C["bear"], alpha=0.8, lw=0)
        ax.text(pm(b["trough"]), F["sp_real"].min() * 1.05, f'{b["dd"]:.0f}%', fontsize=7, ha="center", color="#8b0000")
    ax.plot(F.index, F["sp_real"], color="#111", lw=1.3, label="標普 500 實質（2026 年物價，log）")
    ax.plot(F.index, F["sp"], color="#777", lw=0.8, ls="--", label="標普 500 名義")
    ax.set_yscale("log"); ax.set_ylabel("指數 (log)")
    for ep in J["episodes"]:
        t = pm(ep["anchor"]); ax.axvline(t, color="#1f77b4", lw=0.9, ls="--")
        ax.text(t, ax.get_ylim()[1] * 0.93, ep["key"], fontsize=8, ha="center", color="#1f77b4", fontweight="bold")
    ax.axvline(NOW, color=C["now"], lw=1.5); ax.text(NOW, ax.get_ylim()[1] * 0.93, "2026-10", fontsize=8, ha="right", fontweight="bold")
    ax.legend(loc="upper left", fontsize=9, handles=ax.get_legend_handles_labels()[0] + [Patch(color=C["bear"], label="熊市（月線收市跌 ≥20%）"), Patch(color=C["rec"], alpha=0.6, label="NBER 衰退")])
    ax.set_title("⑤ 標普 500 —— 藍虛線 = 對標年份錨點", loc="left", fontsize=12, fontweight="bold")
    ax.xaxis.set_major_locator(mdates.YearLocator(5)); ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    for a in axs[:4]: a.axvline(NOW, color=C["now"], lw=1.2)
    fig.subplots_adjust(top=0.965, bottom=0.03, left=0.05, right=0.99)
    fig.suptitle("四大力量嘅牛熊周期 1960–2026：息口、政治、產業、黑天鵝 —— 同標普 500 實質走勢", fontsize=15, fontweight="bold", y=0.99)
    fig.text(0.01, 0.003, "數據：Shiller（標普、CPI）、FRED 鏡像（10 年期）、EIA 鏡像（WTI 1986–）、BP 年鑑錨點（1986 年前油價）、Yahoo（^IRX、^IXIC、^GSPC 月收市）；"
             "衰退 = NBER；加減息周期按聯邦基金利率轉向月；最新月份見注釋頁。", fontsize=8, color="#444")
    fig.savefig(f"{OUT}/01_four_forces.png", dpi=130, bbox_inches="tight"); plt.close(fig)

def analogues():
    eps = [e for e in J["episodes"]]
    keys = ["sp", "wti", "irx", "y10", "cpi_yoy"]
    titles = {"sp": "標普 500（錨點月 = 0%）", "wti": "原油（錨點月 = 0%）", "irx": "3 個月息 %", "y10": "10 年期息 %", "cpi_yoy": "CPI 按年 %"}
    fig, axs = plt.subplots(len(keys), 1, figsize=(13, 17), sharex=True, gridspec_kw=dict(hspace=0.12))
    cmap = plt.get_cmap("tab10")
    ks = list(range(-12, 25))
    for i, k in enumerate(keys):
        ax = axs[i]
        for j, ep in enumerate(eps):
            p = ep["paths"][k]; ys = [p.get(str(x), p.get(x)) for x in ks]
            ys = [np.nan if v is None else v for v in ys]
            ax.plot(ks, ys, color=cmap(j % 10), lw=1.6, alpha=0.9, label=f'{ep["key"]} {ep["title"][:14]}')
        # now: path up to 0 from the frame
        idx = [NOW + pd.offsets.MonthEnd(x) for x in range(-12, 1)]
        s = F[k].reindex(idx)
        if k in ("sp", "wti"): s = (s / F[k].loc[NOW] - 1) * 100
        ax.plot(range(-12, 1), s.values, color="k", lw=3.2, label="2026（至 10 月）")
        ax.axvline(0, color="#999", lw=0.8); ax.grid(alpha=0.25); ax.set_ylabel(titles[k])
        if k in ("sp", "wti"): ax.axhline(0, color="#999", lw=0.8)
    axs[0].legend(fontsize=8.5, ncol=4, loc="upper left"); axs[-1].set_xlabel("相對錨點月（月）")
    fig.subplots_adjust(top=0.96, bottom=0.04, left=0.07, right=0.98)
    fig.suptitle("十個對標時期 vs 2026：錨點前 12 個月至後 24 個月", fontsize=14, fontweight="bold", y=0.985)
    fig.savefig(f"{OUT}/02_analogues.png", dpi=130, bbox_inches="tight"); plt.close(fig)

FAMILIES = [("能源", "XLE", "能源"), ("油服", "^OSX", None), ("黃金股", "^XAU", "黃金股"), ("原材料", "XLB", "原材料"),
            ("工業", "XLI", "工業"), ("運輸", "^DJT", "運輸"), ("非必需消費", "XLY", "非必需消費"), ("房屋建築", "^HGX", "房屋建築"),
            ("必需消費", "XLP", "必需消費"), ("醫療保健", "XLV", "醫療保健"), ("科技", "XLK", "科技"), ("半導體", "^SOX", None),
            ("納指", "^IXIC", None), ("金融", "XLF", "金融"), ("銀行", "^BKX", None), ("公用事業", "XLU", "公用事業"),
            ("電訊／媒體", None, "電訊／媒體"), ("房地產", "IYR", "房地產"), ("小型股", "^RUT", None), ("價值 IWD", "IWD", None),
            ("增長 IWF", "IWF", None), ("長債 TLT", "TLT", None), ("黃金 GLD", "GLD", None)]

def family_table(eps, field):
    """rows = sector families, cols = episodes; ETF/index value where it exists, else the survivors basket (flagged)."""
    vals, flags = {}, {}
    for ep in eps:
        by_sym = {g["sym"]: g for g in ep["groups"] if g["sym"]}
        by_bask = {g["group"].split("（")[0]: g for g in ep["groups"] if g["kind"] == "長壽股籃"}
        for fam, sym, bask in FAMILIES:
            g = by_sym.get(sym) if sym else None
            flag = ""
            if (g is None or g[field] is None) and bask and bask in by_bask:
                g = by_bask[bask]; flag = "*"
            v = None if g is None or g[field] is None else g[field] * 100
            vals.setdefault(fam, {})[ep["key"]] = v; flags.setdefault(fam, {})[ep["key"]] = flag
    cols = [e["key"] for e in eps]
    return pd.DataFrame(vals).T.reindex(index=[f[0] for f in FAMILIES], columns=cols), pd.DataFrame(flags).T.reindex(index=[f[0] for f in FAMILIES], columns=cols)

def sectors():
    eps = J["episodes"]
    win, wf = family_table(eps, "win_x"); aft, af = family_table(eps, "after_x")
    fig, axs = plt.subplots(1, 2, figsize=(20, 0.48 * len(FAMILIES) + 3), gridspec_kw=dict(wspace=0.3))
    for ax, df, fl, ttl in ((axs[0], win, wf, "事件窗口內：相對標普 500 超額回報（百分點）"), (axs[1], aft, af, "錨點後 12 個月：相對標普 500 超額回報（百分點）")):
        v = df.values.astype(float); lim = np.nanpercentile(np.abs(v[np.isfinite(v)]), 92) if np.isfinite(v).any() else 50
        ax.imshow(v, cmap="RdYlGn", vmin=-lim, vmax=lim, aspect="auto")
        ax.set_xticks(range(df.shape[1])); ax.set_xticklabels(df.columns, fontsize=11)
        ax.set_yticks(range(df.shape[0])); ax.set_yticklabels(df.index, fontsize=10)
        for i in range(df.shape[0]):
            for j in range(df.shape[1]):
                if not np.isnan(v[i, j]): ax.text(j, i, f"{v[i, j]:+.0f}{fl.values[i, j]}", ha="center", va="center", fontsize=9, color="#111")
        ax.set_title(ttl, fontsize=12, fontweight="bold", pad=28); ax.xaxis.tick_top()
    fig.subplots_adjust(top=0.9, bottom=0.05, left=0.07, right=0.99)
    fig.suptitle("邊類股票跑贏／跑輸標普 500：有 ETF／指數用 ETF／指數，1998 年前用長壽股等權籃（* = 籃，有倖存者偏差）", fontsize=13, fontweight="bold", y=0.985)
    fig.text(0.01, 0.005, "窗口：" + "；".join(f'{e["key"]} {e["span"][0]}→{e["span"][1]}（錨點 {e["anchor"]}）' for e in eps), fontsize=8, color="#444")
    fig.savefig(f"{OUT}/03_sectors.png", dpi=130, bbox_inches="tight"); plt.close(fig)

def similarity():
    s = pd.Series(J["similarity"]["series"]); s.index = pd.to_datetime(s.index) + pd.offsets.MonthEnd(0)
    fig, ax = plt.subplots(figsize=(18, 5.5))
    ax.plot(s.index, s.values, color="#1f77b4", lw=1.1)
    ax.invert_yaxis(); ax.set_ylabel("加權 z 距離（越低越似 2026-10）")
    shade(ax, E.RECESSIONS, C["rec"], 0.5)
    for r in J["similarity"]["top"]:
        t = pm(r["month"]); ax.plot([t], [r["dist"]], "o", color="#d62728", ms=7, zorder=5)
        f12 = "" if r["fwd12"] is None else f'{r["fwd12"]:+.0f}%'
        ax.annotate(f'{r["month"]}\n12 個月後 {f12}', (t, r["dist"]), xytext=(0, -28), textcoords="offset points", ha="center", fontsize=7.5, color="#8b0000")
    ax.axvline(NOW, color="k", lw=1.2); ax.grid(alpha=0.25)
    ax.set_title("每個月同 2026-10 嘅相似度（油價 12 個月變化、CPI、3 個月息 3/12 個月變化、10 年期 12 個月變化、曲線斜率、實質短息、標普 12 個月回報同距高位）",
                 fontsize=11, loc="left")
    ax.xaxis.set_major_locator(mdates.YearLocator(5)); ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.set_xlim(pm("1960-01"), pm("2028-06"))
    fig.savefig(f"{OUT}/04_similarity.png", dpi=130, bbox_inches="tight"); plt.close(fig)

if __name__ == "__main__":
    four_forces(); analogues(); sectors(); similarity(); print("charts written to", OUT)

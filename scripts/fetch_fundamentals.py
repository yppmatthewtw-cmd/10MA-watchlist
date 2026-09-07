#!/usr/bin/env python3
"""Pull income-statement fundamentals from Yahoo Finance for the watchlist's
tickers — run on a GitHub Actions runner (the research container's egress proxy
blocks Yahoo), see .github/workflows/fetch_fundamentals.yml.

Per ticker: the last 6 quarterly income statements and 4 annual ones (revenue,
gross profit, operating income, unusual items, normalized income, net income,
EPS), the company's sector/industry/currency, the analyst revenue and EPS
estimates for the current and next quarter, and the next earnings date.

"Normalized Income" is Yahoo's net income with unusual items (and their tax
effect) removed, which is exactly the 經常 (recurring) column of the workbook;
"Total Unusual Items" is the 一次 (one-off) column. Both are absent for many
companies — the builder marks those rows 待核實 rather than guessing.
"""
import json, math, os, sys, time

import pandas as pd
import yfinance as yf

SCREEN = os.environ.get("SCREEN_JSON", "data/screen_results12.json")
OUT = os.environ.get("OUT", "data/fundamentals/income_r12.json")
LIMIT = int(os.environ.get("LIMIT", "0"))          # 0 = all, else first N (smoke test)

scr = json.load(open(SCREEN))
rows = scr["page1"]
if LIMIT:
    rows = rows[:LIMIT]
print(f"{len(rows)} tickers from {SCREEN} ({scr['meta']['last_date']} close)")

# Nasdaq writes share classes as BRK.B / BF/B; Yahoo wants BRK-B
def ysym(s):
    return s.replace(".", "-").replace("/", "-")

WANT = {                     # our key -> the row labels Yahoo may use, best first
    "revenue": ["Total Revenue", "Operating Revenue"],
    "cost": ["Cost Of Revenue"],
    "gross": ["Gross Profit"],
    "opex": ["Operating Expense"],
    "operating": ["Operating Income", "Total Operating Income As Reported"],
    "ebitda": ["EBITDA", "Normalized EBITDA"],
    "unusual": ["Total Unusual Items", "Total Unusual Items Excluding Goodwill"],
    "unusual_tax": ["Tax Effect Of Unusual Items"],
    "normalized": ["Normalized Income"],
    "pretax": ["Pretax Income"],
    "tax": ["Tax Provision"],
    "interest": ["Net Non Operating Interest Income Expense"],
    "other": ["Other Income Expense", "Other Non Operating Income Expenses"],
    "net": ["Net Income Common Stockholders", "Net Income", "Net Income Including Noncontrolling Interests"],
    "eps": ["Diluted EPS", "Basic EPS"],
}


def num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) or math.isinf(f) else f


def statements(df, n):
    """[{end: 'YYYY-MM-DD', <key>: value...}] newest first, at most n periods."""
    if df is None or getattr(df, "empty", True):
        return []
    out = []
    idx = {str(i).strip(): i for i in df.index}
    for col in list(df.columns)[:n]:
        rec = {"end": pd.Timestamp(col).strftime("%Y-%m-%d")}
        for key, labels in WANT.items():
            for lab in labels:
                if lab in idx:
                    v = num(df.loc[idx[lab], col])
                    if v is not None:
                        rec[key] = v
                        break
        out.append(rec)
    return out


def est_frame(df):
    """{'0q': {...}, '+1q': {...}} from an estimates DataFrame, if it has one."""
    if df is None or getattr(df, "empty", True):
        return {}
    out = {}
    for period in df.index:
        rec = {}
        for c in df.columns:
            v = num(df.loc[period, c])
            if v is not None:
                rec[str(c)] = v
        if rec:
            out[str(period)] = rec
    return out


res, failed = {}, []
for i, r in enumerate(rows, 1):
    sym = r["sym"]
    rec = {"sym": sym, "screen_name": r.get("name"), "close": r.get("close"),
           "mcap_b": r.get("mcap"), "cap": r.get("cap"), "exch": r.get("exch"),
           "sector_zh": r.get("sector_zh"), "industry_screen": r.get("industry")}
    for attempt in range(3):
        try:
            t = yf.Ticker(ysym(sym))
            rec["quarterly"] = statements(t.quarterly_income_stmt, 6)
            rec["annual"] = statements(t.income_stmt, 4)
            try:
                info = t.get_info() or {}
            except Exception:
                info = {}
            for k_out, k_in in (("name", "longName"), ("sector", "sector"), ("industry", "industry"),
                                ("currency", "currency"), ("fin_currency", "financialCurrency"),
                                ("mcap", "marketCap"), ("employees", "fullTimeEmployees"),
                                ("trailing_pe", "trailingPE"), ("forward_pe", "forwardPE"),
                                ("profit_margin", "profitMargins"), ("op_margin", "operatingMargins"),
                                ("rev_growth", "revenueGrowth"), ("earn_growth", "earningsGrowth"),
                                ("rev_ttm", "totalRevenue"), ("net_ttm", "netIncomeToCommon"),
                                ("eps_ttm", "trailingEps"), ("eps_fwd", "forwardEps")):
                v = info.get(k_in)
                if v is not None:
                    rec[k_out] = num(v) if isinstance(v, (int, float)) else str(v)
            for attr, key in (("revenue_estimate", "rev_est"), ("earnings_estimate", "eps_est")):
                try:
                    rec[key] = est_frame(getattr(t, attr))
                except Exception:
                    pass
            try:
                cal = t.calendar or {}
                d = cal.get("Earnings Date")
                if d:
                    rec["next_earnings"] = str(d[0] if isinstance(d, (list, tuple)) else d)[:10]
            except Exception:
                pass
            break
        except Exception as e:
            print(f"{sym}: attempt {attempt + 1} failed: {e}")
            time.sleep(10 * (attempt + 1))
    else:
        failed.append(sym)
        continue
    if not rec.get("quarterly"):
        failed.append(sym)
    res[sym] = rec
    if i % 20 == 0:
        print(f"  {i}/{len(rows)} done")
    time.sleep(0.6)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(res, open(OUT, "w"), ensure_ascii=False, indent=1, sort_keys=True)
have_q = sum(1 for v in res.values() if v.get("quarterly"))
have_norm = sum(1 for v in res.values() if any("normalized" in q for q in v.get("quarterly", [])))
have_unu = sum(1 for v in res.values() if any("unusual" in q for q in v.get("quarterly", [])))
have_est = sum(1 for v in res.values() if v.get("rev_est"))
print(f"wrote {OUT}: {len(res)} tickers · with quarterly {have_q} · normalized income {have_norm} · "
      f"unusual items {have_unu} · revenue estimates {have_est} · failed {len(failed)}")
if failed:
    print("no data:", " ".join(sorted(failed)))
if have_q < 0.8 * len(rows):
    sys.exit(f"only {have_q}/{len(rows)} with income statements; refusing to commit")

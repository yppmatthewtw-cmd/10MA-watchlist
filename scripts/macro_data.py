"""Loaders for the macro-regime study.

Long histories come from four public datahub mirrors (cloned read-only into the
scratchpad, see README) and from one Yahoo monthly pull made by the
fetch_yahoo_eod workflow (data/yahoo/macro_monthly_*.csv.gz):
  Shiller (S&P composite, CPI, long rate, monthly from 1871)   datasets/s-and-p-500
  WTI / Brent spot, daily from 1986 / 1987                       datasets/oil-prices
  10-year constant-maturity yield, monthly from 1953             datasets/bond-yields-us-10y
  Gold, monthly                                                  datasets/gold-prices
  VIX, daily from 1990                                           datasets/finance-vix
Everything is resampled to month-end. Recent months the mirrors have not caught
up with are patched from the published figures listed in PATCH (each one dated
and sourced in the notes sheet)."""
import glob, gzip, os, math
import numpy as np, pandas as pd

HIST = os.environ.get("MACRO_HIST", "/tmp/claude-0/-home-user-10MA-watchlist/1821eb3b-7002-5041-b904-77ace4d47850/scratchpad/hist")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _m(s):                       # month-end index
    s = s.copy(); s.index = pd.to_datetime(s.index).to_period("M").to_timestamp("M"); return s[~s.index.duplicated(keep="last")]

def shiller():
    df = pd.read_csv(f"{HIST}/s-and-p-500/data/data.csv", parse_dates=["Date"]).set_index("Date").replace(0.0, np.nan)
    out = pd.DataFrame({"sp": _m(df["SP500"]), "cpi": _m(df["Consumer Price Index"]), "long": _m(df["Long Interest Rate"]),
                        "div": _m(df["Dividend"]), "eps": _m(df["Earnings"]), "pe10": _m(df["PE10"])})
    return out

def oil():
    w = pd.read_csv(f"{HIST}/oil-prices/data/wti-daily.csv", parse_dates=["Date"]).set_index("Date")["Price"]
    b = pd.read_csv(f"{HIST}/oil-prices/data/brent-daily.csv", parse_dates=["Date"]).set_index("Date")["Price"]
    wm, bm = w.resample("ME").mean(), b.resample("ME").mean()
    wl, bl = w.resample("ME").last(), b.resample("ME").last()
    from macro_events import OIL_ANCHORS
    a = pd.Series({pd.Period(d, "M").to_timestamp("M"): v for d, v in OIL_ANCHORS})
    idx = pd.date_range(a.index[0], wm.index[0] - pd.offsets.MonthEnd(1), freq="ME")
    pre = np.exp(np.interp(idx.map(pd.Timestamp.toordinal), a.index.map(pd.Timestamp.toordinal), np.log(a.values)))
    pre = pd.Series(pre, idx)
    wti = pd.concat([pre, wm]); wti_last = pd.concat([pre, wl])
    return pd.DataFrame({"wti": wti, "wti_last": wti_last, "brent": bm, "brent_last": bl, "oil_src": ["anchor"] * len(pre) + ["spot"] * len(wm)})

def ten_year():
    t = pd.read_csv(f"{HIST}/bond-yields-us-10y/data/monthly.csv", parse_dates=["Date"]).set_index("Date")["Rate"]
    return _m(t).rename("y10")

def gold():
    g = pd.read_csv(f"{HIST}/gold-prices/data/monthly.csv"); g["Date"] = pd.to_datetime(g["Date"], format="%Y-%m")
    return _m(g.set_index("Date")["Price"]).rename("gold")

def vix():
    v = pd.read_csv(f"{HIST}/finance-vix/data/vix-daily.csv"); v.columns = [c.strip().lower() for c in v.columns]
    dcol = [c for c in v.columns if "date" in c][0]; ccol = [c for c in v.columns if "close" in c][0]
    s = pd.Series(v[ccol].values, pd.to_datetime(v[dcol]))
    return s.resample("ME").last().rename("vix")

def yahoo_monthly(path=None):
    path = path or sorted(glob.glob(f"{REPO}/data/yahoo/macro_monthly_*.csv.gz"))[-1]
    df = pd.read_csv(path, parse_dates=["date"])
    df["date"] = df["date"].dt.to_period("M").dt.to_timestamp("M")
    df = df.drop_duplicates(["symbol", "date"], keep="last")
    adj = df.pivot(index="date", columns="symbol", values="adj_close")
    close = df.pivot(index="date", columns="symbol", values="close")
    return adj, close

# Months the mirrors have not reached, from published figures (month, value, source)
PATCH = {
    "cpi_yoy": {  # BLS CPI-U all items, 12-month % change, filled in by macro_regimes from CPI_YOY_RECENT
    },
    "y10": {"2026-09": (5.05, "FRED DGS10 月均約 5.0–5.1；09-28 收 5.23、09-30 高見 5.34（2002 年後最高）")},
    "wti": {"2026-10": (92.6, "WTI 10-02 $92.63 (Trading Economics)")},
    "gold": {"2026-09": (4300.0, "9 月均價約 $4,300；10-02 $4,190 (Trading Economics)"), "2026-10": (4190.0, "10-02 $4,190")},
    "vix": {"2026-09": (15.0, "9 月底約 15"), "2026-10": (15.0, "10-02 約 15")},
}

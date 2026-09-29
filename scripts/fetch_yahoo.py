#!/usr/bin/env python3
"""Pull daily bars from Yahoo Finance for the tickers in data/yahoo/tickers.txt
and write them as one gzipped CSV — run on a GitHub Actions runner (the research
container's egress proxy blocks Yahoo), see .github/workflows/fetch_yahoo_eod.yml.

Yahoo is the second, independent source for the days the Nasdaq-screener series
has no real data for (the mirror's copied days, the volume-less 09-02, the two
partial-volume days) and for cross-checking the single-source 09-04 close; the
comparison itself is done by scripts/yahoo_crosscheck.py against the series.

Unadjusted prices (auto_adjust=False) so a close compares directly with the
screener's last sale; the adjusted close is kept as a separate column, which is
how a split between the two sources shows up.
"""
import csv, gzip, os, sys, time

import pandas as pd
import yfinance as yf

START = os.environ.get("START", "2025-12-26")
END = os.environ.get("END", "2026-09-05")          # yfinance end is exclusive
LIST = os.environ.get("LIST", "data/yahoo/tickers.txt")
INTERVAL = os.environ.get("INTERVAL", "") or "1d"
# Yahoo publishes the last session's daily bar hours after the close (09-17,
# 09-23, 09-28: a few hundred to 1,300 of ~3,850 names that evening), while
# its intraday bars are there at once. An intraday interval is fetched and
# rolled up to one open/high/low/close/volume row per symbol per day; the
# screener takes the day's range from it and the official close and volume
# from the post-close Nasdaq snapshot.
OUT = os.environ.get("OUT", f"data/yahoo/eod_{START}_{END}.csv.gz" if INTERVAL == "1d"
                     else f"data/yahoo/intraday_{START}_{END}_{INTERVAL}.csv.gz")
BATCH = int(os.environ.get("BATCH", "150"))

symbols = [s.strip() for s in open(LIST) if s.strip()]
# Nasdaq writes share classes as BRK.B / BF/B; Yahoo wants BRK-B
ysym = {s: s.replace(".", "-").replace("/", "-") for s in symbols}
back = {v: k for k, v in ysym.items()}
print(f"{len(symbols)} symbols, {START} -> {END}, batches of {BATCH}")

frames, failed = [], []
for i in range(0, len(symbols), BATCH):
    batch = [ysym[s] for s in symbols[i:i + BATCH]]
    for attempt in range(3):
        try:
            df = yf.download(batch, start=START, end=END, interval=INTERVAL, auto_adjust=False,
                             actions=False, group_by="ticker", threads=True, progress=False,
                             prepost=False)
            break
        except Exception as e:                       # rate limit / transient
            print(f"batch {i // BATCH}: attempt {attempt + 1} failed: {e}")
            time.sleep(20 * (attempt + 1))
    else:
        failed += batch; continue
    got = 0
    for y in batch:
        try:
            sub = df[y] if isinstance(df.columns, pd.MultiIndex) else df
        except KeyError:
            failed.append(y); continue
        sub = sub.dropna(subset=["Close"])
        if sub.empty:
            failed.append(y); continue
        sub = sub.reset_index().rename(columns=str.lower)
        if INTERVAL != "1d":                         # roll intraday bars up to the session
            ts = sub.columns[0]
            sub["date"] = pd.to_datetime(sub[ts]).dt.tz_convert("America/New_York").dt.date
            sub = (sub.groupby("date")
                      .agg(open=("open", "first"), high=("high", "max"), low=("low", "min"),
                           close=("close", "last"), volume=("volume", "sum"))
                      .reset_index())
            sub["adj close"] = sub["close"]
        sub["symbol"] = back[y]
        frames.append(sub[["symbol", "date", "open", "high", "low", "close", "adj close", "volume"]])
        got += 1
    print(f"batch {i // BATCH}: {got}/{len(batch)} symbols with bars")
    time.sleep(2)

if not frames:
    sys.exit("no data at all; refusing to write")
all_ = pd.concat(frames)
all_["date"] = pd.to_datetime(all_["date"]).dt.strftime("%Y-%m-%d")
all_ = all_.rename(columns={"adj close": "adj_close"}).sort_values(["symbol", "date"])
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with gzip.open(OUT, "wt", newline="") as f:
    all_.to_csv(f, index=False, float_format="%.4f")
n_sym = all_["symbol"].nunique()
print(f"wrote {OUT}: {len(all_)} bars, {n_sym} symbols, {len(failed)} without data")
if failed:
    print("no data:", " ".join(sorted(failed))[:2000])
if n_sym < 0.8 * len(symbols):
    sys.exit(f"only {n_sym}/{len(symbols)} symbols returned; refusing to commit")

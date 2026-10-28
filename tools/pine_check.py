#!/usr/bin/env python3
"""Does the pinned GG-SHOT Pine strategy fire at the times the signals were posted?

Ports its entry logic (Bollinger breakout + ratcheting trend line) and its ATR-based
targets, then compares them with the signals in signals.csv (symbol,time_utc,direction[,entry]).
Reads ./data/<SYMBOL>.csv written by template_backtest.py fetch. Standard library only.

Pine logic ported (UseATRfilter = false, filter = "No Filtering"):
  BBSignal = close > sma+dev*sd ? 1 : close < sma-dev*sd ? -1 : 0
  BBSignal  1: TrendLine = max(low,  TrendLine[1])
  BBSignal -1: TrendLine = min(high, TrendLine[1])
  BBSignal  0: TrendLine = TrendLine[1]
  iTrend = 1 if TrendLine rose, -1 if it fell, else unchanged
  buy = iTrend flips -1 -> 1, sell = iTrend flips 1 -> -1
  targets: entry = close, TP = entry +/- ATR(14) * [1.5, 3, 5, 9], SL = entry -/+ 6 * ATR(14)
"""
import argparse, csv, datetime as dt, math, statistics as st

TP_MULT = [1.5, 3, 5, 9]
SL_MULT = 6


def load(sym):
    with open(f"data/{sym}.csv") as f:
        return [(int(r["t"]), float(r["o"]), float(r["h"]), float(r["l"]), float(r["c"]))
                for r in csv.DictReader(f)]


def atr(c, n=14):
    out, prev, rma = [None] * len(c), None, None
    trs = []
    for i, (_, _, h, l, cl) in enumerate(c):
        tr = h - l if prev is None else max(h - l, abs(h - prev), abs(l - prev))
        prev = cl
        trs.append(tr)
        if i == n - 1:
            rma = sum(trs) / n
        elif i >= n:
            rma = (rma * (n - 1) + tr) / n
        out[i] = rma
    return out


def pine(c, n, dev):
    """Return (signals {i: 'buy'|'sell'}, z-scores per candle)."""
    sig, z = {}, [None] * len(c)
    tl = trend = None
    prev_trend = None
    for i in range(len(c)):
        if i + 1 < n:
            continue
        closes = [x[4] for x in c[i - n + 1:i + 1]]
        sma, sd = sum(closes) / n, st.pstdev(closes)   # ta.stdev is the biased (population) form
        z[i] = (c[i][4] - sma) / sd if sd else 0.0
        bb = 1 if c[i][4] > sma + dev * sd else -1 if c[i][4] < sma - dev * sd else 0
        old_tl = tl
        if bb == 1:
            tl = c[i][3]
            if old_tl is not None and tl < old_tl:
                tl = old_tl
        elif bb == -1:
            tl = c[i][2]
            if old_tl is not None and tl > old_tl:
                tl = old_tl
        old_trend = trend
        if tl is not None and old_tl is not None:
            if tl > old_tl:
                trend = 1
            elif tl < old_tl:
                trend = -1
        if old_trend == -1 and trend == 1:
            sig[i] = "buy"
        elif old_trend == 1 and trend == -1:
            sig[i] = "sell"
    return sig, z


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--signals", default="signals.csv")
    ap.add_argument("--bb-period", type=int, default=100)
    ap.add_argument("--bb-dev", type=float, default=1.5)
    ap.add_argument("--preset", nargs="*", default=["DOTUSDT=20,2.5"],
                    help="per-symbol SYMBOL=period,dev overrides (script presets)")
    a = ap.parse_args()
    presets = {p.split("=")[0]: tuple(float(x) for x in p.split("=")[1].split(",")) for p in a.preset}

    print(f"{'symbol':9s} {'time_utc':16s} {'side':5s} {'bb':>9s} {'z':>6s} {'z@entry':>8s}  pine signal within -2..+1 candles"
          f"   atr-implied TP1/TP4/SL % (posted: 0.60/5.64/5.15)")
    seen = {}
    with open(a.signals) as f:
        for row in csv.DictReader(f):
            sym = row["symbol"]
            n, dev = presets.get(sym, (a.bb_period, a.bb_dev))
            n = int(n)
            if sym not in seen:
                c = load(sym)
                seen[sym] = (c, *pine(c, n, dev), atr(c))
            c, sig, z, at = seen[sym]
            t = int(dt.datetime.strptime(row["time_utc"], "%Y-%m-%d %H:%M")
                    .replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
            i = max(k for k in range(len(c)) if c[k][0] <= t)
            near = [f"{sig[k]}@{k - i:+d}" for k in range(i - 2, i + 2) if k in sig] or ["none"]
            zi = f"{z[i]:+.2f}" if z[i] is not None else "n/a"
            ze = "n/a"
            if row.get("entry") and i >= n:
                # z-score if the live entry price, not the candle's final close, were "now"
                w = [x[4] for x in c[i - n + 1:i]] + [float(row["entry"])]
                sd = st.pstdev(w)
                ze = f"{(w[-1] - sum(w) / n) / sd:+.2f}" if sd else "n/a"
            if at[i]:
                p = at[i] / c[i][4] * 100
                lv = f"{TP_MULT[0]*p:.2f}/{TP_MULT[3]*p:.2f}/{SL_MULT*p:.2f}"
            else:
                lv = "n/a"
            print(f"{sym:9s} {row['time_utc']:16s} {row['direction']:5s} {f'{n}/{dev}':>9s} {zi:>6s} {ze:>8s}  "
                  f"{','.join(near):34s} {lv}")
    print("\nHow often the script fires on each symbol's data:")
    for sym, (c, sig, z, at) in seen.items():
        days = len(c) / 96
        b = sum(1 for v in sig.values() if v == "buy")
        s = sum(1 for v in sig.values() if v == "sell")
        print(f"  {sym:9s} {b} buys, {s} sells in {days:.1f} days")


if __name__ == "__main__":
    main()

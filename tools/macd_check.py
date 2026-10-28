#!/usr/bin/env python3
"""MACD(12,26,9) state at each signal's posting time, on 15m / 30m / 60m candles.

Reads signals.csv (symbol,time_utc,direction[,entry]) and ./data/<SYMBOL>.csv from
template_backtest.py fetch. 30m and 60m candles are built from the 15m data.
For each timeframe it uses only candles that had closed by the posting time, and shows
the MACD vs signal line, the histogram, and the most recent cross with its age.
It also prints how often a bullish/bearish cross shows up in a random 3-candle window,
so six-for-six can be judged against chance. Standard library only.
"""
import argparse, csv, datetime as dt

FAST, SLOW, SIG = 12, 26, 9


def load(sym):
    with open(f"data/{sym}.csv") as f:
        return [(int(r["t"]), float(r["o"]), float(r["h"]), float(r["l"]), float(r["c"]))
                for r in csv.DictReader(f)]


def resample(c, minutes):
    if minutes == 15:
        return c
    ms = minutes * 60000
    out, cur = [], None
    for t, o, h, l, cl in c:
        start = t - t % ms
        if cur and cur[0] == start:
            cur = (start, cur[1], max(cur[2], h), min(cur[3], l), cl)
        else:
            if cur:
                out.append(cur)
            cur = (start, o, h, l, cl)
    if cur:
        out.append(cur)
    # keep only groups that are complete (all 15m candles present)
    need = minutes // 15
    counts = {}
    for t, *_ in c:
        counts[t - t % ms] = counts.get(t - t % ms, 0) + 1
    return [x for x in out if counts[x[0]] == need]


def ema(v, n):
    k, out, e = 2 / (n + 1), [None] * len(v), None
    for i, x in enumerate(v):
        if i == n - 1:
            e = sum(v[:n]) / n
        elif i >= n:
            e = x * k + e * (1 - k)
        if i >= n - 1:
            out[i] = e
    return out


def macd(closes, fast=FAST, slow=SLOW, sig=SIG):
    f, s = ema(closes, fast), ema(closes, slow)
    m = [a - b if a is not None and b is not None else None for a, b in zip(f, s)]
    valid = [x for x in m if x is not None]
    sg_v = ema(valid, sig)
    sg = [None] * (len(m) - len(valid)) + sg_v
    h = [a - b if a is not None and b is not None else None for a, b in zip(m, sg)]
    return m, sg, h


def last_cross(h, i):
    """Most recent sign change of the histogram at or before index i: (direction, bars ago)."""
    for k in range(i, 0, -1):
        if h[k] is None or h[k - 1] is None:
            return None
        if h[k - 1] <= 0 < h[k]:
            return "bull", i - k
        if h[k - 1] >= 0 > h[k]:
            return "bear", i - k
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--signals", default="signals.csv")
    ap.add_argument("--window", type=int, default=3, help="candles that count as a 'recent' cross")
    a = ap.parse_args()

    cache, rows_out, stats = {}, [], {}
    with open(a.signals) as f:
        sigs = list(csv.DictReader(f))
    print(f"{'symbol':9s} {'time_utc':16s} {'side':5s} tf   macd>sig  hist trend    last cross")
    hits = {15: 0, 30: 0, 60: 0}
    for row in sigs:
        sym = row["symbol"]
        if sym not in cache:
            cache[sym] = {tf: resample(load(sym), tf) for tf in (15, 30, 60)}
        t = int(dt.datetime.strptime(row["time_utc"], "%Y-%m-%d %H:%M")
                .replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
        want = "bull" if row["direction"].strip().lower() == "long" else "bear"
        for tf in (15, 30, 60):
            c = cache[sym][tf]
            closed = [k for k in range(len(c)) if c[k][0] + tf * 60000 <= t]
            if len(closed) < 40:
                print(f"{sym:9s} {row['time_utc']:16s} {row['direction']:5s} {tf:<3d}  not enough history")
                continue
            i = closed[-1]
            m, sg, h = macd([x[4] for x in c])
            lc = last_cross(h, i)
            above = "yes" if h[i] > 0 else "no "
            trend = "rising " if h[i] > h[i - 1] else "falling"
            if lc:
                txt = f"{lc[0]} {lc[1]} candles ago ({lc[1]*tf} min)"
                if lc[0] == want and lc[1] < a.window:
                    hits[tf] += 1
                    txt += "  <-- matches direction"
            else:
                txt = "none in data"
            print(f"{sym:9s} {row['time_utc']:16s} {row['direction']:5s} {tf:<3d}  {above:8s}  {trend:9s}    {txt}")

    print(f"\nSignals with a same-direction cross within the last {a.window} closed candles: "
          + ", ".join(f"{tf}m {hits[tf]}/{len(sigs)}" for tf in (15, 30, 60)))

    print(f"\nChance level: share of all times (these coins' data) with a bullish / bearish cross in the last {a.window} closed candles")
    for tf in (15, 30, 60):
        bull = bear = n = 0
        for sym in cache:
            c = cache[sym][tf]
            m, sg, h = macd([x[4] for x in c])
            for i in range(60, len(c)):
                n += 1
                lc = last_cross(h, i)
                if lc and lc[1] < a.window:
                    bull += lc[0] == "bull"
                    bear += lc[0] == "bear"
        if n:
            print(f"  {tf:>2d}m: bullish {bull/n:5.1%}   bearish {bear/n:5.1%}   ({n} candles)")


if __name__ == "__main__":
    main()

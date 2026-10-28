#!/usr/bin/env python3
"""MACD cross using the LIVE price as the forming 15m candle's close, for several settings.

macd_check.py only sees candles that had closed. A signal posted mid-candle can come from a cross
on the forming candle. For each signal in signals.csv (needs the entry column) this appends the
entry price as the close of the candle being formed and reports, per MACD setting, the histogram
at the last closed candle and at the live price, and whether it flipped from <=0 to >0 (bullish)
or >=0 to <0 (bearish). It also prints how often a flip occurs on a random closed candle.
Run from this folder after template_backtest.py fetch. Standard library only.
"""
import argparse, csv, datetime as dt
from macd_check import load, macd

ap = argparse.ArgumentParser()
ap.add_argument("--signals", default="signals.csv")
ap.add_argument("--params", nargs="+", default=["12,26,9", "8,17,9", "6,13,5", "5,35,5", "3,10,16"],
                help="fast,slow,signal sets to try")
a = ap.parse_args()
sets = [tuple(int(x) for x in p.split(",")) for p in a.params]

cache = {}
print(f"{'symbol':9s} {'time_utc':16s} {'side':5s} " + " | ".join(f"{p:^22s}" for p in a.params))
print(f"{'':32s} " + " | ".join(f"{'hist closed -> live':^22s}" for _ in a.params))
hits = {p: 0 for p in a.params}
n = 0
with open(a.signals) as f:
    for row in csv.DictReader(f):
        sym = row["symbol"]
        c = cache.setdefault(sym, load(sym))
        t = int(dt.datetime.strptime(row["time_utc"], "%Y-%m-%d %H:%M")
                .replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
        i = max(k for k in range(len(c)) if c[k][0] <= t)
        price = float(row["entry"])
        want = 1 if row["direction"].strip().lower() == "long" else -1
        closed = [x[4] for x in c[:i]]
        n += 1
        cols = []
        for p, (fa, sl, sg) in zip(a.params, sets):
            h0 = macd(closed, fa, sl, sg)[2][-1]
            h1 = macd(closed + [price], fa, sl, sg)[2][-1]
            flip = 1 if h0 <= 0 < h1 else -1 if h0 >= 0 > h1 else 0
            ok = flip == want
            hits[p] += ok
            norm = price
            cols.append(f"{h0/norm*1e4:+7.1f}->{h1/norm*1e4:+7.1f} {'FLIP' if ok else ('flip-' if flip else '    ')}")
        print(f"{sym:9s} {row['time_utc']:16s} {row['direction']:5s} " + " | ".join(f"{x:^22s}" for x in cols))
print("\n(hist in basis points of price; FLIP = same-direction cross on the live candle)")
print("Signals with a same-direction live flip: " + ", ".join(f"{p}: {hits[p]}/{n}" for p in a.params))

print("\nChance level: share of closed 15m candles on which the histogram flips bullish / bearish")
for p, (fa, sl, sg) in zip(a.params, sets):
    bull = bear = tot = 0
    for c in cache.values():
        h = macd([x[1] for x in c], fa, sl, sg)[2]
        for k in range(60, len(h)):
            tot += 1
            bull += h[k - 1] <= 0 < h[k]
            bear += h[k - 1] >= 0 > h[k]
    print(f"  {p:8s} bullish {bull/tot:5.1%}  bearish {bear/tot:5.1%}")

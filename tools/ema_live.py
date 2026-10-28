#!/usr/bin/env python3
"""Which EMA rule flips on the forming 15m candle at each EMA Cross signal?

For every row of signals.csv (symbol,time_utc,direction,entry) this appends the entry price as the
close of the forming candle and checks many candidate rules: fast EMA crossing the slow EMA, and
price crossing a single EMA. A rule "hits" when it flips in the posted direction on that live
candle after not being flipped at the last close. The table at the end shows, per rule, how many
signals it hit and how often it flips on a random candle (chance level).
Run from this folder after template_backtest.py fetch. Standard library only.
"""
import argparse, csv, datetime as dt
from macd_check import load, ema

PAIRS = [(5, 10), (5, 20), (8, 21), (9, 21), (9, 26), (10, 30), (12, 26), (20, 50), (21, 55)]
SINGLES = [9, 20, 21, 50]
NAMES = [f"EMA{f}/EMA{s}" for f, s in PAIRS] + [f"price/EMA{n}" for n in SINGLES]


def diffs(closes):
    """Series of (fast-slow) for each pair and (price-ema) for each single EMA."""
    out = []
    for f, s in PAIRS:
        ef, es = ema(closes, f), ema(closes, s)
        out.append([a - b if a is not None and b is not None else None for a, b in zip(ef, es)])
    for n in SINGLES:
        e = ema(closes, n)
        out.append([c - x if x is not None else None for c, x in zip(closes, e)])
    return out


def flip(d0, d1):
    return 1 if d0 <= 0 < d1 else -1 if d0 >= 0 > d1 else 0


ap = argparse.ArgumentParser()
ap.add_argument("--signals", default="signals.csv")
a = ap.parse_args()

cache, hits, n = {}, [0] * len(NAMES), 0
print(f"{'symbol':9s} {'time_utc':16s} {'side':5s} rules that flipped in the posted direction on the live candle")
with open(a.signals) as f:
    for row in csv.DictReader(f):
        sym = row["symbol"]
        c = cache.setdefault(sym, load(sym))
        t = int(dt.datetime.strptime(row["time_utc"], "%Y-%m-%d %H:%M")
                .replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
        i = max(k for k in range(len(c)) if c[k][0] <= t)
        want = 1 if row["direction"].strip().lower() == "long" else -1
        closed = [x[4] for x in c[:i]]
        d_closed = diffs(closed)
        d_live = diffs(closed + [float(row["entry"])])
        got = []
        for k, name in enumerate(NAMES):
            d0, d1 = d_closed[k][-1], d_live[k][-1]
            if d0 is not None and d1 is not None and flip(d0, d1) == want:
                got.append(name)
                hits[k] += 1
        n += 1
        print(f"{sym:9s} {row['time_utc']:16s} {row['direction']:5s} {', '.join(got) or 'none'}")

print(f"\nPer rule: signals hit / {n}   |   chance a random candle flips (either direction)")
for k, name in enumerate(NAMES):
    tot = fl = 0
    for c in cache.values():
        d = diffs([x[4] for x in c])[k]
        for j in range(80, len(d)):
            tot += 1
            fl += flip(d[j - 1], d[j]) != 0
    print(f"  {name:13s} {hits[k]}/{n}   {fl/tot:5.1%}")

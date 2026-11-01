#!/usr/bin/env python3
"""Does the source post flips of the last CLOSED candles, instead of the live price?

The 18:50 UTC+5 round on 1 Nov (13:50 UTC) held flips our log had seen 5-20 minutes earlier, in the 13:30 and 13:45
candles, so the source may post what flipped on closed candles. For every scan (source posts less than 90 s apart)
this checks, with ./data candles only (no network): did the rule flip on the last closed candle (back = 1), the one
before (back = 2)? Reports for back = 1, 1-2 and 1-3 how many posted signals are found and how many extra flips there
are on the source's coins. Standard library only.
"""
import argparse, csv, datetime as dt, glob, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from mygg.rules import MACDCross, EMACross, BBBreak

BAR = 900000


def load(p):
    with open(p) as f:
        return [(int(r["t"]), float(r["c"])) for r in csv.DictReader(f)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--source", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "source_signals.csv"))
    ap.add_argument("--gap", type=int, default=90)
    a = ap.parse_args()
    with open(a.source) as f:
        src = list(csv.DictReader(f))
    in_list = {r["symbol"] for r in src}
    coins = {os.path.basename(p)[:-4]: load(p) for p in sorted(glob.glob(os.path.join(a.data, "*.csv")))}
    rules = {"MACD Cross": MACDCross(), "EMA Cross": EMACross(), "BB": BBBreak(squeeze=None)}
    rows = sorted(((int(dt.datetime.strptime(r["time_utc"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=dt.timezone.utc).timestamp()), r)
                   for r in src), key=lambda x: x[0])
    scans, cur = [], []
    for ts, r in rows:
        if cur and ts - cur[-1][0] > a.gap:
            scans.append(cur)
            cur = []
        cur.append((ts, r))
    if cur:
        scans.append(cur)
    res = {b: [0, 0, 0] for b in (1, 2, 3)}          # [found, posted, extra] with lookback 1..b
    for sc in scans:
        t0 = sc[0][0] * 1000
        cs = t0 - t0 % BAR
        posted = {(r["symbol"], r["rule"]): r["direction"] for _, r in sc}
        flips = {}                                    # (sym, rule) -> {back: direction}
        for sym, c in coins.items():
            j = next((k for k in range(len(c)) if c[k][0] == cs), None)
            if j is None or j < 235:
                continue
            closes = [x[1] for x in c]
            for name, rule in rules.items():
                for back in (1, 2, 3):
                    i = j - back
                    f = rule.flip(closes[:i], closes[i])
                    if f:
                        flips.setdefault((sym, name), {})[back] = "long" if f > 0 else "short"
        for b in (1, 2, 3):
            act = {k: [d for bk, d in v.items() if bk <= b] for k, v in flips.items()}
            act = {k: v[0] for k, v in act.items() if v}
            for k, d in posted.items():
                if k[0] in coins:
                    res[b][1] += 1
                    res[b][0] += act.get(k) == d
            res[b][2] += sum(1 for k in act if k not in posted and k[0] in in_list)
    print(f"{len(scans)} scans. Flip on the last closed candle(s), against the source's posts:")
    for b, label in ((1, "last closed candle"), (2, "last 2 closed candles"), (3, "last 3 closed candles")):
        f, p, e = res[b]
        print(f"  {label:24s} found {f}/{p} posted; extra flips on the source's coins: {e}")


if __name__ == "__main__":
    main()

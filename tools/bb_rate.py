#!/usr/bin/env python3
"""How many Bollinger breakouts per day would the rule produce at different squeeze thresholds?

Replays ./data/<SYMBOL>.csv (from template_backtest.py fetch) with the candle close as the live
price (a close is the last price of the candle, so this slightly undercounts intrabar flips).
Prints events per day for no squeeze filter and for several width-percentile cut-offs, and
checks the original signals in signals_bb.csv against each cut-off. Standard library only.
"""
import argparse, csv, datetime as dt, glob, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from mygg.rules import BBBreak


def load(path):
    with open(path) as f:
        return [(int(r["t"]), float(r["c"])) for r in csv.DictReader(f)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--cuts", type=float, nargs="+", default=[10, 15, 20, 30, 40])
    ap.add_argument("--signals", default="signals_bb.csv")
    ap.add_argument("--devs", type=float, nargs="+", default=[2.0, 2.5, 3.0], help="band sizes in stdev")
    a = ap.parse_args()
    files = sorted(glob.glob(os.path.join(a.data, "*.csv")))
    cuts = [None] + a.cuts
    count = {(d, c): 0 for d in a.devs for c in cuts}
    days = 0.0
    for fp in files:
        c = load(fp)
        closes = [x[1] for x in c]
        days = max(days, len(c) / 96)
        for d in a.devs:
            base = BBBreak(dev=d, squeeze=None)
            rules = {cut: BBBreak(dev=d, squeeze=cut) for cut in a.cuts}
            for i in range(60, len(closes)):
                if base.flip(closes[:i], closes[i]) == 0:
                    continue
                count[(d, None)] += 1
                for cut, r in rules.items():
                    if r.squeezed(closes[:i]):
                        count[(d, cut)] += 1
    print(f"{len(files)} coins, {days:.1f} days of data; breakout events per day (all coins together):")
    print(f"  {'band size':>10s} " + "".join(f"{'no filter' if c is None else 'pct<=' + format(c, 'g'):>11s}" for c in cuts))
    for d in a.devs:
        print(f"  {d:>7g} sd  " + "".join(f"{count[(d, c)] / days:11.1f}" for c in cuts))

    if os.path.exists(a.signals):
        print("\nOriginal signals: does each pass the cut-off? (width percentile of the prior 200 bands)")
        with open(a.signals) as f:
            sigs = list(csv.DictReader(f))
        for row in sigs:
            p = os.path.join(a.data, row["symbol"] + ".csv")
            if not os.path.exists(p):
                continue
            c = load(p)
            t = int(dt.datetime.strptime(row["time_utc"], "%Y-%m-%d %H:%M")
                    .replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
            i = max(k for k in range(len(c)) if c[k][0] <= t)
            closes = [x[1] for x in c[:i]]
            r = BBBreak(squeeze=100)
            n = r.n
            cur = r._width(closes[-n:])
            hist = [r._width(closes[k - n:k]) for k in range(max(n, len(closes) - 200), len(closes))]
            pct = 100 * sum(1 for x in hist if x <= cur) / len(hist)
            print(f"  {row['symbol']:9s} {row['time_utc']}  width percentile {pct:5.1f}")


if __name__ == "__main__":
    main()

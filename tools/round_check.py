#!/usr/bin/env python3
"""Test of the 'rounds' idea: the source posts in rounds, and each round lists the coins whose rule had
flipped in that candle. For every candle that contains a source post, compare
  posted  : the source's signals (tools/source_signals.csv, from the source channel's Cornix export)
  flips   : what our MACD / EMA / BB (no squeeze filter) rules flip on in that candle, for every coin in ./data
using the candle's high/low as the live price (a touch), so intrabar flips count.
Prints, per candle, each posted signal with ok / MISSED, and the extra flips split into coins that appear
in the source list at all (extra) and coins that never appear (off-list). Standard library only.
"""
import argparse, csv, datetime as dt, glob, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from mygg.rules import MACDCross, EMACross, BBBreak

BAR = 900000


def load(p):
    with open(p) as f:
        return [(int(r["t"]), float(r["o"]), float(r["h"]), float(r["l"]), float(r["c"])) for r in csv.DictReader(f)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--source", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "source_signals.csv"))
    a = ap.parse_args()
    with open(a.source) as f:
        src = list(csv.DictReader(f))
    in_list = {r["symbol"] for r in src}
    coins = {os.path.basename(p)[:-4]: load(p) for p in sorted(glob.glob(os.path.join(a.data, "*.csv")))}
    rules = {"MACD Cross": MACDCross(), "EMA Cross": EMACross(), "BB": BBBreak(squeeze=None)}
    candles = {}
    for r in src:
        t = int(dt.datetime.strptime(r["time_utc"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
        candles.setdefault(t - t % BAR, []).append(r)
    tot_post = tot_hit = tot_extra = tot_off = nc = 0
    for ts in sorted(candles):
        flips = {}
        for sym, c in coins.items():
            j = next((k for k in range(len(c)) if c[k][0] == ts), None)
            if j is None or j < 230:
                continue
            closes = [x[4] for x in c[:j]]
            for name, rule in rules.items():
                up = rule.flip(closes, c[j][2]) == 1
                dn = rule.flip(closes, c[j][3]) == -1
                if up or dn:
                    flips[(sym, name)] = "long" if up else "short"
        posted = {(r["symbol"], r["rule"]): r["direction"] for r in candles[ts]}
        if not any(s in coins for s, _ in posted):
            continue
        nc += 1
        tm = dt.datetime.fromtimestamp(ts / 1000, dt.timezone.utc).strftime("%m-%d %H:%M")
        hit = [k for k, d in posted.items() if flips.get(k) == d]
        miss = [k for k in posted if k not in hit and k[0] in coins]
        extra = [(k, d) for k, d in flips.items() if k not in posted and k[0] in in_list]
        off = [(k, d) for k, d in flips.items() if k[0] not in in_list]
        tot_post += len(hit) + len(miss); tot_hit += len(hit); tot_extra += len(extra); tot_off += len(off)
        short = lambda k: f"{k[0][:-4]}:{k[1].split()[0]}"
        print(f"{tm}  posted {len(posted):2d}  found {len(hit):2d}  missed {len(miss):2d}  extra(in list) {len(extra):2d}  off-list {len(off):2d}")
        if miss:
            print("      missed: " + " ".join(short(k) for k in miss))
        if extra:
            print("      extra:  " + " ".join(short(k) + ("+" if d == "long" else "-") for k, d in extra))
    print(f"\n{nc} candles with posts. Posted signals found by our flips: {tot_hit}/{tot_post}. "
          f"Extra flips on coins that are in the source list: {tot_extra}; on coins that never appear in it: {tot_off}.")


if __name__ == "__main__":
    main()

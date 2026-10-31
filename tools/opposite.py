#!/usr/bin/env python3
"""A signal arrives on a coin while an opposite position is still open. Which handling made more?

  python3 opposite.py ../mygg_flips.csv [--data data] [--amount 5] [Cornix options as in evaluate.py]

Policies, run on the same published signals:
  keep both   every position runs to its own exit (what happens if Cornix opens the opposite trade alongside)
  close old   the open opposite position is closed at the new signal's price, the new one opens
  ignore new  the new signal is skipped while an opposite position is open
Reports signals kept, how many opposite arrivals there were, mean return, total account impact, largest drawdown,
peak open positions and peak margin. Same simulation and caveats as evaluate.py; a few days of data is noisy.
"""
import argparse, bisect, calendar, csv, time
from collections import defaultdict
import evaluate as ev


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("flips")
    ap.add_argument("--data", default="data")
    ap.add_argument("--amount", type=float, default=5.0)
    ap.add_argument("--fee", type=float, default=0.0005)
    ap.add_argument("--entry-weights", default="65,15,10,10")
    ap.add_argument("--tp-weights", default="60,20,10,10")
    ap.add_argument("--trail", choices=["breakeven", "moving"], default="moving")
    a = ap.parse_args()
    ew = tuple(float(x) / 100 for x in a.entry_weights.split(","))
    tw = tuple(float(x) / 100 for x in a.tp_weights.split(","))

    cache, sigs = {}, []
    for r in csv.DictReader(open(a.flips)):
        if r.get("published", "1") == "0":
            continue
        sym = r["symbol"]
        if sym not in cache:
            try:
                cache[sym] = ev.load(f"{a.data}/{sym}.csv")
            except FileNotFoundError:
                cache[sym] = None
        c = cache[sym]
        if not c:
            continue
        t = calendar.timegm(time.strptime(r["time_utc"][:19], "%Y-%m-%d %H:%M:%S")) * 1000
        i0 = bisect.bisect_right([x[0] for x in c], t) - 1
        if i0 < 0 or i0 >= len(c) - 1:
            continue
        sigs.append(dict(t=t, sym=sym, side=1 if r["direction"] == "long" else -1, price=float(r["price"]),
                         lev=ev.LEV.get(r["rule"], 20), i0=i0, c=c))
    sigs.sort(key=lambda s: s["t"])

    def run(s, forced=None):
        return ev.simulate(s["c"], s["i0"], s["side"], s["price"], s["lev"], a.fee, ew, tw, a.trail, forced)

    for s in sigs:
        s["nat"] = run(s)

    def policy(name):
        kept, openp, events = [], defaultdict(list), 0
        for s in sigs:
            opp = [p for p in openp[s["sym"]] if p["side"] != s["side"] and p["nat"]["end"] > s["t"] and p.get("forced") is None]
            if opp:
                events += 1
                if name == "ignore new":
                    continue
                if name == "close old":
                    for p in opp:
                        p["forced"] = (s["t"], s["price"])
            s["forced"] = None
            kept.append(s)
            openp[s["sym"]].append(s)
        rows = []
        for s in kept:
            res = run(s, s.get("forced")) if name == "close old" and s.get("forced") else s["nat"]
            rows.append((s, res))
        for s in sigs:                          # reset for the next policy
            s.pop("forced", None)
        return rows, events

    print(f"{len(sigs)} published signals with candles. Amount {a.amount:g}% per signal.\n")
    print(f"{'policy':12s} {'kept':>5s} {'opposite arrivals':>17s} {'mean ROE':>9s} {'impact':>8s} {'max DD':>7s} {'peak open':>9s} {'peak margin':>11s}")
    for name in ("keep both", "close old", "ignore new"):
        rows, events = policy(name)
        n = len(rows)
        imp = [(res["end"], a.amount * res["qty"] * res["roe"]) for s, res in rows]
        cum = peak = mdd = 0.0
        for _, v in sorted(imp):
            cum += v
            peak = max(peak, cum)
            mdd = max(mdd, peak - cum)
        evs = sorted([(s["t"], 1, a.amount * res["qty"]) for s, res in rows] +
                     [(res["end"], -1, -a.amount * res["qty"]) for s, res in rows])
        o = pk = 0
        m = pm = 0.0
        for _, d, mg in evs:
            o += d
            m += mg
            pk, pm = max(pk, o), max(pm, m)
        print(f"{name:12s} {n:5d} {events:17d} {100 * sum(r['roe'] for _, r in rows) / n:8.1f}% {sum(v for _, v in imp):7.1f}% "
              f"{mdd:6.1f}% {pk:9d} {pm:10.0f}%")


if __name__ == "__main__":
    main()

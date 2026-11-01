#!/usr/bin/env python3
"""Which Cornix-side settings would have done best on the same signals?

  python3 sweep.py ../mygg_flips.csv --data data --since "2026-10-28 17:00" --until "2026-10-31 17:00"

Replays every published signal in the window with many combinations of entry split, target split and stop trailing
(the settings you control in Cornix), using the same simulation as evaluate.py. Prints the combinations ranked by mean
return on the full planned size (margin that never fills counts as idle), with your current setting marked, plus how many days each was positive. Best-in-a-few-days is not
predictive: look for settings that are good on most days, and be suspicious of a win that is mostly one day.
Standard library only.
"""
import argparse, bisect, calendar, csv, itertools, statistics as st, time
from collections import defaultdict
import evaluate as ev

ENTRIES = ["100,0,0,0", "65,15,10,10", "50,25,15,10", "40,30,20,10", "25,25,25,25"]
TARGETS = ["100,0,0,0", "60,20,10,10", "50,30,20,0", "40,30,20,10", "25,25,25,25"]
TRAILS = ["breakeven", "moving"]
CURRENT = ("65,15,10,10", "60,20,10,10", "moving")


def ts(s):
    return calendar.timegm(time.strptime(s, "%Y-%m-%d %H:%M")) * 1000


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("flips")
    ap.add_argument("--data", default="data")
    ap.add_argument("--since")
    ap.add_argument("--until")
    ap.add_argument("--fee", type=float, default=0.0005)
    ap.add_argument("--top", type=int, default=12)
    a = ap.parse_args()
    lo = ts(a.since) if a.since else 0
    hi = ts(a.until) if a.until else 10 ** 15
    sigs, cache = [], {}
    for r in csv.DictReader(open(a.flips)):
        if r.get("published", "1") == "0":
            continue
        t = calendar.timegm(time.strptime(r["time_utc"][:19], "%Y-%m-%d %H:%M:%S")) * 1000
        if not lo <= t < hi:
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
        i0 = bisect.bisect_right([x[0] for x in c], t) - 1
        if 0 <= i0 < len(c) - 1:
            sigs.append(dict(c=c, i0=i0, side=1 if r["direction"] == "long" else -1, price=float(r["price"]),
                             lev=ev.LEV.get(r["rule"], 20), day=r["time_utc"][:10]))
    if not sigs:
        print("no signals in that window with candles")
        return
    print(f"{len(sigs)} signals. Combinations: {len(ENTRIES) * len(TARGETS) * len(TRAILS)}. Return is on the margin of each signal.\n")
    out = []
    for ew_s, tw_s, tr in itertools.product(ENTRIES, TARGETS, TRAILS):
        ew = tuple(float(x) / 100 for x in ew_s.split(","))
        tw = tuple(float(x) / 100 for x in tw_s.split(","))
        res = [(s, ev.simulate(s["c"], s["i0"], s["side"], s["price"], s["lev"], a.fee, ew, tw, tr)) for s in sigs]
        roe = [100 * r["roe"] for _, r in res]                     # on the margin actually used
        full = [100 * r["roe"] * r["qty"] for _, r in res]         # on the full planned size (idle margin counts)
        byday = defaultdict(list)
        for (s, r) in res:
            byday[s["day"]].append(100 * r["roe"] * r["qty"])
        dm = [st.mean(v) for v in byday.values()]
        # normalise by filled share so settings with smaller first entries are comparable on margin used
        out.append(dict(ew=ew_s, tw=tw_s, tr=tr, mean=st.mean(full), used=st.mean(roe), fill=100 * st.mean(r["qty"] for _, r in res),
                        days=f"{sum(1 for x in dm if x > 0)}/{len(dm)}",
                        tp1=100 * sum(1 for _, r in res if r["tp1"]) / len(res),
                        stop=100 * sum(1 for _, r in res if r["reason"] == "stop") / len(res),
                        worst=min(roe)))
    out.sort(key=lambda x: -x["mean"])
    print("Ranked by return on the FULL planned size (an entry that never fills leaves its margin idle).\n")
    print(f"{'rank':>4s} {'entries':>12s} {'targets':>12s} {'trail':>10s} {'full-size':>9s} {'on used':>8s} {'avg fill':>8s} {'days>0':>7s} {'TP1%':>6s} {'stop%':>6s}")
    cur_rank = next(i for i, x in enumerate(out) if (x["ew"], x["tw"], x["tr"]) == CURRENT) + 1
    for i, x in enumerate(out[:a.top], 1):
        mark = "  <- your current setting" if (x["ew"], x["tw"], x["tr"]) == CURRENT else ""
        print(f"{i:4d} {x['ew']:>12s} {x['tw']:>12s} {x['tr']:>10s} {x['mean']:8.1f}% {x['used']:7.1f}% {x['fill']:7.0f}% {x['days']:>7s} {x['tp1']:6.1f} {x['stop']:6.1f}{mark}")
    x = out[cur_rank - 1]
    print(f"\nYour current setting ranks {cur_rank} of {len(out)}: {x['mean']:.1f}% on the full size ({x['used']:.1f}% on margin used), "
          f"average fill {x['fill']:.0f}%, days>0 {x['days']}, TP1 {x['tp1']:.1f}%, stop {x['stop']:.1f}%")
    print("Worst combinations:")
    for x in out[-3:]:
        print(f"     {x['ew']:>12s} {x['tw']:>12s} {x['tr']:>10s} {x['mean']:8.1f}% {x['used']:7.1f}% {x['fill']:7.0f}% {x['days']:>7s}")


if __name__ == "__main__":
    main()

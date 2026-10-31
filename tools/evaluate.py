#!/usr/bin/env python3
"""What would the published signals have made? Replay mygg_flips.csv through the template on real candles.

  python3 evaluate.py ../mygg_flips.csv [--data data] [--amount 5] [--fee 0.0005] [--all]

For every published flip (--all: every logged flip) it builds the signal exactly as the scanner did, then walks
the 15m candles after the post: entries fill when touched (50/25/15/10 of the planned size, entry 1 filled at once),
targets take 65/15/10/10 of the filled size, the stop moves to the average entry after target 1, intrabar order is
pessimistic (adverse moves first). Unresolved trades are closed at the last close. Result per signal is the return on
the margin used; account impact assumes --amount percent of the balance as margin when fully filled.
Not modelled: Cornix margin limits, funding, slippage beyond the fee, many positions open at once.
Run from the tools folder after template_backtest.py fetch for the coins in the log. Standard library only.
"""
import argparse, bisect, calendar, csv, os, sys, time
from collections import defaultdict
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from mygg import template

ENTRY_W = (0.50, 0.25, 0.15, 0.10)
TP_W = (0.65, 0.15, 0.10, 0.10)
LEV = {"MACD Cross": 25, "EMA Cross": 15, "BB": 20}


def load(path):
    with open(path) as f:
        return [(int(r["t"]), float(r["o"]), float(r["h"]), float(r["l"]), float(r["c"])) for r in csv.DictReader(f)]


def simulate(c, i0, side, price, lev, fee, entry_w=ENTRY_W, tp_w=TP_W, trail="breakeven", forced=None):
    """forced = (time_ms, price): close whatever is left at that price when that time arrives (reversal)."""
    sig = template.build(side, price, ladder=True)
    entries, tps, stop = sig["entries"], sig["tps"], sig["stop"]
    qty = entry_w[0]
    avg, max_qty, entered, exited, realized = entries[0], qty, qty, 0.0, 0.0
    filled, hit, be = [True, False, False, False], [False] * 4, False
    reason, end = None, len(c) - 1
    adv = lambda k, p: c[k][3] <= p if side > 0 else c[k][2] >= p
    fav = lambda k, p: c[k][2] >= p if side > 0 else c[k][3] <= p

    def close(q, p):
        nonlocal qty, realized, exited
        realized += q * side * (p - avg) / avg
        exited += q
        qty -= q

    for k in range(i0 + 1, len(c)):
        if forced and c[k][0] + 900000 > forced[0]:
            close(qty, forced[1])
            reason, end = "reversed", k
            break
        for j in (1, 2, 3):
            if not filled[j] and adv(k, entries[j]):
                filled[j] = True
                avg = (avg * qty + entries[j] * entry_w[j]) / (qty + entry_w[j])
                qty += entry_w[j]
                entered += entry_w[j]
                max_qty = max(max_qty, qty)
        if adv(k, stop):
            close(qty, stop)
            reason, end = ("breakeven" if be else "stop"), k
            break
        for j in range(4):
            if not hit[j] and fav(k, tps[j]):
                left = sum(tp_w[m] for m in range(4) if not hit[m])
                close(qty * tp_w[j] / left, tps[j])
                hit[j] = True
                if j == 0:
                    be, stop = True, avg
                elif trail == "moving":
                    stop = tps[j - 1]            # Cornix 'Moving Target': stop follows the previous target
        if qty <= 1e-12:
            reason, end = "tp_all", k
            break
    if not reason:
        reason = "open"
        close(qty, c[-1][4])
    roe = lev * (realized - fee * (entered + exited)) / max_qty
    return {"roe": roe, "reason": reason, "tp1": hit[0], "qty": max_qty, "end": c[end][0]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("flips")
    ap.add_argument("--data", default="data")
    ap.add_argument("--amount", type=float, default=5.0, help="percent of balance as margin per full signal")
    ap.add_argument("--fee", type=float, default=0.0005)
    ap.add_argument("--entry-weights", default="50,25,15,10", help="share of the size per entry, e.g. 65,15,10,10")
    ap.add_argument("--tp-weights", default="65,15,10,10", help="share of the position closed at each target")
    ap.add_argument("--trail", choices=["breakeven", "moving"], default="breakeven",
                    help="after target 1 the stop goes to the average entry; 'moving' also follows each later target")
    ap.add_argument("--all", action="store_true", help="include unpublished flips")
    ap.add_argument("--unpublished", action="store_true", help="only the flips that were suppressed (published = 0)")
    a = ap.parse_args()

    ew = tuple(float(x) / 100 for x in a.entry_weights.split(","))
    tw = tuple(float(x) / 100 for x in a.tp_weights.split(","))
    cache, rows, skipped = {}, [], 0
    for r in csv.DictReader(open(a.flips)):
        is_pub = r.get("published", "1") != "0"
        if a.unpublished and is_pub:
            continue
        if not a.all and not a.unpublished and not is_pub:
            continue
        sym = r["symbol"]
        if sym not in cache:
            try:
                cache[sym] = load(f"{a.data}/{sym}.csv")
            except FileNotFoundError:
                cache[sym] = None
        c = cache[sym]
        if not c:
            skipped += 1
            continue
        t = calendar.timegm(time.strptime(r["time_utc"][:19], "%Y-%m-%d %H:%M:%S")) * 1000
        i0 = bisect.bisect_right([x[0] for x in c], t) - 1
        if i0 < 0 or i0 >= len(c) - 1:
            skipped += 1
            continue
        side = 1 if r["direction"] == "long" else -1
        res = simulate(c, i0, side, float(r["price"]), LEV.get(r["rule"], 20), a.fee, ew, tw, a.trail)
        res.update(sym=sym, rule=r["rule"], side=r["direction"], day=r["time_utc"][:10], t=t,
                   impact=a.amount * res["qty"] * res["roe"])
        rows.append(res)

    def block(title, key):
        g = defaultdict(list)
        for x in rows:
            g[x[key]].append(x)
        print(f"\n{title}")
        print(f"  {'':12s} {'n':>5s} {'TP1%':>6s} {'stop%':>6s} {'BE%':>5s} {'open%':>6s} {'mean ROE':>9s} {'account %':>10s}")
        for k in sorted(g):
            v = g[k]
            n = len(v)
            pct = lambda f: 100 * sum(1 for x in v if f(x)) / n
            print(f"  {str(k):12s} {n:5d} {pct(lambda x: x['tp1']):6.1f} {pct(lambda x: x['reason'] == 'stop'):6.1f} "
                  f"{pct(lambda x: x['reason'] == 'breakeven'):5.1f} {pct(lambda x: x['reason'] == 'open'):6.1f} "
                  f"{100 * sum(x['roe'] for x in v) / n:8.1f}% {sum(x['impact'] for x in v):9.1f}%")

    print(f"{len(rows)} signals simulated ({skipped} skipped: no candles or too recent), amount {a.amount}% per signal, fee {a.fee:.2%}/side, "
          f"entries {a.entry_weights}, targets {a.tp_weights}, trail {a.trail}")
    if not rows:
        return
    block("By rule", "rule")
    block("By direction", "side")
    block("By day (UTC)", "day")
    cum, peak, mdd = 0.0, 0.0, 0.0
    for x in sorted(rows, key=lambda x: x["end"]):
        cum += x["impact"]
        peak = max(peak, cum)
        mdd = max(mdd, peak - cum)
    print(f"\nTotal account impact {cum:+.1f}% (not compounded, no margin limit), largest drawdown {mdd:.1f}%")
    print("\nWorst 8 signals (return on margin):")
    for x in sorted(rows, key=lambda x: x["roe"])[:8]:
        print(f"  {x['day']} {x['sym']:10s} {x['rule']:11s} {x['side']:5s} {x['reason']:9s} {100 * x['roe']:+7.1f}%")
    by_coin = defaultdict(float)
    for x in rows:
        by_coin[x["sym"]] += x["impact"]
    worst = sorted(by_coin.items(), key=lambda kv: kv[1])[:5]
    print("Worst coins by account impact: " + ", ".join(f"{k} {v:+.1f}%" for k, v in worst))


if __name__ == "__main__":
    main()

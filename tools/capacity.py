#!/usr/bin/env python3
"""What could a real account have held? Replay a Cornix export with a limit on simultaneous positions and fees.

  python3 capacity.py export.csv [--margin 1000] [--fee 0.0005] [--caps 10 20 30 50 100]

Each signal in the export used a fixed margin (--margin: 5% of the 20,000 starting balance = 1,000 reproduced the paper
account within 2%). Signals are taken first come first served; one that arrives while --cap positions are already open
is skipped, as a real account without enough margin would skip it. Profit is the export's profit % x filled share x
margin. Fees are leverage x --fee x 2 sides x margin x filled share (taker fee on every order; entries and targets as
limit orders would pay less). Open trades are held to the end of the file at their last profit. No slippage, no funding.
Standard library only.
"""
import argparse, csv, datetime as dt, heapq, re


def mins(s):
    t = {"day": 1440, "hr": 60, "min": 1}
    return sum(int(n) * t[u] for n, u in re.findall(r"(\d+)\s*(day|hr|min)", s))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("export")
    ap.add_argument("--margin", type=float, default=1000.0)
    ap.add_argument("--fee", type=float, default=0.0005)
    ap.add_argument("--caps", type=int, nargs="*", default=[10, 20, 30, 50, 100])
    ap.add_argument("--start", type=float, default=20000.0)
    a = ap.parse_args()
    rows = []
    for r in csv.DictReader(open(a.export, newline="")):
        t0 = dt.datetime.strptime(r["Date"], "%Y-%m-%d %H:%M:%S")
        f = float(r["Entry Targets % Filled"] or 0) / 100
        lev = float(re.search(r"([\d.]+)X", r["Leverage"]).group(1))
        is_open = r["Status"].startswith(("Buy", "Sell"))
        rows.append(dict(t0=t0, t1=(t0 + dt.timedelta(days=3650)) if is_open else t0 + dt.timedelta(minutes=mins(r["Duration"])),
                         gross=a.margin * float(r["Signal Gained Profit %"]) / 100 * f, fee=a.margin * lev * a.fee * 2 * f))
    rows.sort(key=lambda r: r["t0"])
    print(f"{len(rows)} signals, {rows[0]['t0']} to {rows[-1]['t0']}. Margin {a.margin:,.0f} per trade, fee {a.fee:.2%} a side, start {a.start:,.0f}.\n")
    print(f"{'max open':>9s} {'taken':>6s} {'gross':>10s} {'fees':>9s} {'net':>10s} {'final':>10s} {'return':>8s}")
    for cap in a.caps + [10 ** 9]:
        h, taken = [], []
        for r in rows:
            while h and h[0] <= r["t0"]:
                heapq.heappop(h)
            if len(h) < cap:
                heapq.heappush(h, r["t1"])
                taken.append(r)
        g, fees = sum(r["gross"] for r in taken), sum(r["fee"] for r in taken)
        print(f"{('all' if cap >= 10 ** 9 else cap):>9} {len(taken):6d} {g:10,.0f} {fees:9,.0f} {g - fees:10,.0f} {a.start + g - fees:10,.0f} {100 * (g - fees) / a.start:7.0f}%")


if __name__ == "__main__":
    main()

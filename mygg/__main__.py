"""python -m mygg {validate,replay,scan} ..."""
import argparse
import csv
import datetime as dt
import glob
import os

from . import live, replay
from .rules import BBBreak, EMACross, MACDCross

RULES = {"macd": MACDCross, "ema": EMACross, "bb": BBBreak}


def main():
    ap = argparse.ArgumentParser(prog="mygg")
    sub = ap.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("validate", help="check real signals against the rules (symbol,time_utc,direction,entry[,rule])")
    v.add_argument("signals")
    v.add_argument("--data", default="data")
    v.add_argument("--window", type=int, default=replay.WINDOW, help="closed candles fed to the indicators")

    f = sub.add_parser("fit", help="try several history windows to see which reproduces the real signals")
    f.add_argument("signals")
    f.add_argument("--data", default="data")
    f.add_argument("--windows", type=int, nargs="*", default=[40, 50, 60, 80, 100, 150, 200, 300, 500, 1000])

    r = sub.add_parser("replay", help="list every rule flip in stored candles")
    r.add_argument("--data", default="data")
    r.add_argument("--out", default="replay.csv")
    r.add_argument("--since", help='UTC, e.g. "2026-10-28 00:00"')

    s = sub.add_parser("scan", help="live paper scanner (needs internet access to Binance)")
    s.add_argument("--symbols", nargs="*", default=live.DEFAULT_WATCHLIST)
    s.add_argument("--interval", type=int, default=20)
    s.add_argument("--once", action="store_true")
    s.add_argument("--rules", nargs="*", choices=sorted(RULES), default=["macd", "ema"],
                   help="bb is an unconfirmed placeholder, so it is off by default")
    s.add_argument("--log", default="mygg_flips.csv")
    s.add_argument("--cooldown", type=int, default=4,
                   help="candles before the same coin, rule and direction is published again (all flips are still logged)")

    a = ap.parse_args()
    if a.cmd == "validate":
        replay.validate(a.signals, a.data, window=a.window)
    elif a.cmd == "fit":
        replay.fit(a.signals, a.data, windows=a.windows)
    elif a.cmd == "replay":
        since = int(dt.datetime.strptime(a.since, "%Y-%m-%d %H:%M").replace(tzinfo=dt.timezone.utc).timestamp() * 1000) if a.since else 0
        rows = []
        for path in sorted(glob.glob(f"{a.data}/*.csv")):
            sym = os.path.basename(path)[:-4]
            rows += [x for x in replay.replay_symbol(sym, replay.load(path)) if x["time"] >= since]
        rows.sort(key=lambda x: x["time"])
        with open(a.out, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["time_utc", "symbol", "rule", "direction", "price"])
            for x in rows:
                w.writerow([dt.datetime.fromtimestamp(x["time"] / 1000, dt.timezone.utc).strftime("%Y-%m-%d %H:%M"),
                            x["symbol"], x["rule"], "long" if x["side"] > 0 else "short", x["price"]])
        print(f"{len(rows)} rule flips written to {a.out}")
    else:
        live.scan([x[:-4] if x.endswith("USDT") else x for x in a.symbols], a.interval, log=a.log,
                  rules=[RULES[r]() for r in a.rules], once=a.once, cooldown=a.cooldown)


if __name__ == "__main__":
    main()

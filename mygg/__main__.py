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
    s.add_argument("--symbols", nargs="*", default=live.DEFAULT_WATCHLIST, help="replace the whole watchlist")
    s.add_argument("--add", nargs="*", default=[], help="extra coins on top of the watchlist, e.g. --add NEAR FIL TIA")
    s.add_argument("--interval", type=int, default=20)
    s.add_argument("--once", action="store_true")
    s.add_argument("--rules", nargs="*", choices=sorted(RULES), default=["macd", "ema"],
                   help="bb is an unconfirmed placeholder, so it is off by default")
    s.add_argument("--log", default="mygg_flips.csv")
    s.add_argument("--avoid-hours", nargs="*", default=[],
                   help='UTC hours with no new signals, e.g. --avoid-hours 5-8 21-24 (start inclusive, end exclusive)')
    s.add_argument("--cooldown-scope", choices=["rule", "dir", "coin"], default="rule",
                   help="what the cooldown applies to: coin+rule+direction (default), coin+direction, or the whole coin")
    s.add_argument("--max-per-hour", type=int, default=0, help="cap on published signals per UTC hour (0 = no cap)")
    s.add_argument("--rounds", action="store_true",
                   help="post like the source: only in rounds every 3-7 h, the flips active then, one per coin")
    s.add_argument("--round-gap", type=float, nargs=2, default=[3.0, 7.0], metavar=("MIN_H", "MAX_H"),
                   help="hours between rounds, random within this range (default 3 7)")
    s.add_argument("--round-max", type=int, default=9, help="most signals in one round (default 9)")
    s.add_argument("--round-coins", nargs="*", default=None,
                   help="coins allowed in rounds (default: the 35 coins the source uses); 'all' = the whole watchlist")
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
        coins = []
        for x in list(a.symbols) + list(a.add):
            x = (x[:-4] if x.upper().endswith("USDT") else x).upper()
            if x not in coins:
                coins.append(x)
        live.scan(coins, a.interval, log=a.log,
                  rules=[RULES[r]() for r in a.rules], once=a.once, cooldown=a.cooldown,
                  cooldown_scope=a.cooldown_scope, max_per_hour=a.max_per_hour,
                  avoid_hours=live.parse_hours(a.avoid_hours), rounds=a.rounds, round_gap=tuple(a.round_gap),
                  round_max=a.round_max,
                  round_coins=(coins if a.round_coins == ["all"] else
                               [x.upper().removesuffix("USDT") for x in a.round_coins] if a.round_coins else None))


if __name__ == "__main__":
    main()

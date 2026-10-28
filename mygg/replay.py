"""Replay rules over stored 15m candles and compare with real signals.

A candle is treated as one forming candle: a bullish flip occurs if the rule's state at the candle's
high differs from the state at the last close, a bearish flip if it differs at the low. For MACD and
EMA rules the exact price of the flip is solved (trigger_price), which is the live price M.
"""
import csv
import datetime as dt

from . import template
from .rules import DEFAULT_RULES

WINDOW = 300          # closes fed to the indicators; ample for EMA convergence


def load(path):
    with open(path) as f:
        return [(int(r["t"]), float(r["o"]), float(r["h"]), float(r["l"]), float(r["c"]))
                for r in csv.DictReader(f)]


def replay_symbol(symbol, candles, rules=DEFAULT_RULES, start=100):
    closes = [c[4] for c in candles]
    out = []
    for i in range(start, len(candles)):
        closed = closes[max(0, i - WINDOW):i]
        t, _, hi, lo, _ = candles[i]
        for rule in rules:
            for side, live in ((1, hi), (-1, lo)):
                if rule.flip(closed, live) != side:
                    continue
                trig = rule.trigger_price(closed)
                price = trig if trig is not None and lo <= trig <= hi else live
                out.append({"symbol": symbol, "time": t, "rule": rule.name, "side": side, "price": price})
    return out


def validate(signals_path, data_dir="data", rules=DEFAULT_RULES):
    """Real signals (symbol,time_utc,direction,entry[,rule]) vs what the rules say at that moment."""
    rows = list(csv.DictReader(open(signals_path)))
    byname = {r.name: r for r in rules}
    hits, totals, errs = {}, {}, {}
    print(f"{'symbol':10s} {'time_utc':16s} {'side':5s} {'rule':11s} flip  live-price M vs solved trigger")
    for row in rows:
        candles = load(f"{data_dir}/{row['symbol']}.csv")
        t = int(dt.datetime.strptime(row["time_utc"], "%Y-%m-%d %H:%M")
                .replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
        i = max(k for k in range(len(candles)) if candles[k][0] <= t)
        side = 1 if row["direction"].strip().lower() == "long" else -1
        m = float(row["entry"]) / (1 + side * template.ZONE)     # entry 1 is 0.15% beyond the live price
        closed = [c[4] for c in candles[max(0, i - WINDOW):i]]
        names = [row["rule"]] if row.get("rule") else list(byname)
        for name in names:
            rule = byname[name]
            ok = rule.flip(closed, m) == side
            trig = rule.trigger_price(closed)
            note = f"M {m:.6g} vs {trig:.6g} ({(m / trig - 1) * 1e4:+.0f} bp)" if trig else f"M {m:.6g}"
            print(f"{row['symbol']:10s} {row['time_utc']:16s} {row['direction']:5s} {name:11s} {'YES' if ok else 'no ':4s}  {note}")
            totals[name] = totals.get(name, 0) + 1
            hits[name] = hits.get(name, 0) + ok
    print("\nPer rule: " + ", ".join(f"{n} {hits[n]}/{totals[n]}" for n in totals))

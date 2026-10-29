#!/usr/bin/env python3
"""How often do two rules flip on the same coin, candle and direction?

Reads the file written by `python3 -m mygg replay` (time_utc,symbol,rule,direction,price). The original bot's
batches never repeat a coin. If a coin often has both a MACD and an EMA flip in one candle, that absence means
the bot publishes one signal per coin per round. Standard library only.
"""
import csv, sys
from collections import defaultdict

groups = defaultdict(set)
for r in csv.DictReader(open(sys.argv[1] if len(sys.argv) > 1 else "replay.csv")):
    groups[(r["time_utc"], r["symbol"], r["direction"])].add(r["rule"])
per_rule = defaultdict(int)
both = 0
for rules in groups.values():
    for r in rules:
        per_rule[r] += 1
    both += len(rules) > 1
print(f"{len(groups)} coin-candle-direction flips; per rule: " + ", ".join(f"{k} {v}" for k, v in sorted(per_rule.items())))
print(f"{both} of them ({both / max(1, len(groups)):.1%}) have two rules flipping together")
macd = per_rule.get("MACD Cross", 0)
print(f"{both / max(1, macd):.1%} of MACD flips coincide with another rule's flip")

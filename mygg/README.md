# mygg

A paper-trading signal scanner built from rules inferred from a set of observed signals.
It posts nothing and places no orders: `scan` prints and logs signals only.

## What is modelled
| Strategy | Rule (15m chart, evaluated on the forming candle) | Leverage | Confidence |
|---|---|---|---|
| MACD Cross | MACD(12,26,9) histogram changes sign | 25x | high |
| EMA Cross | EMA9 crosses EMA21 | 15x | moderate |
| BB | price beyond Bollinger(20, 2) of the prior closes | 20x | low, placeholder |

Levels (`template.py`) are fixed percentages of the live price M, fitted to the originals:
zone M x (1 -/+ 0.15%), targets +0.75 / 1.7 / 3.2 / 5.8 %, stop 5 % against the trade.

## Unknown
Which flips are actually published. On 28 Oct 15:12 UTC five coins flipped bullish and four had
signals, so some filter exists (watchlist, cooldown, size). `replay` lists every raw flip so the
published signals can be compared against it.

## Use
    python3 -m unittest discover -s tests
    python3 -m mygg validate signals.csv --data data   # real signals vs the rules
    python3 -m mygg replay --data data --out replay.csv
    python3 -m mygg scan --once                        # needs access to Binance public data

`signals.csv` columns: `symbol,time_utc,direction,entry[,rule]` where entry is entry 1 as published.
Candles come from `tools/template_backtest.py fetch` (`data/<SYMBOL>.csv`).

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
    python3 -m mygg scan --rules macd ema              # live paper scan; needs access to Binance public data

`signals.csv` columns: `symbol,time_utc,direction,entry[,rule]` where entry is entry 1 as published.
Candles come from `tools/template_backtest.py fetch` (`data/<SYMBOL>.csv`).

## Where signals go
`scan` prints to the terminal (or `scan.out` under nohup) and appends to `mygg_flips.csv`.
To also get them in your own private Telegram chat, create a bot with @BotFather, send it a message,
and put the token and your chat id in a file kept out of git (several chats: separate the ids with commas,
`MYGG_TG_CHAT=-1001111,-1002222`; each needs the bot as an admin):

    printf 'MYGG_TG_TOKEN=...\nMYGG_TG_CHAT=...\n' > ~/.mygg_env && chmod 600 ~/.mygg_env
    set -a; . ~/.mygg_env; set +a
    nohup python3 -m mygg scan --rules macd ema > scan.out 2>&1 &

## Repeats
Every flip is logged to `mygg_flips.csv` (column `published`). A signal is only published (printed and sent)
if the same coin, rule and direction was not published within `--cooldown` candles (default 4, a guess), and a
restart never repeats a flip already logged in the same candle.

## Rounds mode (like the source channel)

The source does not post flips as they happen. It posts in rounds, 30-34 times a week (gaps of 3-7 h), listing the
flips that are active at that moment on its own coins, one per coin. `--rounds` does the same:

    ./tools/run_scanner.sh --rounds --rules macd ema bb --add NEAR FIL TIA HBAR LDO ALGO ETC BCH TON TAO

- flips are still logged as they happen (`published` 0) so the continuous version can be compared later;
- a round is posted every 3-7 h (random, `--round-gap MIN MAX`); the next time is kept in `mygg_rounds.json`
  next to the log, so a restart does not reset it;
- a round posts the flips active at that moment, on the 34 coins the source uses (`--round-coins`, or
  `--round-coins all`), one per coin (MACD, then EMA, then BB), skipping coins posted in the previous round,
  at most `--round-max` (9), a second apart;
- `--cooldown` settings do not apply; `--avoid-hours` still skips a round that falls in a blocked hour.

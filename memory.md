# mygg project memory

Last updated: 2026-10-29. Checkpoint tag: `checkpoint-2026-10-29` (branch `claude/peaceful-wozniak-o9b7ec`).
Read this first when resuming.

## Goal and ground rules
- Work out how GG-SHOT's Telegram signals are generated (seen through the original bot and relayed in other
  channels, one of which re-labels them "RAPID SCALPERS"), and build `mygg`, a paper-trading scanner that
  reproduces them. Purpose: measure how close the analysis gets.
- Agreed limits: personal research, paper only. The owner chose the message header "SABBOT REAL"; the account
  behind it is still paper. No GG-SHOT or relay branding, no redistributing the provider's signals, no selling.
  The relay channels (GG_Shot_Leak and the promo links in it) look like unauthorised redistribution of a paid service.
- The owner's Cornix account attached to their private channel is a **paper** account (confirmed). Keep it so.
- Secrets (`MYGG_TG_TOKEN`, `MYGG_TG_CHAT`) live only in `~/.mygg_env` on the owner's instance. Never ask for
  or store them in chat or the repo.

## Environment
- Repo `traderhydr/mygg`, branch `claude/peaceful-wozniak-o9b7ec`. Skill `reverse-engineer-anything` (from
  morluto/rea, instructions only) is in `.claude/skills/`.
- The cloud sandbox cannot reach Binance, Telegram, t.me or ggshot.com. The owner's Debian instance
  (`instance-20261028-150121`) can reach Binance and Hyperliquid public APIs. The owner runs commands there
  and pastes output. Owner's local time is UTC+5 (local = UTC + 5h).
- Scanner on the instance: `python3 -m mygg scan --rules macd ema` (log `mygg_flips.csv`, output `scan.out`).
  Keep-alive wrapper that restarts it if it exits: `nohup ./tools/run_scanner.sh &`. Manual restart:
  `pkill -f "mygg scan"; set -a; . ~/.mygg_env; set +a; nohup python3 -m mygg scan --rules macd ema > scan.out 2>&1 &`

## Current scanner behaviour (frozen for the month-long run)
- Rules: MACD(12,26,9) histogram flip (25x), EMA9/EMA21 flip (15x). Bollinger rule exists but is off (unconfirmed).
- Checked each 20 s on the forming 15m candle with Binance public last price; watchlist in `mygg/live.py`.
- Every raw flip is logged to `mygg_flips.csv` with `published` 0/1. A flip is published (printed + sent to the
  owner's private channel, where Cornix paper-trades it) only if: not already logged this candle (restart-safe), the
  coin has no other published signal this candle (the original's batches never repeat a coin; a guess), and the same
  coin/rule/direction was not published in the last 4 candles (a guess).
- Layout: header "⚡ SABBOT REAL ⚡", Pair, Direction, `Leverage: Cross NX`, four Entries, four Take Profits, Stop
  Loss. No exchange line, no disclaimer. Levels from `mygg/template.py`.
- Old log `mygg_signals.csv` (before the cooldown and layout changes) is kept for reference.

## Repo layout
- `mygg/`: `indicators.py`, `rules.py`, `template.py` (levels + `fmt`), `replay.py` (`validate`, `fit`, replay),
  `live.py` (scanner, Telegram send, layout), `__main__.py`. README in `mygg/README.md`.
- `tests/test_mygg.py`: 10 tests (template vs real signals, rule maths, layout, restart safety, one signal per
  coin per candle, token never printed). Run `python3 -m unittest discover -s tests`.
- `tools/`, all stdlib: `template_backtest.py` (fetch candles, baseline, score, flip, rule), `macd_check.py`,
  `macd_live.py`, `ema_live.py`, `bb_check.py`, `pine_check.py`, `scan_flips.py`, `find_time.py`, `trace.py`,
  `explain.py` (features of posted vs skipped flips), `compare.py` (scanner vs the original's posts),
  `overlap.py` (how often MACD and EMA flip together), `fetch_hyperliquid.py`, `run_scanner.sh`.
  Candle CSVs: `tools/data/<SYMBOL>.csv` (t,o,h,l,c,v).
- Notes: Binance futures uses `1000PEPEUSDT`-style names for PEPE/SHIB/FLOKI/BONK. Hyperliquid names them `kPEPE`
  etc. and does not list GRT.

## Confirmed findings
1. **Level template** (fits original signals to the last digit). With M = live price: entry zone
   M x (1 -/+ 0.15%); targets M x (1 +/- 0.75, 1.7, 3.2, 5.8 %); stop M x (1 -/+ 5 %). Long entry 1 is the top of
   the zone (0.15% above market), short entry 1 the bottom. Relay posts add entries 3 and 4 at 2.575% and 4.273% of
   M beyond the live price. Prices are exchange-tick rounded.
2. **Strategies and leverage** (about 40+ signals, no exceptions): MACD Cross 25x, BB Breakout / BB Breakdown 20x,
   EMA Cross 15x. A separate "15m | Short-Term" desk (SOL example, "Desk: #Hyper") uses ATR-based levels:
   targets about 1.5 / 3 / 4.5 / 9 x ATR, stop about 6 x ATR.
3. **Triggers** (15m chart, evaluated on the forming candle with the live price):
   - MACD Cross: MACD(12,26,9) histogram changes sign. Matches 7 of 7 known signals (longs and shorts).
   - EMA Cross: EMA9 vs EMA21 crosses. 3 of 4 on Hyperliquid candles (2 of 4 on Binance); the misses are 1-2 bp
     margins that depend on the price feed. ORDI still misses by 12 bp.
   - BB Breakout/Breakdown: Bollinger breakout. ENA fits n=20, 2 sd (z 2.8, band width at the 2nd percentile); the
     15:12 batch of 4 does not fit n>=20. Parameters unconfirmed.
4. **Signals post after the flip**: the live price M sits 11-93 bp beyond the exact trigger price for longs,
   so posts lag the flip by minutes. Flips are probably latched within the candle.
5. **Batches**: the Signal ID restarts at 001 for every scan round and all signals of a round fire together
   (often one market-wide move). Order within a round follows a fixed watchlist order. No coin appears twice in
   a batch (about 14 batches, 100 signals).
6. **Commentary text is random template filler** (shorts say "bullish posture", longs say "bearish"). No information.
7. **Pinned Pine script ("GG-SHOT" strategy)** is a Bollinger-trend-line strategy with ATR targets and
   per-coin presets. It does not reproduce the MACD/EMA/BB-fixed-percentage signals (checked at six signal times).
8. **Relay channels only show wins**: about 150 result messages, zero stop-loss / breakeven messages. Do not use
   them for win rates. Use Cornix paper results or the exchange history instead.
9. **Random-entry baseline** (this template, 15 coins, 30 days to 28 Oct, a down-trending month): TP1 reached about
   90%, stopped out about 10%, average win +16%, average loss about -107% of margin at 25x, break-even win rate
   about 87%. Long-only was about break-even, short-only positive. The high TP1 rate is built into the template.
10. **Cornix settings of the owner**: entry weights 50/25/15/10, TP split 65/15/10/10, breakeven after TP1. They
    reproduce reported average entries and profits to within about 0.05% price (fill slippage).

## Known signal rows (UTC)
| Signal | Time | Rule | Result in `validate` |
|---|---|---|---|
| DOT long, entry 1.009 | 2026-10-26 21:55 | MACD | flip |
| PYTH 0.07169, STRK 0.04683, WLD 0.43405, ARB 0.16707 (long) | 2026-10-28 15:12 | MACD | flip |
| ARB long 0.18646, GRT short 0.02737 | 2026-10-10 05:38 | MACD | flip (GRT 3 bp rounding) |
| ATOM long 2.035, IMX short 0.19914 | 2026-10-10 05:38 | EMA | flip |
| SUI long 0.94001, ORDI short 3.679 | 2026-10-28 08:14 | EMA | SUI flips on Hyperliquid, ORDI misses |
| ENA long 0.20852 | 2026-10-28 08:14 | BB | not a MACD/EMA flip (control) |
Entry value is entry 1 as published; `validate` derives M from it.

## Open questions
- **The filter.** Not every flip is published. APT flipped bullish at 28 Oct 15:12 with no signal. The scanner fired an
  XLM MACD short (pre-layout-change) that the original bot did not post to the owner. Candidates: per-user coin or
  strategy settings, a watchlist, a minimum histogram size, a MACD-line side-of-zero condition, a trend or volatility
  filter (TRX whipsawed long/short/long in 90 minutes on 29 Oct). Use `tools/explain.py` with `posted=1/0` rows.
- BB rule parameters; the ATR "Short-Term" desk's trigger; the exact data feed (GRT is signalled but absent on
  Hyperliquid); the posting delay distribution.
- Timestamps for the 14 relay batches (A-N); only batch E (10 Oct 05:38 UTC, ATOM) is known.
- Not yet answered: which of the 29 Oct flips (TRX 19:18 long, ENA 19:30 short, POL 19:30 long, TRX 20:30 short,
  TRX 20:48 long) the original bot also posted.

## Month-long evaluation (started 2026-10-29, owner's decision)
The owner reports the paper trades look highly accurate and profitable so far (early, unverified, no stop data yet
in this record) and will run the frozen set-up for a month before deciding next steps.
- **Freeze:** do not change rules, template, cooldown, header or watchlist during the month; note the date of any
  forced fix (the checkpoint tag is the reference version). Do not move Cornix to a live account.
- **Keep:** `mygg_flips.csv` (never delete), `scan.out`, the Cornix paper history (export the channel weekly as JSON),
  and optionally `original.csv` (time, symbol, direction, rule of the original bot's posts) for `tools/compare.py`.
- **Report at the end, in this order:** (1) published signals and independent clusters (signals within 30 minutes
  count as one market event); (2) TP1 rate, TP2+ rate, breakeven exits, **stop-outs**; (3) paper return and **maximum
  drawdown** at the owner's sizing; (4) expectancy per signal after fees (0.05% a side) and funding, which Cornix
  paper does not charge; (5) the same-month random-entry baseline from `template_backtest.py baseline`.
- **How to read it:** a TP1 rate of 87-93% is expected from this template even for random entries, so accuracy only
  counts when stop-outs and drawdown are included and the result beats the same-month baseline. One month is one
  market regime; a trending month flatters one direction. Need roughly 100 independent clusters to say much.

## Resume checklist
1. `git pull`, run the tests, read this file.
2. Check the scanner (`pgrep -f "mygg scan"`, `tail scan.out`, `tail mygg_flips.csv`).
3. Get from the owner: `mygg_flips.csv`, Cornix paper messages, `original.csv`, the XLM line from `mygg_signals.csv`,
   batch timestamps.
4. Run `compare.py`, `explain.py`, `overlap.py`; then the end-of-month report above.

## Cautions
- Results come from about a dozen validated signals and a 30-day window. Treat stated win rates as unverified.
- The template risks more than the margin at a stop (5% x 15-25x). The owner must not move Cornix to a live account
  on this evidence.

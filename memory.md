# mygg project memory

Last updated: 2026-10-29. Checkpoint commit: `075aaf6` on branch `claude/peaceful-wozniak-o9b7ec` (a git tag could not be
pushed from the cloud session; on the instance run `git tag checkpoint-2026-10-29 075aaf6` if you want one).
Read this first when resuming.

## Goal and ground rules
- Work out how GG-SHOT's Telegram signals are generated (seen through the original bot and relayed in other
  channels, one of which re-labels them "RAPID SCALPERS"), and build `mygg`, a paper-trading scanner that
  reproduces them. Purpose: measure how close the analysis gets.
- Agreed limits: personal research, paper only. The owner chose the message header "SABBOT REAL"; the account
  behind it is still paper. No GG-SHOT or relay branding, no redistributing the provider's signals, no selling.
  The relay channels (GG_Shot_Leak and the promo links in it) look like unauthorised redistribution of a paid service.
- The owner's Cornix account attached to their private channel is a **paper** account (confirmed). Keep it so.
- Secrets (`MYGG_TG_TOKEN`, `MYGG_TG_CHAT`; the chat variable may list several ids separated by commas, added
  2026-10-29, delivery only, no effect on the rules) live only in `~/.mygg_env` on the owner's instance. Never ask for
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
- Layout: header "⚡ SABBOT REAL ⚡", a `Strategy:` line (MACD Cross / EMA Cross; added 2026-10-31, cosmetic), Pair, Direction, `Leverage: Cross NX`, four Entries, four Take Profits, Stop
  Loss. No exchange line, no disclaimer. Levels from `mygg/template.py`.
- Old log `mygg_signals.csv` (before the cooldown and layout changes) is kept for reference.

- 2026-10-29: a heartbeat file (`mygg_heartbeat`) and `tools/status.sh` were added for monitoring. Neither changes a signal.

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
  forced fix (commit `075aaf6` is the reference version). Do not move Cornix to a live account.
- **Keep:** `mygg_flips.csv` (never delete), `scan.out`, the Cornix paper history (export the channel weekly as JSON),
  and optionally `original.csv` (time, symbol, direction, rule of the original bot's posts) for `tools/compare.py`.
- **Report at the end, in this order:** (1) published signals and independent clusters (signals within 30 minutes
  count as one market event); (2) TP1 rate, TP2+ rate, breakeven exits, **stop-outs**; (3) paper return and **maximum
  drawdown** at the owner's sizing; (4) expectancy per signal after fees (0.05% a side) and funding, which Cornix
  paper does not charge; (5) the same-month random-entry baseline from `template_backtest.py baseline`.
- **How to read it:** a TP1 rate of 87-93% is expected from this template even for random entries, so accuracy only
  counts when stop-outs and drawdown are included and the result beats the same-month baseline. One month is one
  market regime; a trending month flatters one direction. Need roughly 100 independent clusters to say much.

## Volume warning (found 2026-10-29)
`status.sh` showed 361 flips logged and 282 published in about 21 hours of 29 Oct UTC (about 13 published per hour,
around 300 a day over ~39 coins). The original bot very probably publishes far fewer. The month-long run therefore
tests a much more active version of the rules than the original. Open decision for the owner: accept it as a test
of the raw rules, or add a volume filter before the freeze (unknown what the original filters on). Ask the owner how
many signals the original bot sent on a typical day, and look at per-hour and per-coin counts in `mygg_flips.csv`.
Also check Cornix's concurrent-trade limits: hundreds of 15-25x positions on one paper balance is not realistic.
**Decision (owner, 2026-10-29): keep it simple, change nothing, run the month as is.** So the month measures the
raw MACD/EMA rules at about 13 published signals an hour, not the original's filtered feed. Read the final report
with that in mind; the original's own volume is still unknown.

## Repeats and stacking (measured 2026-10-31, `tools/repeats.py`)
1030 published signals in 28-31 Oct: 56% repeat the same coin and direction within 4 h, 65% opened while an earlier
position on that coin and direction was still open (deepest: ETH long x10, ETH short x10, BTC short x10). Repeats do not
perform worse than first signals (TP1 81% both, mean return about 4% both). Peak 208 positions open at once, tying up
about 750% of the balance at 5% each, so Cornix cannot take every signal: its paper result depends on its amount per
signal and concurrent-trade limit. Owner to report those settings; the month-end read must account for them.

## Volume limits (added 2026-10-31, optional flags, defaults unchanged)
`python3 -m mygg scan` now accepts `--cooldown N` (candles), `--cooldown-scope rule|dir|coin` and `--max-per-hour N`;
`tools/run_scanner.sh` passes extra options through. `tools/whatif.py` compared limits on 2.6 days of flips (1433 logged):
per-signal quality barely changes (TP1 76-85%, stops 6-8.5%), so limits reduce exposure, not edge. Current set-up: 394
signals a day, peak 167 open, 662% margin at 5% each, drawdown 92%. "4h per coin+direction, max 3 an hour": 66 a day,
peak 29 open, 116% margin, drawdown 25%. Max 6 an hour: 123 a day, peak 52, 204%, drawdown 28%. Totals in impact are noise.
When the owner applies a limit, record the date here: before that date = unrestricted period, after = limited period.

## Cornix export seen 2026-10-31 (chat "Botbac", 232 signals, 29 Oct 23:30 to 31 Oct 09:10 UTC)
Active signals only: 180 open, 46 with some targets, 6 all targets; no stopped or closed statuses, so stop-outs and
breakeven exits are missing and totals are biased upward. Leverage 25x (MACD) 155, 15x (EMA) 77. Cornix allows several
trades on one pair (ETH long x11). 8-10 exchange accounts per signal. Active trades younger than 6 h are mostly
underwater (mean -5%); the worst are 25x longs at -45% to -83% after 7-22 h (INJ, TRX x3, FET, ONDO, DOT, LTC), close to
their stops. Shorts are doing better than longs in this window. Tool: `tools/cornix_report.py <csv ...>`; ask the owner
for the closed/stopped signals export as well.

## Limited period (owner decision 2026-10-31)
Owner chose a 4-hour cooldown per coin and direction, any rule, no hourly cap, opposite directions still allowed:
`./tools/run_scanner.sh --cooldown 16 --cooldown-scope dir`. Reason: the Cornix export showed 89% of open trades
stacked on the same coin and direction (ETH long x11, ETH short x10, BTC long x8). Start time: 2026-10-31 14:51:52 UTC (the owner's restart). At the same restart:
PEPE/SHIB/FLOKI/BONK (1000x contracts) and 10 extra coins (NEAR FIL TIA HBAR LDO ALGO ETC BCH TON TAO via `--add`) were added, so the
limited period also has a 52-coin watchlist. Command: `./tools/run_scanner.sh --cooldown 16 --cooldown-scope dir --add NEAR FIL TIA HBAR LDO ALGO ETC BCH TON TAO`.
At that moment 421 flips were logged and 222 published for 31 Oct UTC so far. Everything logged before it is the unrestricted period. Positions already
open are not closed by this.

## Cornix full export seen 2026-10-31 (1072 signals, 28 Oct 17:32 to 31 Oct 09:15 UTC, chat "Botbac")
Includes closed trades. Status: Partial Targets Achieved 493 (mean +10.7%), Cancelled 270 (mean +9.7%), All Targets
Achieved 119 (mean +63.9%), still open 181 (mean +1.3%), Stopped Out only 9 (mean -71%). Closed trades 891: winners 763 (avg
+24.7%), losers 121 (avg -32.8%). 232 of the 270 cancellations ended within 2.5 min of an OPPOSITE signal on the same
coin (0 with a same-direction signal): the owner's Cornix closes the old trade when a reverse signal arrives. Cancelled
before any target: 119 trades, mean -24.5%, which is how losses are realised, far smaller than a stop-out (-110%).
So Cornix's real result is much better than the evaluator model (mean +14% per signal vs +3-4%); likely reasons: the
reversal exit, moving-target trailing, paper fills at signal prices. Signal-level profit is per signal margin; no
balance column, so account change still unknown. Do not block opposite signals (`--cooldown-scope coin`): they act as
the loss limiter. `tools/cornix_report.py` handles these exports.

## Per-coin results (Cornix full export, 1072 signals, 37 coins, 28-31 Oct)
Mean profit per signal ranges from +24.8% (RENDER) to +3.6% (ETH, 42 signals, 21 still open). A permutation test says the
spread between coins is no larger than chance (p about 0.89), so no coin is reliably better; do not prune the watchlist
on this. Coins with the most cancel-losses/stops: POL 10, TRX 8, KAS 6, LTC 6, OP 7. Recheck on the month's data,
splitting first half vs second half. The scanner uses a fixed hand-picked watchlist (`DEFAULT_WATCHLIST` in
`mygg/live.py`), checked every 20 s; the original also looks like a fixed list scanned in a fixed order.

## Watchlist change (owner request, 2026-10-31)
PEPE, SHIB, FLOKI and BONK added to `DEFAULT_WATCHLIST`. Binance lists them as 1000x contracts (1000PEPEUSDT); the scanner
queries those names but shows and logs the plain pair (PEPEUSDT) with prices divided by 1000, like the original signals.
`template_backtest.py fetch --symbols PEPEUSDT ...` does the same when saving candles, so every tool reads `data/PEPEUSDT.csv`
in plain units. Record the restart time here when the owner reports it.

## Extra coins without code edits (2026-10-31)
`python3 -m mygg scan --add NEAR FIL TIA ...` adds coins to the default watchlist (`--symbols` replaces it). The scanner prints
once at start which coins it watches and which are not on Binance futures. Every coin seen in the original's signals was
already in the list; extra coins are the owner's choice and add volume (about 5 signals a day per coin with the 4-hour
cooldown). Fetch candles for new coins with `template_backtest.py fetch` before evaluating them.

## Owner confirmations
- 2026-10-31: the owner confirmed the Cornix set-up is paper trading "for now". Cornix settings seen in the admin panel
  for a scanner signal: entries 65/15/10/10, targets 60/20/10/10, trailing "Moving Target" triggered at target 1,
  amount 5.0%, 10 exchange accounts listed. About 185-225 trades were open on 31 Oct. Use
  `tools/evaluate.py --entry-weights 65,15,10,10 --tp-weights 60,20,10,10 --trail moving --amount 5`.
- Conditions to agree before any real money (owner to tell the assistant first): full month incl. all stop-outs, a
  drawdown the owner can accept (the model shows 90%+ at 200 stacked positions), a beat over the same-month random
  baseline, a position-size and concurrent-trade cap, and a small separate live test.

## Known delivery gaps
- 2026-10-31: two Telegram sends failed with URLError (brief network blips) on the chat whose id ends 1908:
  TRXUSDT and IMXUSDT signals (lines 1921 and 2291 of `scan.out`; no times recorded). They are `published=1` in the log
  but did not reach that chat. Check which chat Cornix follows before counting them in the month-end comparison.
  Scan errors (URLError) skip one scan pass and recover on their own.

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

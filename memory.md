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

## Bollinger rule switched on (owner request, 2026-11-01)
Command adds `--rules macd ema bb` (the later `--rules` overrides the wrapper's default). BB = price beyond a 20-candle, 2-sigma band of the
previous closes, fresh versus the last close; shown as BB Breakout (long) or BB Breakdown (short), 20x. Unconfirmed: whether the
original also needs a squeeze, and the exact band settings. Shares the 4-hour same-direction cooldown. Start time to be
recorded from the owner's `date -u`. Everything logged with rule "BB" is the new strategy.

## Market sessions (looked at 2026-11-01, Cornix export, 1072 signals, 4 days)
Sessions (UTC): Asia 00-08 mean +12.0%, London 08-13:30 +8.9%, New York 13:30-21 +17.6%, Late 21-24 +19.0%. Signal volume spikes
at 07-08 UTC and 17-18 UTC. The London-open window 07-09 UTC is the weakest (n=140, mean +5%, 62% positive). The ranking
reverses between days (29 Oct: New York +37%, Asia +8%; 30 Oct: Asia +25%, New York +5%), so it tracks each day's market
move, not a stable session effect; a trade-level permutation test overstates significance because signals from one
move are correlated. Use the day as the unit: `tools/sessions.py` does this (also groups by how many signals fire in
the same candle). Needs weeks of data; do not use sessions as a filter yet.

## Cornix export 3 (1411 signals, 28 Oct 17:32 to 1 Nov 11:05 UTC), the edge fades (2026-11-01)
Mean profit per signal by day (closed only): 28 Oct +32.3%, 29 Oct +18.9%, 30 Oct +9.6%, 31 Oct +3.3%, 1 Nov +0.4% (partial).
Blocks: 30 Oct 12-24 +6.2% (85% positive); 31 Oct 00-08 +5.8%; 08-14:51 +4.2% (57%); after the 14:51 UTC change -0.1% (47%);
1 Nov 00-11 -0.4% (40%). The fade started before the 31 Oct 14:51 change, so it is not attributable to it. Cancelled-by-
reverse-signal share of signals: 19% (30 Oct) to 57% (31 Oct), 56% (1 Nov); most are closed before target 1 at a small loss
(392 trades, mean -14.8%): a whipsaw regime. The 181 trades open in export 2 resolved to net +290% (146 cancelled at a mean
-1.8%, 35 reached targets). The 84 signals on the 14 added coins average -0.27% (36% positive), same as the rest after the change.
No 20x (BB) rows appear yet, so the Bollinger rule was not running at export time. Paper fills have no fees or slippage;
small losses and near-zero averages would be negative with costs. Open question for later: a cool-down after a reversal
on a coin to damp whipsaw (test offline first).

## PARTLY SUPERSEDED, see the screenshot correction: Paper account balance (owner, 2026-11-01 about 11:30 UTC)
Started 20,000; now 77,302 (+286.5%); peak 122,000 (+510%), date of the peak not given. From the peak: -44,698 (-36.6%). The
signals' average profit fell from +32% (28 Oct) to about 0% (1 Nov), so the equity curve flattening and giving back
gains matches. Paper has no fees, slippage or margin limit; hundreds of stacked 15-25x positions at 5% each could not be
held in a real account. Ask the owner for one balance reading a day (same time) for `tools/equity.py`, and for the amount per signal.

## SUPERSEDED by the screenshot correction below: Amount per signal and a reality check (owner: 5% per signal, 2026-11-01)
Calibration: 5% of the 20,000 start = 1,000 margin per signal, fixed (not compounding). Summing profit% x filled share x 1,000 over
the 1411 signals gives 78.7k vs the actual 77.3k (2% apart), so the signal-level profits explain the paper balance. The owner's
reported peak (122k, 31 Oct) is not reproduced: realised-only reconstruction peaks near 82k (31 Oct 23:00 UTC) with a largest drop
about 6k, so the 122k was probably equity including floating profit on open trades that was later given back (to check with the
owner). Capacity/fees (first come first served, taker fee 0.05% a side, no slippage): max 20 open -> 357 trades, +10.4k net on
20k; max 50 -> 876 trades, +29.3k; unlimited -> 1411 trades, +40.3k net vs +58.7k gross (fees about 18k, 31% of gross). A real
20k account at 1,000 a trade can hold about 20 positions. Tool: `tools/capacity.py <cornix export>`.

## CORRECTION from the Cornix bot screenshot (2026-11-01 11:33 UTC)
Screenshot of "Botbac Signals Bot" (DEMO TRADING banner, account "My Binance Demo - Futures", group "Botbac"): Closed Trades 588,
$77,302.39 (accumulated profit of closed trades, NOT the balance; balance would be about 97k if the start was 20k), Open Trades 17.
The Accumulated Profit chart is flat until about 28 Oct, peaks at about 121,593 around 30-31 Oct, then falls to about 77-80k.
So: (1) the owner's 122k peak was a REALISED peak, not floating equity; about 44k (36%) of realised profit was given back
in roughly a day. (2) The bot took 605 trades (588 closed + 17 open) out of 1411 signals in the group export, so the signal exports
are signal-level, not this bot's trades. (3) My statement that fixed 1,000 per signal reproduced the "balance" within 2% was a
coincidence from misreading profit as balance; the sizing is probably 5% of the current balance (compounding), which magnifies
gains and the later losses. (4) Only one demo account is connected to this bot (the "10 exchanges" in earlier exports came from the
signal/group view). To do: ask for the bot's Trades export (closed trades with dollar profit and size) and a screenshot of the bot
configuration (amount, max open trades, opposite-signal handling) to explain why only 43% of signals were traded.

## First 3 days (28 Oct 17:00 to 31 Oct 17:00 UTC, Cornix signal export, 1143 signals): which settings did best?
MACD(25x) +16.2% vs EMA(15x) +9.6% per signal, but the same average price move (0.65% vs 0.64%): leverage, not rule quality.
Long +15.5% (0.73% move) vs short +11.7% (0.56%); MACD short had the most cancel-before-target (29%). By day: +32.3, +18.9,
+9.5, +5.1% (price move 1.45 to 0.24%). By scanner version: v1 +31.6% (n=50), v2 1h cooldown +23.4% (n=356), v3 one-per-coin-per-candle
+7.7% (n=737): confounded with the fading days, not an effect of the settings. Conclusion: no scanner setting explains the early
results; the market did. `tools/sweep.py` tests Cornix-side settings (entry split, target split, trailing) on the same signals;
run it and check consistency across days before changing anything.

## Settings sweep (corrected, 1120 signals, 28 Oct 17:00 to 31 Oct 17:00, ranked on the full planned size, fees 0.05%/side, no reversal exit)
Entry split barely matters (top four entry splits within 1.8-2.1%); the target split does: equal 25/25/25/25 targets take the top
8 rows (about +2.0%) vs the owner's 60/20/10/10 at +0.3% (rank 34 of 50, positive on 1 of 4 days). Even the best is positive on
only 2 of 4 days, and the model is pessimistic against Cornix (it has fees and no reverse-signal exit). A front-loaded target split
did worst in this trending window only if all-in at target 1 (100/0/0/0: -1.4% to -2.0%). Not conclusive: 4 days, correlated signals.
Suggested test instead of changing the live paper settings: a second demo bot on the same group with 25/25/25/25 targets, run side by side.
An earlier sweep ranked on margin used and was biased towards deep, rarely filled entries; fixed.

## Sessions again, with export 3 (1411 signals, 28 Oct 17:32 to 1 Nov 11:05 UTC)
Mean profit per signal / share positive / loss exits: Asia 00-08 +9.2% / 69% / 28%; London 08-13:30 +7.6% / 71% / 21%; New York 13:30-21
+14.8% / 79% / 20%; Late 21-24 +10.0% / 62% / 37% (positive on only 2 of 4 days, 90% range -11.5 to +24). Weakest hours (n>=25):
05:00 -4.5% (n=26), 23:00 -0.1%, 07:00 +1.2% (n=99, the London-open hour), 06:00 +1.5%. Best hours 17:00, 01:00, 18:00 (about +19% to +27%).
All sessions fade over the days (New York 29 Oct +37%, 30 Oct +5%, 31 Oct +3%). Not significant yet; recheck with `tools/sessions.py`
on the month.

## Avoid-hours filter (owner decision, 2026-11-01)
Owner asked to avoid trading in the weak hours. Implemented as `--avoid-hours 5-8 21-24` (UTC, start inclusive, end exclusive): no
new signals in hours 05, 06, 07 and 21, 22, 23. Blocked flips are logged with published 0 and also written to `mygg_blocked.csv`
(same format, published 1 = would have been sent) so `tools/evaluate.py mygg_blocked.csv` can score what was skipped. Caveat: reverse
signals are blocked too, so a trade opened before a window is not closed by a reversal until it ends. Evidence at the time (export 3):
those 6 hours held 22% of signals, mean +4.9% (57% positive) vs +12.7% (77%) in other hours; weaker on 3 of 5 days, better on 28 Oct.
Start time: to be recorded from the owner's `date -u`. Compare before and after at month end.

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

## Period change: BB on + avoid hours (applied)
- Applied 2026-11-01 12:21:23 UTC on the instance: `--rules macd ema bb --avoid-hours 5-8 21-24 --cooldown 16 --cooldown-scope dir`, same 52 coins.
- Everything before this time = MACD/EMA only, no hour filter. BB trades = the 20x group in Cornix exports.
- Blocked flips go to mygg_blocked.csv; score at month-end with tools/evaluate.py.
- At the first scan after restart, several BB short flips were logged within 3 s (12:21:12-14), only some published; check whether BB state-at-start produced a burst (see follow-up).

## BB fit from four original signals (31 Oct 17:57 UTC BTC/UNI long; 1 Nov 00:21 UTC AVAX/UNI short)
- All four are exact template (mid price M). With M as the price: z20 = 2.77, 3.07, 2.98, 2.93 (beyond 2 sd); band-width percentile (prior 200) = 8, 8, 0, 6 -> a squeeze. Earlier z20 ~1 for BTC came from using the zone edge, not M; in a squeeze the band is tiny so the price used matters.
- Pinned Pine strategy does not fire at these times. Text mentions squeeze/oscillator (RSI-like filter, untested).
- BBBreak now requires width percentile <= 10 (squeeze=10, lookback=200); before this (restart 2026-11-01 12:21:23 UTC) BB fired on any 2 sd close and produced a startup burst. Squeeze version start time: to be recorded after the owner's restart.
- Squeeze version restarted on the instance at about 2026-11-01 12:34:35 UTC (date -u 12:35:05 after a 30 s wait). BB period with the loose rule (no squeeze): 12:21:23 to 12:34:35 UTC; its published BB shorts (seen: HBAR, LDO, FIL, maybe more) are the loose-rule group; keep them apart from squeeze-version BB trades in the 20x group.

## BB fit update (six original signals)
- Added ARB long and AAVE long, both 2026-10-31 06:52 UTC (owner time 11:52). Signal IDs (001, 002, 007, 008) number signals inside one batch/scan pass, not per day: the 06:52 batch had at least 8 BB signals.
- z20 (mid price): 2.77, 3.07, 2.98, 2.93, 2.47, 2.68 (all > 2). Band-width percentile: 8, 8, 0, 6, 12, 27. The cut-off of 10 rejects ARB and AAVE; text wording ("squeeze", oscillator level) varies and is not a reliable filter.
- tools/bb_rate.py counts breakout events per day per cut-off and checks the original signals; threshold to be chosen from its output.
- The 06:52 batch falls in the avoid-hours window 5-8 UTC: our filter would block it.
- bb_rate on 51 coins x 10 days: 277 breakouts/day (2 sd, no filter), 75/day at width pct <= 10, 143/day at <= 30. Far too many versus the original (batches of 8+ at a time). Originals' width pct: 8.5, 8, 0, 6, 11.5, 27. Squeeze alone does not explain the original rate; tools/bb_rate.py now prints a grid of band size (2/2.5/3 sd) x squeeze cut-off. Needed: the original's count of BB posts per day.
- Running scanner still has BB on with cut-off 10 (about 75/day before cooldown). Recommended: turn BB off until the rule is fitted.

## BB turned off again
- Restarted without bb at about 2026-11-01 12:58:36 UTC (date -u 12:59:06 after 30 s). Periods: BB loose rule 12:21:23-12:34:35; BB squeeze<=10 12:34:35-12:58:36; BB off after. Config now: --rules macd ema, --avoid-hours 5-8 21-24, --cooldown 16 --cooldown-scope dir, 52 coins.
- Grid (51 coins x 10 days, breakouts/day): 2 sd: none 277, pct<=10 75, <=20 112, <=30 143; 2.5 sd: 181, 52, 76, 97; 3 sd: 111, 35, 50, 65. Even 3 sd + squeeze<=10 gives 35/day. Need the original's daily BB count to choose.

## Eleven original BB signals (all 20x, exact template; 11 in ~27 h from 30 Oct 21:06 UTC to 1 Nov 00:21 UTC = ~10/day)
- Times UTC: 30 Oct 21:06 FLOKI short, WIF, ONDO, PYTH long; 31 Oct 06:52 ARB, AAVE long; 06:56 ENA long; 17:57 BTC, UNI long; 1 Nov 00:21 AVAX, UNI short. Signal IDs are probably shared with MACD/EMA signals (gaps).
- z20 (mid price): 2.32-3.07 -> 2 sd band is right (2.5 would reject three). Width percentile: 8.5, 8, 0, 6, 11.5, 27, 31, 11, 44, 41, 9 -> not a strict squeeze; all below the median.
- Our rule at 2 sd + width<=45 still gives roughly 150+/day versus the original ~10/day: an unknown selection condition removes ~90%. Next step: tools/bb_discriminate.py compares breakouts the original picked with those it did not at each batch time (RSI, move size, range).
- Three of the originals fall in our avoid-hours windows (21:06 and 06:52/06:56 UTC).
- bb_discriminate result (candle-close test): at the six batch times only 2-4 of 51 coins had a breakout (about the all-day average of ~3 per candle); picked and not-picked coins look the same (z, width%, RSI, move). ETH (z 2.41, width 4) not posted while BTC was at 17:57; LDO, ICP, PEPE, FIL also not posted. The original posts in only some candles (6 candles for 11 signals in ~27 h). Intrabar flips explain misses by the close test (FLOKI, ONDO, PYTH, ARB, AAVE, UNI long, AVAX). Next: tools/bb_candles.py lists every candle with eligible coins vs candles with posts.

## Source channel Cornix export (owner-supplied, 127 signals, 2026-10-25 21:24 to 2026-11-01 06:42 UTC) -> tools/source_signals.csv
- These are the ORIGINAL's signals as Cornix received them (times in UTC, to the second; BB rows match the posts the owner pasted). 64 MACD (25x), 44 EMA (15x), 19 BB (20x); about 18 a day in total, BB 2.7 a day (a burst of 11 in 27 h on 30 Oct-1 Nov).
- 33 coins appear; all are in our list. Never seen in the week: ETH SOL XRP BNB ALGO BCH ETC FIL HBAR KAS LDO TAO TIA TON PEPE SHIB BONK FLOKI (FLOKI BB short at 30 Oct 21:06 was posted by the original but is missing here: Cornix probably could not parse its scientific-notation prices; we print fixed decimals).
- Posts come in ROUNDS: 34 distinct minutes in 7 days, gaps of 3-7 h (one of 22 h), up to 9 signals per round, signals of one round a few seconds apart, never the same coin twice in a round, mixed MACD/EMA/BB and directions.
- Hypothesis (to test with tools/round_check.py): the original scans only at irregular times and posts the rules that flipped in that candle for a fixed list of ~33 coins, one signal per coin (priority maybe MACD > EMA > BB). Our scanner posts every flip continuously on 52 coins: ~190 signals in 12 h vs ~18 a day.
- BB comparison at 21:06 (30 Oct): LDO, PEPE, ICP also broke the band but LDO/PEPE are not in the original's list and ICP was posted as MACD 25x; ETH at 17:57 (z 2.41, same as BTC) is not in its list.
- round_check (candle high/low touch, 30 candles with posts): our rules flipped on 100/127 posted source signals (79%); extras on source-list coins 283, on never-listed coins 157. So the original posts only about 1 in 4 of the flips seen over the full candle, but that count includes flips after the post time inside the candle. Next: tools/round_live.py repeats the test at the exact post second with 1-minute prices.

## Ours vs source (Cornix exports, window 2026-10-28 17:32 to 2026-11-01 06:43 UTC; our file = Botbac export, 1,411 signals)
- Ours 1,336 signals (844 MACD, 492 EMA, no BB) vs source 46 (26 MACD, 9 EMA, 11 BB): about 38x on MACD+EMA (35 source). Per day: ours 137/280/487/350/82 vs source -/6/9/25/6.
- ENA: ours 32 (20 MACD, 12 EMA) vs source 3 (EMA short 29 Oct, BB long 31 Oct, MACD short 31 Oct).
- Our rules catch the source: for 35 source MACD/EMA signals, 27 had the same coin, direction, rule from us within the hour before (median ~7 min earlier), 35/35 within a day. The source posts a few minutes after the flip.
- 236 of our signals (18%) are on coins the source never used (ETH 48, BNB 40, KAS 34, XRP 32, SOL 25, ETC, TIA, SHIB, BCH, FLOKI).
- Conclusion: rules/timing close; volume ~30x too high. Open question: what the source skips (round_live result pending).

## round_live result (flip list at the exact post second, 1-minute prices, 30 scans)
- Our MACD/EMA/BB(no squeeze) flips found 94/127 posted source signals (74%). Extra flips at the same moments: 99 on coins the source uses (45 MACD, 31 BB, 23 EMA) and 68 on coins it never uses. So at the scan moments we see ~193 flips on its coins vs 127 posted (1.5x), against ~30x when we publish continuously. The volume gap is therefore mostly because the source scans only ~4-5 times a day (30-34 rounds in 7 days, gaps 3-7 h, irregular) and posts what is flipped at that moment.
- Remaining extras are explained in part by: BB without squeeze filter (31), flips on coins already posted in an earlier round the same candle (e.g. 26 Oct 22:03 after 21:55), coins never used by the source (ETH BNB SOL XRP KAS...).
- Proposed rounds mode (not built, awaiting owner's go-ahead): publish only at round times (random gap 3-7 h), only flips present at that moment, only on the source's 33 coins, one signal per coin per round, no repeat of a coin posted in the previous round, max 9 per round.

## Rounds mode built (awaiting the owner's restart)
- `--rounds` in mygg scan: flips logged as before (published 0); posts only in rounds every 3-7 h (random, state in mygg_rounds.json), the flips active at that moment, on SOURCE_COINS (34 coins), one per coin (priority MACD > EMA > BB, unconfirmed), skipping coins posted in the previous round, max 9, 1 s apart. 26 tests pass.
- BBBreak squeeze default changed from 10 to 45 (all 11 original BB signals pass; unconfirmed).
- Start time to be recorded after the owner's restart; the continuous period ends then (it ran with BB off, avoid-hours 5-8 21-24 since 2026-11-01 12:58:36 UTC).

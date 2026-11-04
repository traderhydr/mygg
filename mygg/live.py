"""Live scanner on Binance USD-M futures public data (no keys). Paper only: it prints and logs signals."""
import calendar
import csv
import json
import os
import time
import urllib.parse
import urllib.request

from . import template
from .rules import DEFAULT_RULES

API = "https://fapi.binance.com/fapi/v1"
BAR_MS = 15 * 60 * 1000
DEFAULT_WATCHLIST = ("BTC ETH SOL BNB XRP DOGE ADA AVAX LINK DOT UNI ATOM LTC AAVE ARB OP APT SUI SEI INJ "
                     "RENDER FET IMX ONDO ENA WLD STRK PYTH JUP ORDI ICP GRT XLM TRX POL KAS WIF PEPE SHIB FLOKI BONK").split()

# Binance quotes these as 1000x contracts (1000PEPEUSDT ~ 0.004). The signals show the plain price (~4e-06).
SCALED = {"PEPE", "SHIB", "FLOKI", "BONK"}
SCALE = 1000


def market(sym):
    """(Binance symbol, price divisor) for a coin like PEPE or BTC."""
    return (f"{SCALE}{sym}USDT", SCALE) if sym in SCALED else (f"{sym}USDT", 1)


def _get(path, **params):
    url = f"{API}/{path}" + ("?" + urllib.parse.urlencode(params) if params else "")
    with urllib.request.urlopen(url, timeout=20) as r:
        return json.load(r)


def send_telegram(text):
    """Send to your own chats. MYGG_TG_TOKEN is the bot token; MYGG_TG_CHAT is one chat id or several
    separated by commas. A failure on one chat does not stop the others. Never prints the token."""
    token = os.environ.get("MYGG_TG_TOKEN")
    chats = [c.strip() for c in os.environ.get("MYGG_TG_CHAT", "").split(",") if c.strip()]
    if not token or not chats:
        return False
    sent = False
    for n, chat in enumerate(chats, 1):
        data = urllib.parse.urlencode({"chat_id": chat, "text": text}).encode()
        for attempt in range(3):                      # network blips (URLError) are retried; the chat id is never printed
            try:
                urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", data, timeout=15)
                sent = True
                break
            except Exception as ex:
                code = getattr(ex, "code", "")
                print(f"telegram send failed: chat {n} {type(ex).__name__} {code}", flush=True)
                if code or attempt == 2:              # an HTTP answer (bad chat, rate limit) is not retried
                    break
                time.sleep(2)
    return sent


HEADER = "⚡ SABBOT REAL ⚡"


def strategy_label(rule, side):
    """Name shown in the message, as the original labels them."""
    if rule == "BB":
        return "BB Breakout" if side == "long" else "BB Breakdown"
    return rule


def format_signal(sig):
    """Cornix-readable layout (pair, direction, leverage, entries, targets, stop)."""
    f = template.fmt
    return (f"{HEADER}\n\n"
            f"🧠 Strategy: {strategy_label(sig['rule'], sig['side'])}\n"
            f"🪙 Pair: {sig['symbol']}\n"
            f"🧭 Direction: {sig['side'].upper()}\n"
            f"⚙️ Leverage: Cross {sig['leverage']}X\n"
            f"🎯 Entry: {'-'.join(f(p) for p in sig['entries'])}\n"
            f"💰 Take Profits: {'-'.join(f(p) for p in sig['tps'])}\n"
            f"🛑 Stop Loss: {f(sig['stop'])}")


def _cooldown_key(sym, rule, side, scope):
    return {"rule": (sym, rule, side), "dir": (sym, side), "coin": (sym,)}[scope]


def _restore(log, scope="rule"):
    """Rebuild what was already logged so a restart does not repeat signals or exceed the hourly cap."""
    seen, last_pub, in_candle, hours = set(), {}, set(), {}
    if not os.path.exists(log):
        return seen, last_pub, in_candle, hours
    with open(log) as f:
        for r in csv.DictReader(f):
            try:
                ms = calendar.timegm(time.strptime(r["time_utc"][:19], "%Y-%m-%d %H:%M:%S")) * 1000
            except (ValueError, KeyError):
                continue
            start, side = ms - ms % BAR_MS, 1 if r["direction"] == "long" else -1
            seen.add((r["symbol"], r["rule"], start, side))
            if r.get("published", "1") != "0":
                k = _cooldown_key(r["symbol"], r["rule"], side, scope)
                last_pub[k] = max(last_pub.get(k, 0), start)
                in_candle.add((r["symbol"], start))
                hours[ms // 3600000] = hours.get(ms // 3600000, 0) + 1
    return seen, last_pub, in_candle, hours


def parse_hours(specs):
    """['5-8', '21-24'] -> {5,6,7,21,22,23}; a bare number means that hour only. Start inclusive, end exclusive, UTC."""
    out = set()
    for sp in specs or []:
        lo, _, hi = str(sp).partition("-")
        lo = int(lo)
        hi = int(hi) if hi else lo + 1
        out.update(h % 24 for h in range(lo, hi))
    return out


def parse_quiet(specs, tz="UTC"):
    """['13:00-16:15', '19:30-23:15'] with a time zone name -> a function epoch_seconds -> True while inside a window.
    Start inclusive, end exclusive, in the local time of `tz` (daylight saving included); a window may wrap midnight."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    zone = ZoneInfo(tz)
    wins = []
    for sp in specs or []:
        a, _, b = str(sp).partition("-")
        h1, _, m1 = a.partition(":")
        h2, _, m2 = b.partition(":")
        wins.append((int(h1) * 60 + int(m1 or 0), int(h2) * 60 + int(m2 or 0)))

    def is_quiet(ts):
        d = datetime.fromtimestamp(ts, zone)
        now = d.hour * 60 + d.minute
        return any(lo <= now < hi if lo < hi else now >= lo or now < hi for lo, hi in wins)
    return is_quiet


# The 37 coins that appear in the source channel's signals (week of 25 Oct - 1 Nov); the original never posted ETH,
# SOL, XRP, BNB, KAS, LDO and other coins on our broader list.
SOURCE_COINS = ("AAVE ADA APT ARB ATOM AVAX BTC DOGE DOT ENA FET FLOKI GRT ICP IMX INJ JUP KAS LINK LTC NEAR ONDO OP PEPE "
                "ORDI POL PYTH RENDER SEI SHIB STRK SUI TRX UNI WIF WLD XLM").split()
# One signal per coin per round: when several rules flipped on a coin, the first of these wins (a guess: the source
# posted ICP at 21:06 on 30 Oct as MACD although its Bollinger rule had also flipped).
PRIORITY = {"MACD Cross": 0, "EMA Cross": 1, "BB": 2}


class _RoundHeld(Exception):
    """A due round was moved to the end of the quiet hours (control flow only)."""


def pick_round(cands, previous, limit):
    """Choose what a round publishes from candidates {order, key, rule, side, price}: one per coin by rule
    priority, nothing for a coin posted in the previous round, at most `limit`, rule priority then list order."""
    best = {}
    for c in cands:
        if c["key"] in previous:
            continue
        cur = best.get(c["key"])
        if cur is None or PRIORITY.get(c["rule"].name, 9) < PRIORITY.get(cur["rule"].name, 9):
            best[c["key"]] = c
    chosen = sorted(best.values(), key=lambda c: (PRIORITY.get(c["rule"].name, 9), c["order"]))
    return chosen[:limit]


def _round_state(path, gap, rng):
    """{'next': epoch s, 'last': [keys posted in the previous round]}; a new file schedules the first round soon."""
    try:
        with open(path) as f:
            st = json.load(f)
        return {"next": float(st["next"]), "last": list(st.get("last", []))}
    except (OSError, ValueError, KeyError):
        st = {"next": time.time() + rng.uniform(600, gap[1] * 3600), "last": []}
        _save_round_state(path, st)                   # a restart before the first round keeps this time
        return st


def _save_round_state(path, st):
    try:
        with open(path, "w") as f:
            json.dump(st, f)
    except OSError:
        pass


def scan(symbols, interval=20, log="mygg_flips.csv", rules=DEFAULT_RULES, once=False, cooldown=4,
         cooldown_scope="rule", max_per_hour=0, avoid_hours=frozenset(), quiet=None, rounds=False, round_gap=(3.0, 7.0),
         round_max=12, round_coins=None, round_pause=1.0, rng=None):
    """Log every raw flip; publish (print + Telegram) unless the same coin, rule and direction was
    published within `cooldown` candles, or the coin already has a published signal in this candle (the
    original's batches never repeat a coin). The cooldown is a guess to tune against the original.
    cooldown_scope: "rule" (coin+rule+direction, the default), "dir" (coin+direction, any rule) or "coin".
    max_per_hour: cap on published signals per UTC hour (0 = no cap).
    avoid_hours: UTC hours of the day with no new signals. Flips in them are still logged (published 0) and also written to
    mygg_blocked.csv next to the log, in the same format, so their results can be checked later. Reverse signals are blocked
    too, so a trade opened before a blocked window is not closed by a reversal until the window ends.
    rounds: publish like the source does, in rounds. Flips are still logged (published 0) as they happen, but nothing is
    posted until a round: every `round_gap` hours (random between the two numbers, the source's gaps were 3-7 h) the
    scanner posts the flips that are active at that moment, on `round_coins` only (default SOURCE_COINS), one per coin,
    skipping coins posted in the previous round, at most `round_max`, `round_pause` seconds apart. Round state is kept in
    mygg_rounds.json next to the log, so a restart does not reset the schedule. Cooldown settings do not apply.
    quiet: optional function epoch -> bool (see parse_quiet) for quiet windows with minutes and a time zone; it works
    together with avoid_hours (either one blocks).
    In rounds mode avoid_hours are quiet hours: a round that falls due in them is held until they end (plus 1-10 min)."""
    import random
    rng = rng or random.Random()

    def is_quiet(ts):
        return time.gmtime(ts).tm_hour in avoid_hours or bool(quiet and quiet(ts))

    round_set = set(round_coins if round_coins is not None else SOURCE_COINS)
    rpath = os.path.join(os.path.dirname(os.path.abspath(log)), "mygg_rounds.json")
    rstate = _round_state(rpath, round_gap, rng) if rounds else None
    cache, told = {}, False
    heartbeat = os.path.join(os.path.dirname(os.path.abspath(log)), "mygg_heartbeat")
    seen, last_pub, in_candle, hours = _restore(log, cooldown_scope)
    if not os.path.exists(log):
        with open(log, "w", newline="") as f:
            csv.writer(f).writerow(["time_utc", "symbol", "rule", "direction", "price", "entry1", "stop", "published"])
    while True:
        try:
            now = int(time.time() * 1000)
            prices = {p["symbol"]: float(p["price"]) for p in _get("ticker/price")}
            if not told:
                told = True
                missing = [x for x in symbols if market(x)[0] not in prices]
                print(f"watching {len(symbols) - len(missing)} coins" +
                      (f"; not on Binance futures, skipped: {' '.join(missing)}" if missing else ""), flush=True)
            for sym in symbols:
                api, scale = market(sym)
                key = sym + "USDT"                              # the name shown in signals and the log
                if api not in prices:
                    continue
                start = now - now % BAR_MS
                if cache.get(key, (None,))[0] != start:       # new candle: refresh the closed history
                    k = _get("klines", symbol=api, interval="15m", limit=320)
                    cache[key] = (start, [float(x[4]) for x in k if x[0] < start])
                closed = cache[key][1]
                price = prices[api] / scale
                for rule in rules:
                    side = rule.flip(closed, prices[api])       # indicator signs do not depend on the scale
                    if not side or (key, rule.name, start, side) in seen:
                        continue
                    seen.add((key, rule.name, start, side))
                    ck = _cooldown_key(key, rule.name, side, cooldown_scope)
                    hour = now // 3600000
                    blocked = is_quiet(now / 1000)
                    publish = (start - last_pub.get(ck, -10 ** 15) >= cooldown * BAR_MS
                               and (key, start) not in in_candle           # one published signal per coin per candle
                               and (not max_per_hour or hours.get(hour, 0) < max_per_hour)
                               and not blocked and not rounds)
                    sig = template.build(side, price, ladder=True)
                    sig.update(symbol=key, rule=rule.name, leverage=rule.leverage)
                    if publish:
                        last_pub[ck] = start
                        in_candle.add((key, start))
                        hours[hour] = hours.get(hour, 0) + 1
                        text = format_signal(sig)
                        print(text, "\n", flush=True)
                        send_telegram(text)
                    row = [time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()), key, rule.name,
                           sig["side"], price, sig["entries"][0], sig["stop"], int(publish)]
                    with open(log, "a", newline="") as f:
                        csv.writer(f).writerow(row)
                    if blocked:                                           # would have been published
                        bpath = os.path.join(os.path.dirname(os.path.abspath(log)), "mygg_blocked.csv")
                        new = not os.path.exists(bpath)
                        with open(bpath, "a", newline="") as f:
                            w = csv.writer(f)
                            if new:
                                w.writerow(["time_utc", "symbol", "rule", "direction", "price", "entry1", "stop", "published"])
                            w.writerow(row[:7] + [1])
            if rounds and time.time() >= rstate["next"]:
                if is_quiet(time.time()):                       # quiet hours: hold the round until they end
                    t = time.time()
                    for _ in range(24 * 60):
                        if not is_quiet(t):
                            break
                        t += 60
                    rstate = {"next": t + rng.uniform(60, 600), "last": rstate["last"]}
                    _save_round_state(rpath, rstate)
                    print("round held: quiet hours", flush=True)
                    raise _RoundHeld
                cands = []
                for order, sym in enumerate(symbols):
                    api, scale = market(sym)
                    key = sym + "USDT"
                    if sym not in round_set or api not in prices or key not in cache:
                        continue
                    for rule in rules:
                        side = rule.flip(cache[key][1], prices[api])
                        if side:
                            cands.append(dict(order=order, key=key, rule=rule, side=side, price=prices[api] / scale))
                chosen = pick_round(cands, set(rstate["last"]), round_max)
                print(f"round: {len(cands)} active flips, {len(chosen)} published", flush=True)
                posted = []
                for c in chosen:
                    sig = template.build(c["side"], c["price"], ladder=True)
                    sig.update(symbol=c["key"], rule=c["rule"].name, leverage=c["rule"].leverage)
                    row = [time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()), c["key"], c["rule"].name,
                           sig["side"], c["price"], sig["entries"][0], sig["stop"], 1]
                    text = format_signal(sig)
                    print(text, "\n", flush=True)
                    send_telegram(text)
                    with open(log, "a", newline="") as f:
                        csv.writer(f).writerow(row)
                    posted.append(c["key"])
                    time.sleep(round_pause)
                rstate = {"next": time.time() + rng.uniform(*round_gap) * 3600, "last": posted}
                _save_round_state(rpath, rstate)
        except _RoundHeld:
            pass
        except Exception as ex:                                 # network hiccup: keep going
            print("scan error:", type(ex).__name__, flush=True)
        try:                                                    # proof of life for tools/status.sh
            with open(heartbeat, "w") as f:
                f.write(str(int(time.time())))
        except OSError:
            pass
        if once:
            return
        time.sleep(interval)

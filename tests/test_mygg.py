import unittest

from mygg import indicators as ix
from mygg import template
from mygg.rules import EMACross, MACDCross


class TemplateTests(unittest.TestCase):
    def test_ena_long(self):
        # original ENA signal: zone 0.2079-0.20852, TP 0.20977/0.21175/0.21487/0.22029, stop 0.1978
        s = template.build(1, 0.20821)
        self.assertEqual(s["zone"], (0.2079, 0.20852))
        self.assertEqual(s["tps"], [0.20977, 0.21175, 0.21487, 0.22029])
        self.assertEqual(s["stop"], 0.1978)

    def test_btc_short(self):
        # original BTC short: zone 83415.21-83665.83, stop 87717.55, TP4 78695.17
        s = template.build(-1, 83540.52)
        self.assertEqual(s["zone"], (83415.21, 83665.83))
        self.assertEqual(s["tps"], [82913.97, 82120.33, 80867.22, 78695.17])
        self.assertEqual(s["stop"], 87717.55)
        self.assertEqual(s["entries"][0], 83415.21)      # short enters at the bottom of the zone


class MultiChatTests(unittest.TestCase):
    def test_several_chats_and_one_failure_does_not_block_the_rest(self):
        import os
        from unittest import mock
        from mygg import live
        env = {"MYGG_TG_TOKEN": "123:SECRET", "MYGG_TG_CHAT": "-1001, -1002 ,-1003"}
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch("urllib.request.urlopen", side_effect=[OSError("x")] * 3 + [None, None]) as op, \
                mock.patch("time.sleep"), mock.patch("builtins.print") as pr:
            self.assertTrue(live.send_telegram("hi"))
        self.assertEqual(op.call_count, 5)                      # first chat: 3 tries, then the other two
        sent = [c[0][1] for c in op.call_args_list]
        self.assertIn(b"chat_id=-1002", sent[3])
        self.assertIn(b"chat_id=-1003", sent[4])
        self.assertNotIn("SECRET", " ".join(str(a) for c in pr.call_args_list for a in c[0]))


class ScanTests(unittest.TestCase):
    def test_restart_and_cooldown_do_not_repeat_signals(self):
        import os, tempfile, time
        from unittest import mock
        from mygg import live
        from mygg.rules import EMACross
        now = int(time.time() * 1000)
        start = now - now % live.BAR_MS

        def fake_get(path, **kw):
            if path == "ticker/price":
                return [{"symbol": "BTCUSDT", "price": "110.0"}]
            p, k = 100.0, []
            for j in range(300, 0, -1):
                p *= 0.999
                k.append([start - j * live.BAR_MS, 0, 0, 0, str(p), 0])
            k.append([start, 0, 0, 0, str(p), 0])
            return k

        log = os.path.join(tempfile.mkdtemp(), "f.csv")
        with mock.patch.object(live, "_get", fake_get), mock.patch.object(live, "send_telegram") as tg, \
                mock.patch("builtins.print"):
            live.scan(["BTC"], once=True, log=log, rules=[EMACross()])
            live.scan(["BTC"], once=True, log=log, rules=[EMACross()])      # restart in the same candle
            self.assertEqual(tg.call_count, 1)
        with open(log) as f:
            self.assertEqual(len(f.read().strip().splitlines()), 2)            # header + one flip
        seen, last, in_candle, hours = live._restore(log)
        self.assertEqual(last[("BTCUSDT", "EMA Cross", 1)], start)


    def test_scan_writes_a_heartbeat(self):
        import os, tempfile
        from unittest import mock
        from mygg import live
        d = tempfile.mkdtemp()
        with mock.patch.object(live, "_get", lambda path, **kw: [] if path == "ticker/price" else []):
            live.scan(["BTC"], once=True, log=os.path.join(d, "f.csv"), rules=[])
        with open(os.path.join(d, "mygg_heartbeat")) as f:
            self.assertGreater(int(f.read()), 1_700_000_000)

    def test_hourly_cap_and_restart(self):
        import os, tempfile, time
        from unittest import mock
        from mygg import live
        from mygg.rules import EMACross
        now = int(time.time() * 1000)
        start = now - now % live.BAR_MS

        def fake_get(path, **kw):
            if path == "ticker/price":
                return [{"symbol": "BTCUSDT", "price": "110.0"}, {"symbol": "ETHUSDT", "price": "110.0"}]
            p, k = 100.0, []
            for j in range(300, 0, -1):
                p *= 0.999
                k.append([start - j * live.BAR_MS, 0, 0, 0, str(p), 0])
            k.append([start, 0, 0, 0, str(p), 0])
            return k

        log = os.path.join(tempfile.mkdtemp(), "h.csv")
        with mock.patch.object(live, "_get", fake_get), mock.patch.object(live, "send_telegram") as tg, \
                mock.patch("builtins.print"):
            live.scan(["BTC", "ETH"], once=True, log=log, rules=[EMACross()], max_per_hour=1, cooldown_scope="dir")
            live.scan(["BTC", "ETH"], once=True, log=log, rules=[EMACross()], max_per_hour=1, cooldown_scope="dir")
        self.assertEqual(tg.call_count, 1)                         # two coins flipped, only one under the cap

    def test_one_published_signal_per_coin_per_candle(self):
        import os, tempfile, time
        from unittest import mock
        from mygg import live
        from mygg.rules import BBBreak, EMACross
        now = int(time.time() * 1000)
        start = now - now % live.BAR_MS

        def fake_get(path, **kw):
            if path == "ticker/price":
                return [{"symbol": "BTCUSDT", "price": "110.0"}]
            p, k = 100.0, []
            for j in range(300, 0, -1):
                p *= 0.999
                k.append([start - j * live.BAR_MS, 0, 0, 0, str(p), 0])
            k.append([start, 0, 0, 0, str(p), 0])
            return k

        log = os.path.join(tempfile.mkdtemp(), "g.csv")
        with mock.patch.object(live, "_get", fake_get), mock.patch.object(live, "send_telegram") as tg, \
                mock.patch("builtins.print"):
            live.scan(["BTC"], once=True, log=log, rules=[EMACross(), BBBreak(squeeze=None)])
        self.assertEqual(tg.call_count, 1)                    # both rules flipped; only the first published
        with open(log) as f:
            flags = [line.strip().split(",")[-1] for line in f.read().strip().splitlines()[1:]]
        self.assertEqual(flags, ["1", "0"])


class AvoidHoursTests(unittest.TestCase):
    def test_parse_hours(self):
        from mygg import live
        self.assertEqual(live.parse_hours(["5-8", "21-24"]), {5, 6, 7, 21, 22, 23})
        self.assertEqual(live.parse_hours(["3"]), {3})
        self.assertEqual(live.parse_hours([]), set())

    def run_at(self, hour_utc, avoid):
        import calendar, csv, os, tempfile
        from unittest import mock
        from mygg import live
        from mygg.rules import EMACross
        now = calendar.timegm((2026, 10, 31, hour_utc, 10, 0)) * 1000
        start = now - now % live.BAR_MS

        def fake_get(path, **kw):
            if path == "ticker/price":
                return [{"symbol": "BTCUSDT", "price": "110.0"}]
            p, k = 100.0, []
            for j in range(300, 0, -1):
                p *= 0.999
                k.append([start - j * live.BAR_MS, 0, 0, 0, str(p), 0])
            k.append([start, 0, 0, 0, str(p), 0])
            return k

        d = tempfile.mkdtemp()
        log = os.path.join(d, "f.csv")
        with mock.patch.object(live, "_get", fake_get), mock.patch.object(live, "send_telegram") as tg, \
                mock.patch.object(live.time, "time", return_value=now / 1000), mock.patch("builtins.print"):
            live.scan(["BTC"], once=True, log=log, rules=[EMACross()], avoid_hours=avoid)
        with open(log) as f:
            rows = list(csv.DictReader(f))
        bpath = os.path.join(d, "mygg_blocked.csv")
        blocked = list(csv.DictReader(open(bpath))) if os.path.exists(bpath) else []
        return tg.call_count, rows, blocked

    def test_flip_in_an_avoided_hour_is_logged_but_not_sent(self):
        sent, rows, blocked = self.run_at(22, {21, 22, 23})
        self.assertEqual(sent, 0)
        self.assertEqual(rows[0]["published"], "0")
        self.assertEqual(len(blocked), 1)
        self.assertEqual(blocked[0]["published"], "1")

    def test_flip_in_a_normal_hour_is_sent(self):
        sent, rows, blocked = self.run_at(10, {21, 22, 23})
        self.assertEqual(sent, 1)
        self.assertEqual(rows[0]["published"], "1")
        self.assertEqual(blocked, [])


class WatchlistTests(unittest.TestCase):
    def test_unknown_coins_are_reported_once_and_skipped(self):
        import os, tempfile
        from unittest import mock
        from mygg import live
        log = os.path.join(tempfile.mkdtemp(), "w.csv")
        with mock.patch.object(live, "_get", lambda path, **kw: [{"symbol": "BTCUSDT", "price": "1"}] if path == "ticker/price" else []), \
                mock.patch("builtins.print") as pr:
            live.scan(["BTC", "NOPE"], once=True, log=log, rules=[])
        said = " ".join(str(a) for c in pr.call_args_list for a in c[0])
        self.assertIn("watching 1 coins", said)
        self.assertIn("skipped: NOPE", said)


class ScaledCoinTests(unittest.TestCase):
    def test_1000x_contracts_are_scaled_in_signals_and_log(self):
        import csv, os, tempfile, time
        from unittest import mock
        from mygg import live
        from mygg.rules import EMACross
        self.assertEqual(live.market("PEPE"), ("1000PEPEUSDT", 1000))
        self.assertEqual(live.market("BTC"), ("BTCUSDT", 1))
        now = int(time.time() * 1000)
        start = now - now % live.BAR_MS

        def fake_get(path, **kw):
            if path == "ticker/price":
                return [{"symbol": "1000PEPEUSDT", "price": "4.4"}]
            assert kw["symbol"] == "1000PEPEUSDT"
            p, k = 4.0, []
            for j in range(300, 0, -1):
                p *= 0.999
                k.append([start - j * live.BAR_MS, 0, 0, 0, str(p), 0])
            k.append([start, 0, 0, 0, str(p), 0])
            return k

        log = os.path.join(tempfile.mkdtemp(), "s.csv")
        with mock.patch.object(live, "_get", fake_get), mock.patch.object(live, "send_telegram") as tg, \
                mock.patch("builtins.print"):
            live.scan(["PEPE"], once=True, log=log, rules=[EMACross()])
        text = tg.call_args[0][0]
        self.assertIn("Pair: PEPEUSDT", text)
        self.assertIn("Stop Loss: 0.004180", text)        # 4.4 on the 1000x contract is 0.0044 plain; stop 5% below
        with open(log) as f:
            row = list(csv.DictReader(f))[0]
        self.assertEqual(row["symbol"], "PEPEUSDT")
        self.assertAlmostEqual(float(row["price"]), 4.4e-3, places=6)


class FormatTests(unittest.TestCase):
    def test_arb_layout_matches_the_original_numbers(self):
        from mygg import live
        sig = template.build(1, 0.16682, ladder=True)
        sig.update(symbol="ARBUSDT", leverage=25, rule="MACD Cross")
        text = live.format_signal(sig)
        self.assertIn("🧠 Strategy: MACD Cross", text)
        self.assertEqual(live.strategy_label("BB", "long"), "BB Breakout")
        self.assertEqual(live.strategy_label("BB", "short"), "BB Breakdown")
        self.assertTrue(text.startswith("⚡ SABBOT REAL ⚡"))
        self.assertIn("🪙 Pair: ARBUSDT", text)
        self.assertNotIn("Exchange", text)
        self.assertIn("🧭 Direction: LONG", text)
        self.assertIn("⚙️ Leverage: Cross 25X", text)
        self.assertIn("🎯 Entry: 0.16707-0.16657-0.16252-0.15969", text)
        self.assertIn("💰 Take Profits: 0.16807-0.16966-0.17216-0.17650", text)
        self.assertIn("🛑 Stop Loss: 0.15848", text)

    def test_fmt_decimals(self):
        self.assertEqual(template.fmt(83540.5), "83540.50")
        self.assertEqual(template.fmt(1.0149), "1.015")
        self.assertEqual(template.fmt(4.07e-06), "0.000004070")


def series():
    # flat, then a sharp 3% drop over five candles: MACD below its signal line, fast EMA below slow
    return [100.0] * 150 + [100 - 0.6 * k for k in range(1, 6)]


class RuleTests(unittest.TestCase):
    def test_macd_trigger_price_is_the_zero_crossing(self):
        rule, closed = MACDCross(), series()
        trig = rule.trigger_price(closed)
        self.assertIsNotNone(trig)
        self.assertAlmostEqual(rule.value(closed, trig), 0.0, places=9)
        self.assertEqual(rule.flip(closed, trig * 1.001), 1)
        self.assertEqual(rule.flip(closed, trig * 0.999), 0)

    def test_ema_cross_flips_upward_on_a_jump(self):
        rule, closed = EMACross(), series()
        self.assertEqual(rule.flip(closed, closed[-1] * 1.10), 1)
        self.assertEqual(rule.flip(closed, closed[-1]), 0)

    def test_emas_are_sma_seeded(self):
        vals = [1.0] * 10
        self.assertEqual(ix.ema(vals, 5)[-1], 1.0)


class NotifyTests(unittest.TestCase):
    def test_telegram_only_with_env_and_hides_token(self):
        import os
        from unittest import mock
        from mygg import live
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertFalse(live.send_telegram("hi"))
        env = {"MYGG_TG_TOKEN": "123:SECRET", "MYGG_TG_CHAT": "42"}
        with mock.patch.dict(os.environ, env, clear=True), mock.patch("urllib.request.urlopen") as op:
            self.assertTrue(live.send_telegram("hi"))
            url, data = op.call_args[0][0], op.call_args[0][1]
            self.assertIn("bot123:SECRET/sendMessage", url)
            self.assertIn(b"chat_id=42", data)
        with mock.patch.dict(os.environ, env, clear=True), mock.patch("urllib.request.urlopen", side_effect=OSError("boom")), \
                mock.patch("builtins.print") as pr:
            self.assertFalse(live.send_telegram("hi"))
            self.assertNotIn("SECRET", " ".join(map(str, pr.call_args[0])))


class BBSqueezeTest(unittest.TestCase):
    def _series(self, wide):
        import math
        # wide swings, then a quiet stretch (squeeze) if wide is False
        base = [100 + 3 * math.sin(i / 2) for i in range(250)]
        quiet = [100 + 0.05 * math.sin(i) for i in range(30)]
        noisy = [100 + 3 * math.sin(i / 2) for i in range(30)]
        return base + (noisy if wide else quiet)

    def test_breakout_needs_squeeze(self):
        from mygg.rules import BBBreak
        r = BBBreak()
        quiet = self._series(False)
        self.assertEqual(r.flip(quiet, 101.0), 1)          # out of a squeeze
        wide = self._series(True)
        up = max(wide[-20:]) + 20
        self.assertEqual(BBBreak(squeeze=None).flip(wide, up), 1)
        self.assertEqual(r.flip(wide, up), 0)              # wide band: no signal


class RoundsTest(unittest.TestCase):
    def _env(self):
        import os, tempfile, time
        from mygg import live
        now = int(time.time() * 1000)
        start = now - now % live.BAR_MS

        def fake_get(path, **kw):
            if path == "ticker/price":
                return [{"symbol": "BTCUSDT", "price": "110.0"}, {"symbol": "DOTUSDT", "price": "110.0"}]
            p, k = 100.0, []
            for j in range(300, 0, -1):
                p *= 0.999
                k.append([start - j * live.BAR_MS, 0, 0, 0, str(p), 0])
            k.append([start, 0, 0, 0, str(p), 0])
            return k

        d = tempfile.mkdtemp()
        return d, os.path.join(d, "g.csv"), fake_get

    def _state(self, d, nxt, last=()):
        import json, os
        with open(os.path.join(d, "mygg_rounds.json"), "w") as f:
            json.dump({"next": nxt, "last": list(last)}, f)

    def _scan(self, log, fake_get, **kw):
        from unittest import mock
        from mygg import live
        from mygg.rules import EMACross
        with mock.patch.object(live, "_get", fake_get), mock.patch.object(live, "send_telegram") as tg, \
                mock.patch("builtins.print"):
            live.scan(["BTC", "DOT"], once=True, log=log, rules=[EMACross()], rounds=True, round_pause=0, **kw)
        return tg

    def test_nothing_is_posted_before_a_round_is_due(self):
        import csv, time
        d, log, fake = self._env()
        self._state(d, time.time() + 3600)
        tg = self._scan(log, fake)
        self.assertEqual(tg.call_count, 0)
        rows = list(csv.DictReader(open(log)))
        self.assertEqual([r["published"] for r in rows], ["0", "0"])        # flips are still logged

    def test_a_due_round_posts_active_flips_once_per_coin(self):
        import csv, json, os
        d, log, fake = self._env()
        self._state(d, 0)
        tg = self._scan(log, fake)
        self.assertEqual(tg.call_count, 2)
        rows = list(csv.DictReader(open(log)))
        self.assertEqual(sorted(r["published"] for r in rows), ["0", "0", "1", "1"])
        st = json.load(open(os.path.join(d, "mygg_rounds.json")))
        self.assertEqual(sorted(st["last"]), ["BTCUSDT", "DOTUSDT"])
        self.assertGreater(st["next"], __import__("time").time() + 2.9 * 3600)   # next round 3-7 h away

    def test_coins_from_the_previous_round_are_skipped_and_the_list_is_respected(self):
        d, log, fake = self._env()
        self._state(d, 0, last=["BTCUSDT"])
        tg = self._scan(log, fake)
        self.assertEqual(tg.call_count, 1)                                  # BTC posted last round
        d, log, fake = self._env()
        self._state(d, 0)
        tg = self._scan(log, fake, round_coins=["BTC"])
        self.assertEqual(tg.call_count, 1)                                  # DOT is not on the round list

    def test_first_schedule_is_saved_so_a_restart_keeps_it(self):
        import json, os
        d, log, fake = self._env()
        self._scan(log, fake)
        with open(os.path.join(d, "mygg_rounds.json")) as f:
            first = json.load(f)["next"]
        self._scan(log, fake)
        with open(os.path.join(d, "mygg_rounds.json")) as f:
            self.assertEqual(json.load(f)["next"], first)

    def test_telegram_retries_network_errors_and_hides_the_chat_id(self):
        import io, os, urllib.error
        from contextlib import redirect_stdout
        from unittest import mock
        from mygg import live
        calls = []

        def flaky(url, data, timeout):
            calls.append(1)
            if len(calls) < 3:
                raise urllib.error.URLError("blip")
            return None

        out = io.StringIO()
        with mock.patch.dict(os.environ, {"MYGG_TG_TOKEN": "T", "MYGG_TG_CHAT": "-100123456"}), \
                mock.patch("urllib.request.urlopen", flaky), mock.patch("time.sleep"), redirect_stdout(out):
            ok = live.send_telegram("hi")
        self.assertTrue(ok)
        self.assertEqual(len(calls), 3)
        self.assertNotIn("100123456", out.getvalue())

    def test_pick_round_priority_and_limit(self):
        from mygg import live
        from mygg.rules import BBBreak, EMACross, MACDCross
        c = lambda o, k, r: dict(order=o, key=k, rule=r, side=1, price=1.0)
        cands = [c(0, "A", BBBreak()), c(0, "A", MACDCross()), c(1, "B", EMACross()), c(2, "C", BBBreak()), c(3, "D", MACDCross())]
        got = live.pick_round(cands, {"D"}, 2)
        self.assertEqual([(x["key"], x["rule"].name) for x in got], [("A", "MACD Cross"), ("B", "EMA Cross")])


if __name__ == "__main__":
    unittest.main()
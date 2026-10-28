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


if __name__ == "__main__":
    unittest.main()

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import evaluate as ev  # noqa: E402


class SimulateTests(unittest.TestCase):
    def candles(self):
        # a flat history, then one candle that spikes through every target of a long signal
        base = [(i * 900000, 100.0, 100.1, 99.9, 100.0) for i in range(5)]
        return base + [(5 * 900000, 100.0, 110.0, 99.95, 109.0), (6 * 900000, 109.0, 109.5, 108.5, 109.0)]

    def test_all_in_at_target_one_does_not_divide_by_zero(self):
        res = ev.simulate(self.candles(), 4, 1, 100.0, 25, 0.0005, (1.0, 0, 0, 0), (1.0, 0, 0, 0), "moving")
        self.assertEqual(res["reason"], "tp_all")
        self.assertGreater(res["roe"], 0)

    def test_zero_weight_targets_are_skipped(self):
        res = ev.simulate(self.candles(), 4, 1, 100.0, 25, 0.0005, (0.65, 0.15, 0.10, 0.10), (0.5, 0.3, 0.2, 0.0), "breakeven")
        self.assertEqual(res["reason"], "tp_all")

    def test_default_weights_still_work(self):
        res = ev.simulate(self.candles(), 4, 1, 100.0, 25, 0.0005)
        self.assertTrue(res["tp1"])


if __name__ == "__main__":
    unittest.main()

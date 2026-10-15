import unittest
from backend.analysis import analyse_prices, rsi
from backend.risk import RiskManager

class EngineTests(unittest.TestCase):
    def test_wait_on_short_series(self):
        self.assertEqual(analyse_prices([1,2,3])["signal"], "WAIT")
    def test_rsi_bounds(self):
        self.assertGreaterEqual(rsi([float(i) for i in range(30)]), 0)
        self.assertLessEqual(rsi([float(i) for i in range(30)]), 100)
    def test_stake_is_capped(self):
        rm = RiskManager()
        self.assertEqual(rm.stake_for(10, 5), 0.2)
    def test_three_losses_stop(self):
        rm = RiskManager()
        rm.begin_session(10)
        for _ in range(3): rm.record_result(-0.2)
        allowed, _ = rm.can_trade(9.4)
        self.assertFalse(allowed)
    def test_daily_loss_stop(self):
        rm = RiskManager()
        rm.begin_session(10)
        rm.record_result(-1.1)
        allowed, _ = rm.can_trade(8.9)
        self.assertFalse(allowed)

if __name__ == "__main__":
    unittest.main()

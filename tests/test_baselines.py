import datetime as dt
import unittest
from forecasting.baselines import month_shift, known_at, forecast_one, backtest

class BaselineTests(unittest.TestCase):
    def test_month_rollover(self):
        self.assertEqual(month_shift('2026-01', -1),'2025-12')
        self.assertEqual(month_shift('2026-12', 1),'2027-01')
    def test_vintage_no_lookahead(self):
        rows=[('state:retail','2025-01',100,dt.date(2025,2,15)),('state:retail','2025-01',180,dt.date(2026,1,20))]
        self.assertEqual(known_at(rows,dt.date(2025,12,31))['state:retail']['2025-01'],100)
        self.assertEqual(known_at(rows,dt.date(2026,2,1))['state:retail']['2025-01'],180)
    def test_forecast_requires_prior_year(self):
        self.assertIsNone(forecast_one({'2025-02':123},'2026-01'))
        self.assertEqual(forecast_one({'2025-01':123},'2026-01'),{'seasonal_naive':123})
    def test_backtest_does_not_use_revisions_early(self):
        rows=[('s','2025-01',100,dt.date(2025,2,2)),('s','2026-01',120,dt.date(2026,2,15)),('s','2025-01',900,dt.date(2026,5,1))]
        errors=backtest(rows,'s',dt.date(2026,6,1))
        self.assertEqual(errors['seasonal_naive']['n'],1)
        self.assertEqual(errors['seasonal_naive']['mae'],20)
if __name__=='__main__':unittest.main()

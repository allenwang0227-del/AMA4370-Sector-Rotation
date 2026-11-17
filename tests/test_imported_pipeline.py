"""Check the shared snapshot and the imported indicator/entry pipeline."""
import contextlib
import io
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

from entry_signals import generate_entry_signals
from indicators import add_all_indicators


ROOT = Path(__file__).resolve().parents[1]


class ImportedPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.market = pd.read_csv(ROOT / "data/market_data.csv", parse_dates=["Date"])

    def test_shared_market_data_has_unique_complete_price_rows(self):
        data = self.market
        self.assertFalse(data.duplicated(["Date", "Ticker"]).any())
        self.assertEqual(set(data.Ticker), {
            "XLK", "XLY", "XLE", "XLF", "XLI", "XLB",
            "XLP", "XLV", "XLU", "GLD", "SHY", "SPY",
        })
        self.assertTrue(data.groupby("Date").size().eq(12).all())
        prices = data[["Open", "High", "Low", "Close", "Adj_Close"]]
        self.assertTrue(np.isfinite(prices).all().all())
        self.assertTrue(prices.gt(0).all().all())

    def test_notebook_indicators_reproduce_supplied_snapshot(self):
        prices = pd.read_csv(ROOT / "data/clean_prices.csv", parse_dates=["Date"])
        prices = prices.sort_values(["Ticker", "Date"]).reset_index(drop=True)
        with contextlib.redirect_stdout(io.StringIO()):
            actual = add_all_indicators(prices)
        columns = ["Date", "Ticker", "R3m", "R6m", "R12m", "Momentum",
                   "MA_200", "HV_60", "ATR_14"]
        expected = self.market.sort_values(["Ticker", "Date"]).reset_index(drop=True)
        pd.testing.assert_frame_equal(
            actual[columns], expected[columns], check_dtype=False,
            check_exact=False, rtol=1e-10, atol=1e-10,
        )

    def test_entry_pipeline_reproduces_supplied_candidates(self):
        actual_outputs = generate_entry_signals(self.market)
        names = ["monthly_rankings.csv", "entry_signals.csv",
                 "monthly_selection_summary.csv"]
        for name, actual in zip(names, actual_outputs):
            with self.subTest(file=name):
                actual = pd.read_csv(io.StringIO(actual.to_csv(index=False)))
                expected = pd.read_csv(ROOT / "archive/received_signals" / name)
                pd.testing.assert_frame_equal(
                    actual, expected, check_dtype=False,
                    check_exact=False, rtol=1e-10, atol=1e-10,
                )


if __name__ == "__main__":
    unittest.main()

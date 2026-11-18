import unittest

import numpy as np
import pandas as pd

from portfolio_risk import DrawdownState, update_drawdown
from position_sizing import calculate_weights, monthly_weights


def prices(**annualized_vols):
    dates = pd.bdate_range("2022-01-03", periods=61)
    shocks = pd.Series(np.tile([-1, 1], 30))
    returns = shocks / shocks.std() / np.sqrt(252)
    return pd.DataFrame({
        ticker: np.r_[1, (1 + returns * volatility).cumprod()] * 100
        for ticker, volatility in annualized_vols.items()
    }, index=dates)


class SizingTests(unittest.TestCase):
    def test_inverse_volatility(self):
        close = prices(XLK=.125, XLI=.09, GLD=.09, SHY=.01)
        result = calculate_weights(close, close.index[-1], ["XLK", "XLI", "GLD"])
        expected = pd.Series([.72, 1, 1, 0], index=["XLK", "XLI", "GLD", "SHY"]) / 2.72
        pd.testing.assert_series_equal(result.weights, expected, atol=1e-12)
        self.assertEqual(result.risk_scale, 1)

    def test_caps_leave_released_budget_in_shy(self):
        close = prices(XLK=.0225, XLY=.03, GLD=.09, SHY=.01)
        result = calculate_weights(close, close.index[-1], ["XLK", "XLY", "GLD"])
        self.assertAlmostEqual(result.weights[["XLK", "XLY"]].sum(), .50)
        self.assertAlmostEqual(result.weights["XLK"], .50 * .40 / (.40 + .375))
        self.assertAlmostEqual(result.weights["GLD"], .125)
        self.assertAlmostEqual(result.weights["SHY"], .375)

    def test_empty_seats_and_individual_cap(self):
        close = prices(XLK=.02, XLI=.10, SHY=.01)
        single = calculate_weights(close, close.index[-1], ["XLK"])
        self.assertAlmostEqual(single.weights["XLK"], 1 / 3)
        pair = calculate_weights(close, close.index[-1], ["XLK", "XLI"])
        self.assertAlmostEqual(pair.weights["XLK"], .40)
        self.assertAlmostEqual(pair.weights["SHY"], 1 - .40 - 1 / 9)
        empty = calculate_weights(close, close.index[-1], [])
        self.assertEqual(empty.weights.to_dict(), {"SHY": 1})

    def test_full_covariance_target_and_no_lookahead(self):
        close = prices(XLK=.20, XLI=.20, GLD=.20, SHY=.01)
        signal_date = close.index[-1]
        close.loc[signal_date + pd.offsets.BDay()] = 9999
        result = calculate_weights(close, signal_date, ["XLK", "XLI", "GLD"])
        self.assertAlmostEqual(result.base_volatility, .20)
        self.assertAlmostEqual(result.estimated_volatility, .15)
        self.assertAlmostEqual(result.risk_scale, (.15 - .01) / (.20 - .01))
        self.assertAlmostEqual(result.weights.sum(), 1)

    def test_negative_covariance_reduces_volatility_estimate(self):
        close = prices(XLK=.30, XLI=-.30, SHY=0)
        result = calculate_weights(close, close.index[-1], ["XLK", "XLI"])
        self.assertAlmostEqual(result.estimated_volatility, 0)
        self.assertEqual(result.risk_scale, 1)

    def test_unattainable_target_returns_minimum_risk_without_leverage(self):
        close = prices(XLK=.35, SHY=.20)
        result = calculate_weights(close, close.index[-1], ["XLK"])
        self.assertAlmostEqual(result.estimated_volatility, .20)
        self.assertEqual(result.risk_scale, 0)

    def test_invalid_input_is_not_silently_accepted(self):
        close = prices(XLK=.10, SHY=.01)
        with self.assertRaisesRegex(ValueError, "unique"):
            calculate_weights(close, close.index[-1], ["XLK", "XLK"])
        with self.assertRaisesRegex(ValueError, "61"):
            calculate_weights(close.iloc[1:], close.index[-1], ["XLK"])
        close.iloc[30, 0] = np.nan
        with self.assertRaisesRegex(ValueError, "finite"):
            calculate_weights(close, close.index[-1], ["XLK"])

    def test_monthly_csv_baskets_are_keyed_to_the_next_open(self):
        close = prices(XLK=.10, SHY=.01)
        signal_date = close.index[-1]
        next_open = signal_date + pd.offsets.BDay()
        close.loc[next_open] = 9999
        holdings = pd.DataFrame({
            "Signal_Date": [signal_date], "Next_Trading_Date": [next_open],
            "Selected_ETFs": ["XLK"],
        })
        output = monthly_weights(close, holdings, input_type="final_basket")
        self.assertEqual(set(output["Next_Trading_Date"]), {next_open})
        self.assertEqual(set(output["Input_Type"]), {"final_basket"})
        self.assertAlmostEqual(output["Target_Weight"].sum(), 1)
        holdings.loc[0, "Next_Trading_Date"] = next_open + pd.offsets.BDay()
        with self.assertRaisesRegex(ValueError, "next trading date"):
            monthly_weights(close, holdings, input_type="final_basket")


class DrawdownTests(unittest.TestCase):
    def test_peak_exact_threshold_calendar_month_and_reset(self):
        state = update_drawdown(DrawdownState(), 100, "2022-07-29")
        state = update_drawdown(state, 110, "2022-08-01")
        state = update_drawdown(state, 94, "2022-08-05")
        self.assertEqual(state.peak_nav, 110)
        self.assertFalse(state.in_cooldown("2022-08-05"))
        state = update_drawdown(state, 93.50, "2022-08-08")
        self.assertEqual(state.shy_until, pd.Timestamp("2022-09-08"))
        self.assertTrue(state.in_cooldown("2022-09-07"))
        self.assertFalse(state.in_cooldown("2022-09-08"))
        self.assertEqual(update_drawdown(state, 80, "2022-08-31"), state)
        recovered = update_drawdown(state, 90, "2022-09-08")
        self.assertEqual(recovered, DrawdownState(peak_nav=90))
        retriggered = update_drawdown(recovered, 76, "2022-10-03")
        self.assertTrue(retriggered.in_cooldown("2022-10-03"))

    def test_bad_nav_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "NAV"):
            update_drawdown(DrawdownState(), np.nan, "2022-08-05")


if __name__ == "__main__":
    unittest.main()

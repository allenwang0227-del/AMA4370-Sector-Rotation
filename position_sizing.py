"""Size a final ETF basket at the signal close for the following trading open."""

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from portfolio_risk import scale_to_volatility_target


ROOT = Path(__file__).resolve().parent
LOOKBACK = 60
MAX_POSITIONS = 3
ETF_CAP = .40
CATEGORY_CAP = .50
CATEGORIES = {
    "Offensive": ("XLK", "XLY"),
    "Cyclical": ("XLE", "XLF", "XLI", "XLB"),
    "Defensive": ("XLP", "XLV", "XLU"),
    "Hedge": ("GLD",),
}
UNIVERSE = {ticker for category in CATEGORIES.values() for ticker in category}


@dataclass(frozen=True)
class Allocation:
    weights: pd.Series
    base_volatility: float
    estimated_volatility: float
    risk_scale: float


def calculate_weights(adjusted_closes, signal_date, selected_etfs):
    """Use 60 returns through signal_date from a date-indexed adjusted-close panel."""
    selected = list(selected_etfs)
    if len(selected) > MAX_POSITIONS or len(set(selected)) != len(selected) or set(selected) - UNIVERSE:
        raise ValueError("Select at most three unique candidate ETFs (excluding SHY and SPY)")
    dates = adjusted_closes.index
    if not isinstance(dates, pd.DatetimeIndex) or not dates.is_unique or not dates.is_monotonic_increasing:
        raise ValueError("Adjusted closes must have an increasing, unique DatetimeIndex")
    signal_date = pd.Timestamp(signal_date)
    tickers = [*selected, "SHY"]
    if signal_date not in dates or set(tickers) - set(adjusted_closes.columns):
        raise ValueError("Adjusted closes must contain the signal date and every requested ETF")
    window = adjusted_closes.loc[:signal_date, tickers].tail(LOOKBACK + 1)
    if len(window) != LOOKBACK + 1:
        raise ValueError("Sizing requires 61 adjusted closes through the signal date")
    if not np.isfinite(window.to_numpy()).all() or (window <= 0).any().any():
        raise ValueError("Adjusted closes in the sizing window must be finite and positive")
    returns = window.pct_change(fill_method=None).iloc[1:]
    covariance = returns.cov() * 252
    if not np.isfinite(covariance.to_numpy()).all():
        raise ValueError("Annualized return covariance must be finite")

    weights = pd.Series(0.0, index=tickers)
    if selected:
        asset_vols = np.sqrt(np.diag(covariance)[:-1])
        if (asset_vols <= 0).any():
            raise ValueError("Selected ETFs must have positive historical volatility")
        inverse_vols = 1 / asset_vols
        weights.loc[selected] = (inverse_vols / inverse_vols.sum() * (len(selected) / MAX_POSITIONS)).clip(max=ETF_CAP)
        for category in CATEGORIES.values():
            members = weights.index.intersection(category)
            exposure = weights.loc[members].sum()
            if exposure > CATEGORY_CAP:
                weights.loc[members] *= CATEGORY_CAP / exposure

    weights.loc["SHY"] = max(0.0, 1 - weights.sum())
    return Allocation(*scale_to_volatility_target(weights, covariance))


def monthly_weights(adjusted_closes, holdings, *, input_type):
    """Build complete monthly target snapshots; an omitted ticker has target weight zero."""
    signals = pd.to_datetime(holdings["Signal_Date"])
    if holdings.empty or signals.isna().any() or not signals.is_unique:
        raise ValueError("Provide at least one basket, with a valid and unique signal date per basket")
    rows = []
    for row in holdings.itertuples(index=False):
        signal_date = pd.Timestamp(row.Signal_Date)
        next_open = pd.Timestamp(row.Next_Trading_Date)
        selected = [] if pd.isna(row.Selected_ETFs) else [
            ticker.strip() for ticker in row.Selected_ETFs.split(",") if ticker.strip()
        ]
        allocation = calculate_weights(adjusted_closes, signal_date, selected)
        dates = adjusted_closes.index
        next_index = dates.searchsorted(signal_date, side="right")
        if next_index == len(dates) or next_open != dates[next_index]:
            raise ValueError(f"{next_open} is not the next trading date for {signal_date.date()}")
        for ticker, weight in allocation.weights.items():
            rows.append({
                "Signal_Date": signal_date, "Next_Trading_Date": next_open, "Input_Type": input_type,
                "Ticker": ticker, "Target_Weight": weight, "Base_Ann_Vol": allocation.base_volatility,
                "Target_Ann_Vol_Estimate": allocation.estimated_volatility, "Risk_Scale": allocation.risk_scale,
            })
    return pd.DataFrame(rows).sort_values(["Signal_Date", "Ticker"], ignore_index=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--holdings", type=Path, help="CSV of final baskets after exits and entries")
    parser.add_argument("--output", type=Path, default=ROOT / "results/portfolio_weights.csv")
    args = parser.parse_args()

    market = pd.read_csv(ROOT / "data/market_data.csv", parse_dates=["Date"])
    closes = market.pivot(index="Date", columns="Ticker", values="Adj_Close").sort_index()
    if args.holdings is not None:
        holdings = pd.read_csv(args.holdings)
        input_type = "final_basket"
    else:
        summary = pd.read_csv(ROOT / "archive/received_signals/monthly_selection_summary.csv")
        holdings = summary.loc[summary["Within_Backtest_Execution"] & summary["Regime"].ne("WARMUP")].copy()
        holdings["Selected_ETFs"] = holdings["Selected_ETFs"].replace("None (no new entries)", "")
        input_type = "entry_candidates_example"

    weights = monthly_weights(closes, holdings, input_type=input_type)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    weights.to_csv(args.output, index=False, float_format="%.10f")
    print(f"Saved {weights['Signal_Date'].nunique()} monthly targets ({input_type}): {args.output}")


if __name__ == "__main__":
    main()

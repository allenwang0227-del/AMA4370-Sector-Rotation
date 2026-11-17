"""
indicators.py
Calculate the indicators required by the Sector Rotation project.

Input:
    Long-format daily market data with Date, Ticker, OHLC and Adj Close.

Output columns added:
    Return_3M, Return_6M, Return_12M, Momentum,
    MA200, Vol60, Vol60_Annualized, ATR14

Conventions:
    - Momentum returns use Adj Close to include distributions.
    - MA200 uses Close, following the team's stated indicator specification.
    - Vol60 uses the standard deviation of daily Adj Close returns.
    - ATR14 uses OHLC prices and Wilder's smoothing.
    - All rolling calculations are backward-looking; no future data is used.
"""

from __future__ import annotations

from pathlib import Path
import pandas as pd


TRADING_DAYS_3M = 63
TRADING_DAYS_6M = 126
TRADING_DAYS_12M = 252
MA_WINDOW = 200
VOL_WINDOW = 60
ATR_WINDOW = 14
TRADING_DAYS_PER_YEAR = 252


REQUIRED_COLUMNS = {
    "Date", "Ticker", "Open", "High", "Low", "Close", "Adj Close"
}


def _true_range(group: pd.DataFrame) -> pd.Series:
    """Calculate True Range for one ticker."""
    previous_close = group["Close"].shift(1)

    ranges = pd.concat(
        [
            group["High"] - group["Low"],
            (group["High"] - previous_close).abs(),
            (group["Low"] - previous_close).abs(),
        ],
        axis=1,
    )
    return ranges.max(axis=1)


def calculate_indicators(market_data: pd.DataFrame) -> pd.DataFrame:
    """
    Add all project indicators to a long-format market DataFrame.

    The function preserves rows with unavailable warm-up indicators as NaN.
    Do not fill these NaNs with zero; those dates are not yet eligible for
    indicator-based trading.
    """
    missing = REQUIRED_COLUMNS.difference(market_data.columns)
    if missing:
        raise ValueError(f"Input is missing required columns: {sorted(missing)}")

    data = market_data.copy()
    data["Date"] = pd.to_datetime(data["Date"])
    data = data.sort_values(["Ticker", "Date"]).reset_index(drop=True)

    if data.duplicated(["Date", "Ticker"]).any():
        raise ValueError("Input contains duplicate Date/Ticker observations.")

    numeric_columns = ["Open", "High", "Low", "Close", "Adj Close"]
    for column in numeric_columns:
        data[column] = pd.to_numeric(data[column], errors="coerce")

    output_groups = []

    for ticker, group in data.groupby("Ticker", sort=False):
        group = group.sort_values("Date").copy()

        # Total returns use adjusted closing prices.
        adjusted_close = group["Adj Close"]
        group["Return_3M"] = (
            adjusted_close / adjusted_close.shift(TRADING_DAYS_3M) - 1
        )
        group["Return_6M"] = (
            adjusted_close / adjusted_close.shift(TRADING_DAYS_6M) - 1
        )
        group["Return_12M"] = (
            adjusted_close / adjusted_close.shift(TRADING_DAYS_12M) - 1
        )

        group["Momentum"] = group[
            ["Return_3M", "Return_6M", "Return_12M"]
        ].mean(axis=1, skipna=False)

        # The presentation specifies a 200-day moving average of Close.
        group["MA200"] = group["Close"].rolling(
            window=MA_WINDOW, min_periods=MA_WINDOW
        ).mean()

        # Daily adjusted-price returns, then 60-observation sample standard deviation.
        daily_return = adjusted_close.pct_change(fill_method=None)
        group["Vol60"] = daily_return.rolling(
            window=VOL_WINDOW, min_periods=VOL_WINDOW
        ).std(ddof=1)
        group["Vol60_Annualized"] = (
            group["Vol60"] * (TRADING_DAYS_PER_YEAR ** 0.5)
        )

        # Wilder ATR: first value is the 14-period simple average of True Range;
        # subsequent values use Wilder's recursive smoothing.
        tr = _true_range(group)
        atr = pd.Series(index=group.index, dtype="float64")

        if len(group) >= ATR_WINDOW:
            first_atr_position = ATR_WINDOW - 1
            first_atr = tr.iloc[:ATR_WINDOW].mean()
            atr.iloc[first_atr_position] = first_atr

            for position in range(first_atr_position + 1, len(group)):
                previous_atr = atr.iloc[position - 1]
                current_tr = tr.iloc[position]
                if pd.notna(previous_atr) and pd.notna(current_tr):
                    atr.iloc[position] = (
                        previous_atr * (ATR_WINDOW - 1) + current_tr
                    ) / ATR_WINDOW

        group["ATR14"] = atr
        output_groups.append(group)

    if not output_groups:
        return data

    result = pd.concat(output_groups, ignore_index=True)
    return result.sort_values(["Date", "Ticker"]).reset_index(drop=True)


def save_indicator_data(
    market_data: pd.DataFrame,
    output_path: str | Path = "data/market_data.csv",
) -> pd.DataFrame:
    """Calculate indicators and save the resulting dataset."""
    result = calculate_indicators(market_data)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_path, index=False, date_format="%Y-%m-%d")
    return result


def main() -> None:
    input_path = Path("data/market_data.csv")
    output_path = Path("data/market_data.csv")

    if not input_path.exists():
        raise FileNotFoundError(
            f"{input_path} not found. Run `python data_loader.py` first."
        )

    raw_data = pd.read_csv(input_path, parse_dates=["Date"])
    result = save_indicator_data(raw_data, output_path)
    print(f"Saved {len(result):,} rows with indicators to {output_path.resolve()}")

    indicator_columns = [
        "Return_3M", "Return_6M", "Return_12M", "Momentum",
        "MA200", "Vol60", "Vol60_Annualized", "ATR14",
    ]
    print("\nNon-missing indicator counts:")
    print(result[indicator_columns].notna().sum())


if __name__ == "__main__":
    main()

"""
data_loader.py
Download and clean daily ETF market data from Yahoo Finance.

Universe:
    XLK, XLY, XLE, XLF, XLI, XLB, XLP, XLV, XLU, GLD, SHY, SPY

Default download:
    2004-01-01 through the latest available trading day.

Install:
    pip install -r requirements.txt

Run:
    python data_loader.py
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import logging

import pandas as pd
import yfinance as yf


TICKERS = [
    "XLK", "XLY", "XLE", "XLF", "XLI", "XLB",
    "XLP", "XLV", "XLU", "GLD", "SHY", "SPY",
]
START_DATE = "2004-01-01"

# Yahoo Finance treats the end date as exclusive. Using tomorrow includes
# the latest completed session available when the script is run.
END_DATE = (date.today() + timedelta(days=1)).isoformat()

OUTPUT_DIR = Path("data")
OUTPUT_FILE = OUTPUT_DIR / "market_data.csv"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


def _normalise_history(history: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Standardise one ticker's Yahoo Finance history into ordinary columns."""
    if history.empty:
        logger.warning("%s: Yahoo Finance returned no rows.", ticker)
        return pd.DataFrame()

    # Ticker.history() normally returns flat columns, but normalise defensively.
    if isinstance(history.columns, pd.MultiIndex):
        history.columns = [
            next((str(part) for part in col if str(part) in {
                "Open", "High", "Low", "Close", "Adj Close",
                "Volume", "Dividends", "Stock Splits"
            }), str(col[-1]))
            for col in history.columns
        ]

    history = history.copy()
    history.index = pd.to_datetime(history.index)

    # Remove timezone while preserving the exchange-local calendar date.
    if history.index.tz is not None:
        history.index = history.index.tz_localize(None)

    history.index = history.index.normalize()
    history.index.name = "Date"

    required_price_columns = ["Open", "High", "Low", "Close"]
    for column in required_price_columns + [
        "Adj Close", "Volume", "Dividends", "Stock Splits"
    ]:
        if column not in history.columns:
            history[column] = pd.NA

    result = history[
        required_price_columns
        + ["Adj Close", "Volume", "Dividends", "Stock Splits"]
    ].copy()

    result.insert(0, "Ticker", ticker)
    result = result.reset_index()

    numeric_columns = [
        "Open", "High", "Low", "Close", "Adj Close",
        "Volume", "Dividends", "Stock Splits",
    ]
    for column in numeric_columns:
        result[column] = pd.to_numeric(result[column], errors="coerce")

    # Remove duplicate dates and rows with no usable price data.
    result = result.drop_duplicates(subset=["Date"], keep="last")
    result = result.dropna(subset=["Open", "High", "Low", "Close", "Adj Close"])

    # Do not forward-fill prices: that would create artificial observations.
    result = result.sort_values("Date")
    return result


def download_one_ticker(
    ticker: str,
    start: str = START_DATE,
    end: str = END_DATE,
) -> pd.DataFrame:
    """Download daily OHLCV, adjusted close, dividends and split information."""
    logger.info("Downloading %s (%s to %s)", ticker, start, end)
    history = yf.Ticker(ticker).history(
        start=start,
        end=end,
        interval="1d",
        auto_adjust=False,
        actions=True,
        raise_errors=False,
    )
    return _normalise_history(history, ticker)


def download_market_data(
    tickers: list[str] | None = None,
    start: str = START_DATE,
    end: str = END_DATE,
) -> pd.DataFrame:
    """Download all tickers and return a long-format DataFrame."""
    tickers = tickers or TICKERS
    frames = []

    for ticker in tickers:
        try:
            frame = download_one_ticker(ticker, start=start, end=end)
            if not frame.empty:
                frames.append(frame)
            else:
                logger.warning("%s has no usable observations.", ticker)
        except Exception:
            logger.exception("Download failed for %s.", ticker)

    if not frames:
        raise RuntimeError(
            "No market data was downloaded. Check your internet connection "
            "and Yahoo Finance availability."
        )

    data = pd.concat(frames, ignore_index=True)
    data["Date"] = pd.to_datetime(data["Date"])
    data = data.sort_values(["Ticker", "Date"]).reset_index(drop=True)

    # A ticker may have a later inception date (for example, GLD).
    # Keep each ticker's real available history; do not fabricate earlier data.
    return data


def validate_market_data(data: pd.DataFrame) -> None:
    """Print a compact data-quality report and raise on serious problems."""
    if data.empty:
        raise ValueError("The downloaded market dataset is empty.")

    duplicate_count = int(data.duplicated(["Date", "Ticker"]).sum())
    if duplicate_count:
        raise ValueError(f"Found {duplicate_count} duplicate Date/Ticker rows.")

    logger.info("Rows downloaded: %s", f"{len(data):,}")
    logger.info("Date range: %s to %s", data["Date"].min().date(),
                data["Date"].max().date())

    for ticker in TICKERS:
        ticker_data = data.loc[data["Ticker"] == ticker]
        if ticker_data.empty:
            logger.warning("%s is missing entirely from the download.", ticker)
        else:
            logger.info(
                "%s: %s rows, %s to %s",
                ticker,
                len(ticker_data),
                ticker_data["Date"].min().date(),
                ticker_data["Date"].max().date(),
            )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    market_data = download_market_data()
    validate_market_data(market_data)

    market_data.to_csv(OUTPUT_FILE, index=False, date_format="%Y-%m-%d")
    logger.info("Saved cleaned market data to %s", OUTPUT_FILE.resolve())


if __name__ == "__main__":
    main()

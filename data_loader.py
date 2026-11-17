# Extracted from the supplied Untitled43.ipynb; indicator logic is unchanged.
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

# Universe
TICKERS = [
    "XLK", "XLY", "XLE", "XLF", "XLI",
    "XLB", "XLP", "XLV", "XLU", "GLD",
    "SHY", "SPY"
]

def download_raw_data(tickers, start="2005-01-01", end=None):
    """
    Download daily OHLCV + dividends for multiple tickers.
    Returns a long-format DataFrame.
    """
    if end is None:
        end = datetime.today().strftime("%Y-%m-%d")

    print(f"Downloading data from {start} to {end} ...")

    # Download with actions (includes Dividends and Stock Splits)
    raw = yf.download(
        tickers,
        start=start,
        end=end,
        auto_adjust=False,          # keep raw + Adj Close
        actions=True,               # include Dividends
        group_by="ticker",
        threads=True,
        progress=True
    )

    all_data = []

    for ticker in tickers:
        try:
            df = raw[ticker].copy()
            df = df.reset_index()
            df["Ticker"] = ticker

            # Standardize column names
            df = df.rename(columns={
                "Date": "Date",
                "Open": "Open",
                "High": "High",
                "Low": "Low",
                "Close": "Close",
                "Adj Close": "Adj_Close",
                "Volume": "Volume",
                "Dividends": "Dividends",
                "Stock Splits": "Stock_Splits"
            })

            # Keep only useful columns
            cols = ["Date", "Ticker", "Open", "High", "Low", "Close",
                    "Adj_Close", "Volume", "Dividends", "Stock_Splits"]
            df = df[[c for c in cols if c in df.columns]]

            all_data.append(df)
            print(f"  ✓ {ticker}: {len(df)} rows")

        except Exception as e:
            print(f"  ✗ Failed to process {ticker}: {e}")

    if not all_data:
        raise ValueError("No data downloaded.")

    long_df = pd.concat(all_data, ignore_index=True)
    return long_df

def clean_and_align(df):
    """
    Clean missing values and unify trading dates across all tickers.
    """
    df = df.copy()
    df["Date"] = pd.to_datetime(df["Date"])

    # Sort
    df = df.sort_values(["Ticker", "Date"]).reset_index(drop=True)

    # Create master calendar (union of all trading days)
    all_dates = sorted(df["Date"].unique())
    master_calendar = pd.DataFrame({"Date": all_dates})

    cleaned_list = []

    for ticker, group in df.groupby("Ticker"):
        g = group.set_index("Date")

        # Reindex to master calendar
        g = g.reindex(all_dates)

        # Forward fill price-related columns (reasonable for prices)
        price_cols = ["Open", "High", "Low", "Close", "Adj_Close"]
        g[price_cols] = g[price_cols].ffill()

        # Volume and Dividends: fill 0 (no trade / no dividend)
        g["Volume"] = g["Volume"].fillna(0)
        if "Dividends" in g.columns:
            g["Dividends"] = g["Dividends"].fillna(0)
        if "Stock_Splits" in g.columns:
            g["Stock_Splits"] = g["Stock_Splits"].fillna(0)

        g["Ticker"] = ticker
        g = g.reset_index()
        cleaned_list.append(g)

    cleaned = pd.concat(cleaned_list, ignore_index=True)

    # Drop rows that still have no Close price (very early dates)
    cleaned = cleaned.dropna(subset=["Close"])

    # Final sort
    cleaned = cleaned.sort_values(["Date", "Ticker"]).reset_index(drop=True)

    return cleaned

def get_data_summary(df):
    """Print summary of available dates and coverage."""
    print("\n=== Data Summary ===")
    summary = df.groupby("Ticker")["Date"].agg(["min", "max", "count"])
    summary.columns = ["First_Date", "Last_Date", "N_Days"]
    print(summary.to_string())
    print(f"\nTotal rows: {len(df)}")
    print(f"Date range: {df['Date'].min().date()} → {df['Date'].max().date()}")

def load_market_data(start="2005-01-01", end=None, save_path="data/clean_prices.csv"):
    """
    Main function: download + clean + optionally save.
    Returns the cleaned DataFrame.
    """
    raw = download_raw_data(TICKERS, start=start, end=end)
    clean = clean_and_align(raw)
    get_data_summary(clean)

    if save_path:
        clean.to_csv(save_path, index=False)
        print(f"\nSaved cleaned data to: {save_path}")

    return clean

# ============================================================
# Run when executed directly
# ============================================================
if __name__ == "__main__":
    df = load_market_data(
        start="2005-01-01",
        save_path="data/clean_prices.csv"
    )
    print("\nSample of the data:")
    print(df.head(10))

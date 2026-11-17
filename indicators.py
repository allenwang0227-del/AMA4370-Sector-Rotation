# Extracted from the supplied Untitled43.ipynb; indicator logic is unchanged.
import pandas as pd
import numpy as np

# Approximate trading days for each horizon
LOOKBACKS = {
    "R3m": 63,    # ~3 months
    "R6m": 126,   # ~6 months
    "R12m": 252   # ~12 months
}

def load_clean_data(path="data/clean_prices.csv"):
    """Load the cleaned price data from data_loader.py"""
    df = pd.read_csv(path, parse_dates=["Date"])
    df = df.sort_values(["Ticker", "Date"]).reset_index(drop=True)
    return df

def calculate_total_returns(df, price_col="Adj_Close"):
    """
    Calculate 3m / 6m / 12m total returns using adjusted close.
    Returns are simple percentage returns.
    """
    for name, periods in LOOKBACKS.items():
        df[name] = df.groupby("Ticker")[price_col].pct_change(periods=periods)
    return df

def calculate_momentum(df):
    """
    Momentum Score = equal-weighted average of R3m, R6m, R12m
    """
    df["Momentum"] = (df["R3m"] + df["R6m"] + df["R12m"]) / 3
    return df

def calculate_moving_average(df, window=200, price_col="Adj_Close"):
    """200-day Simple Moving Average"""
    df["MA_200"] = df.groupby("Ticker")[price_col].transform(
        lambda x: x.rolling(window=window, min_periods=window).mean()
    )
    return df

def calculate_historical_volatility(df, window=60, price_col="Adj_Close"):
    """
    60-day Historical Volatility (annualized).
    Based on daily returns of Adj_Close.
    """
    df["Daily_Return"] = df.groupby("Ticker")[price_col].pct_change()
    df["HV_60"] = df.groupby("Ticker")["Daily_Return"].transform(
        lambda x: x.rolling(window=window, min_periods=window).std() * np.sqrt(252)
    )
    return df

def calculate_atr(df, window=14):
    """
    14-day Average True Range (simple rolling mean of True Range).
    True Range = max(High-Low, |High-PrevClose|, |Low-PrevClose|)
    """
    # Previous close (within each ticker)
    df["Prev_Close"] = df.groupby("Ticker")["Close"].shift(1)

    # True Range components
    tr1 = df["High"] - df["Low"]
    tr2 = (df["High"] - df["Prev_Close"]).abs()
    tr3 = (df["Low"] - df["Prev_Close"]).abs()

    df["TR"] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # 14-day ATR
    df["ATR_14"] = df.groupby("Ticker")["TR"].transform(
        lambda x: x.rolling(window=window, min_periods=window).mean()
    )

    # Clean temporary columns
    df = df.drop(columns=["Prev_Close", "TR"], errors="ignore")
    return df

def add_all_indicators(df):
    """Run all indicator calculations in sequence"""
    print("Calculating total returns (3m / 6m / 12m)...")
    df = calculate_total_returns(df)

    print("Calculating Momentum Score...")
    df = calculate_momentum(df)

    print("Calculating 200-day Moving Average...")
    df = calculate_moving_average(df)

    print("Calculating 60-day Historical Volatility...")
    df = calculate_historical_volatility(df)

    print("Calculating 14-day ATR...")
    df = calculate_atr(df)

    return df

def select_output_columns(df):
    """Keep the most useful columns for the final market_data.csv"""
    keep = [
        "Date", "Ticker",
        "Open", "High", "Low", "Close", "Adj_Close", "Volume", "Dividends",
        "R3m", "R6m", "R12m", "Momentum",
        "MA_200", "HV_60", "ATR_14"
    ]
    # Only keep columns that actually exist
    keep = [c for c in keep if c in df.columns]
    return df[keep].copy()

def save_market_data(df, path="data/market_data.csv"):
    """Save the final dataset"""
    df.to_csv(path, index=False)
    print(f"\nSaved final data to: {path}")
    print(f"Shape: {df.shape}")

def get_indicator_summary(df):
    """Show when indicators become available (warm-up period)"""
    print("\n=== Indicator Warm-up Summary (first non-null date) ===")
    indicators = ["R3m", "R6m", "R12m", "Momentum", "MA_200", "HV_60", "ATR_14"]
    for ind in indicators:
        if ind in df.columns:
            first_valid = df.dropna(subset=[ind]).groupby("Ticker")["Date"].min()
            print(f"\n{ind}:")
            print(first_valid.to_string())

# ============================================================
# Main
# ============================================================
if __name__ == "__main__":
    # 1. Load cleaned prices
    df = load_clean_data("data/clean_prices.csv")
    print(f"Loaded clean data: {df.shape}")

    # 2. Calculate all indicators
    df = add_all_indicators(df)

    # 3. Select final columns
    final_df = select_output_columns(df)

    # 4. Show warm-up info
    get_indicator_summary(final_df)

    # 5. Save
    save_market_data(final_df, "data/market_data.csv")

    print("\nSample of final data (latest rows):")
    print(final_df.tail(12))

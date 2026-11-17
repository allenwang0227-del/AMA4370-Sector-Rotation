"""AMA4370: Monthly Sector Rotation entry signals, 2005-2022.

First eligible month-end: January 2006. No transactions are executed here.
"""
from pathlib import Path
import pandas as pd

START_DATE = "2005-01-01"
END_DATE = "2022-12-31"
BASE_DIR = Path(__file__).resolve().parent
INPUT_FILE = BASE_DIR / "data" / "market_data.csv"
OUTPUT_DIR = BASE_DIR / "results" / "entry_signals"

ETFS = ["XLK", "XLY", "XLE", "XLF", "XLI", "XLB", "XLP", "XLV", "XLU", "GLD"]
BEAR_ALLOWED = {"XLP", "XLV", "XLU", "GLD"}
NEEDED = {"Date", "Ticker", "Adj_Close", "Momentum", "MA_200"}


def generate_entry_signals(market_data, start=START_DATE, end=END_DATE):
    missing = NEEDED.difference(market_data.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")

    df = market_data.copy()
    df["Date"] = pd.to_datetime(df["Date"])
    df["Ticker"] = df["Ticker"].astype(str).str.strip().str.upper()
    df = df.sort_values(["Date", "Ticker"])
    if df.duplicated(["Date", "Ticker"]).any():
        raise ValueError("Duplicate Date + Ticker rows detected")

    start, end = pd.Timestamp(start), pd.Timestamp(end)
    if start > end:
        raise ValueError("Start date must be before end date")

    calendar = pd.DatetimeIndex(sorted(df["Date"].unique()))
    if len(calendar) == 0:
        raise ValueError("Empty market data")

    # Genuine last trading day of each month, not calendar month-end.
    month_ends = (
        pd.Series(calendar, index=calendar.to_period("M"))
        .groupby(level=0).max()
    )
    # The file may end midway through its final calendar month.
    if calendar[-1] < calendar[-1].to_period("M").end_time.normalize():
        month_ends = month_ends.loc[month_ends.index < calendar[-1].to_period("M")]
    month_ends = [d for d in month_ends if start <= d <= end]
    if not month_ends:
        raise ValueError("No monthly signal dates in chosen period")

    ranks_out = []
    summary_out = []

    for date in month_ends:
        snapshot = df.loc[df["Date"].eq(date)].set_index("Ticker")
        required_tickers = set(ETFS) | {"SPY", "SHY"}
        if not required_tickers.issubset(snapshot.index):
            raise ValueError(f"Missing assets on {date.date()}: {required_tickers - set(snapshot.index)}")

        next_days = calendar[calendar > date]
        next_day = next_days[0] if len(next_days) else pd.NaT
        # A signal on Dec 2022 may imply a Jan 2023 order outside the test.
        inside_backtest = pd.notna(next_day) and next_day <= end

        spy, shy = snapshot.loc["SPY"], snapshot.loc["SHY"]
        all_prices_ready = snapshot.loc[ETFS, ["Momentum", "Adj_Close", "MA_200"]].notna().all().all()
        ready = (all_prices_ready and
                 pd.notna(spy["Adj_Close"]) and pd.notna(spy["MA_200"]) and
                 pd.notna(shy["Momentum"]))

        # In 2005 the raw file cannot compute full 12-month momentum.
        if not ready:
            for ticker in ETFS:
                asset = snapshot.loc[ticker]
                ranks_out.append({
                    "Signal_Date": date, "Next_Trading_Date": next_day,
                    "Within_Backtest_Execution": inside_backtest,
                    "Ticker": ticker, "Regime": "WARMUP", "Global_Rank": pd.NA,
                    "Rank": pd.NA, "Momentum": asset["Momentum"],
                    "SHY_Momentum": shy["Momentum"],
                    "Adj_Close": asset["Adj_Close"], "MA_200": asset["MA_200"],
                    "Allowed_by_Regime": False, "Top3": False,
                    "Pass_SHY": False, "Pass_MA200": False,
                    "Entry_Signal": 0, "Reason": "WARMUP: insufficient 12-month history"
                })
            summary_out.append({"Signal_Date": date, "Next_Trading_Date": next_day,
                                "Within_Backtest_Execution": inside_backtest,
                                "Regime": "WARMUP", "Selected_ETFs": "WARMUP",
                                "Selected_Count": 0})
            continue

        bear = bool(spy["Adj_Close"] < spy["MA_200"])
        regime = "Bear" if bear else "Normal"
        allowed = ETFS if not bear else [t for t in ETFS if t in BEAR_ALLOWED]
        global_sorted = snapshot.loc[ETFS].sort_values("Momentum", ascending=False, kind="stable")
        global_ranks = {t: i for i, t in enumerate(global_sorted.index, start=1)}
        regime_sorted = snapshot.loc[allowed].sort_values("Momentum", ascending=False, kind="stable")
        eligible_ranks = {t: i for i, t in enumerate(regime_sorted.index, start=1)}

        selected = []
        for ticker in ETFS:
            asset = snapshot.loc[ticker]
            eligible = ticker in eligible_ranks
            rank = eligible_ranks.get(ticker, pd.NA)
            top3 = eligible and rank <= 3
            pass_shy = bool(asset["Momentum"] > shy["Momentum"])
            pass_ma = bool(asset["Adj_Close"] > asset["MA_200"])
            entry = int(top3 and pass_shy and pass_ma)
            if entry:
                selected.append(ticker)
            reason = ("Excluded by bear regime" if not eligible else
                      "Outside Top 3" if not top3 else
                      "Momentum <= SHY" if not pass_shy else
                      "Price <= MA200" if not pass_ma else "PASS")
            ranks_out.append({
                "Signal_Date": date, "Next_Trading_Date": next_day,
                "Within_Backtest_Execution": inside_backtest,
                "Ticker": ticker, "Regime": regime,
                "Global_Rank": global_ranks[ticker],
                "Rank": rank, "Momentum": asset["Momentum"],
                "SHY_Momentum": shy["Momentum"],
                "Adj_Close": asset["Adj_Close"], "MA_200": asset["MA_200"],
                "Allowed_by_Regime": eligible, "Top3": bool(top3),
                "Pass_SHY": pass_shy, "Pass_MA200": pass_ma,
                "Entry_Signal": entry, "Reason": reason
            })

        # Show the chosen ETFs in their Momentum ranking order.
        selected.sort(key=lambda t: eligible_ranks[t])
        summary_out.append({"Signal_Date": date, "Next_Trading_Date": next_day,
                            "Within_Backtest_Execution": inside_backtest,
                            "Regime": regime,
                            "Selected_ETFs": ", ".join(selected) if selected else "None (no new entries)",
                            "Selected_Count": len(selected)})

    rankings = pd.DataFrame(ranks_out)
    entries = rankings.loc[rankings["Entry_Signal"].eq(1)].copy()
    monthly = pd.DataFrame(summary_out)
    return rankings, entries, monthly


def main():
    if not INPUT_FILE.is_file():
        raise FileNotFoundError(f"Place market_data.csv next to this Python file: {INPUT_FILE}")
    df = pd.read_csv(INPUT_FILE, parse_dates=["Date"])
    rankings, entries, monthly = generate_entry_signals(df)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rankings.to_csv(OUTPUT_DIR / "monthly_rankings.csv", index=False)
    entries.to_csv(OUTPUT_DIR / "entry_signals.csv", index=False)
    monthly.to_csv(OUTPUT_DIR / "monthly_selection_summary.csv", index=False)

    print("\n=== AMA4370 ENTRY SIGNALS COMPLETE ===")
    print("Requested period:", START_DATE, "to", END_DATE)
    print("Months in summary:", len(monthly))
    print("Warm-up months:", int(monthly["Regime"].eq("WARMUP").sum()))
    print("Months with valid signals:", int(monthly["Regime"].ne("WARMUP").sum()))
    print("Candidate entry records:", len(entries), "(NOT executed trades)")
    print("Saved to:", OUTPUT_DIR)
    print("\nFirst months with valid signals:")
    print(monthly.loc[monthly["Regime"].ne("WARMUP")].head(6).to_string(index=False))
    print("\nLast 3 monthly decisions:")
    print(monthly.tail(3).to_string(index=False))
    print("\nREMINDER: Entry signals are candidates, not trades. Coordinate with Exit/Risk/Backtest teams.")


if __name__ == "__main__":
    main()

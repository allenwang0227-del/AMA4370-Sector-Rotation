"""AMA4370: monthly exit rules and holdings path check (Harris).

Monthly exit rules, checked on the last trading day of each month and executed
at the next trading day's Open (docs/Sector_Rotation_Strategy_TC.pdf, section 4).
A held ETF is sold if ANY of these is true:
    1. Outside the Top 5 (ranks 4 and 5 are a buffer zone)
    2. Momentum <= SHY Momentum
    3. Adj_Close <= MA_200
These are the exact opposites of Rosie's entry tests, so an ETF can never pass
entry and fail exit in the same month.

Daily stops (2.5 x ATR stop loss, 3 x ATR trailing stop) live in stop_loss.py.

Default choices for the open items in RULES.md (all are parameters):
    - Top 5 uses `Rank` (rank inside the regime's allowed pool). In a bear
      regime a held cyclical ETF has no Rank and is therefore sold. Pass
      rank_col="Global_Rank" to keep it while it stays in the global Top 5.
    - Held ETFs that pass every exit test keep their seat. A new Top 1 does
      not push out a held ETF that is still in the Top 5.
    - Empty seats are filled from Rosie's entry candidates in rank order, up
      to 3 positions. Seats that stay empty go to SHY.
    - An ETF stopped out during a month is not bought back at that month's
      rebalance (the "no buy back this month" rule).

simulate_holdings_path() runs these rules day by day to show which ETFs are
held and why each one was sold. It has no weights, costs or portfolio PnL;
position sizing is Allen's module and the full backtest is Rebecca's.
"""
import argparse
from pathlib import Path

import pandas as pd

from entry_signals import generate_entry_signals
from stop_loss import StopTracker, STOP_ATR_MULT, TRAIL_ATR_MULT

BASE_DIR = Path(__file__).resolve().parent
INPUT_FILE = BASE_DIR / "data" / "market_data.csv"
OUTPUT_DIR = BASE_DIR / "results" / "exits"

EXIT_RANK_LIMIT = 5
MAX_POSITIONS = 3
START_DATE = "2005-01-01"
END_DATE = "2022-12-31"

MONTHLY_REASONS = {
    "Exit_Top5": "Outside Top 5",
    "Exit_SHY": "Momentum <= SHY",
    "Exit_MA200": "Price <= MA200",
}


def add_exit_flags(rankings, rank_col="Rank", rank_limit=EXIT_RANK_LIMIT):
    """Add monthly exit tests to every row of Rosie's monthly_rankings.

    Holding-independent: the backtest only acts on rows for ETFs it holds.
    """
    needed = {"Signal_Date", "Ticker", "Regime", rank_col, "Momentum",
              "SHY_Momentum", "Adj_Close", "MA_200"}
    missing = needed.difference(rankings.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")

    out = rankings.copy()
    warm = out["Regime"].eq("WARMUP")
    rank = pd.to_numeric(out[rank_col], errors="coerce")

    out["Pass_Top5"] = rank.le(rank_limit).fillna(False).astype(bool)
    out["Exit_Top5"] = ~out["Pass_Top5"]
    out["Exit_SHY"] = ~(out["Momentum"] > out["SHY_Momentum"])
    out["Exit_MA200"] = ~(out["Adj_Close"] > out["MA_200"])
    for col in MONTHLY_REASONS:
        out.loc[warm, col] = False
        out[col] = out[col].astype(bool)

    def reason(row):
        if row["Regime"] == "WARMUP":
            return "WARMUP"
        hits = [MONTHLY_REASONS[c] for c in MONTHLY_REASONS if row[c]]
        if row["Exit_Top5"] and pd.isna(row[rank_col]):
            hits[0] = "Excluded by bear regime"
        return "; ".join(hits) if hits else "HOLD"

    out["Exit_Signal"] = out[list(MONTHLY_REASONS)].any(axis=1).astype(int)
    out["Exit_Reason"] = out.apply(reason, axis=1)
    return out


def select_holdings(month_rankings, held, blocked=(), max_positions=MAX_POSITIONS,
                    rank_col="Rank"):
    """Decide one month's holdings from the current holdings.

    month_rankings: rows of monthly_rankings for a single Signal_Date.
    held: tickers held at the close of the signal date (after any stops).
    blocked: tickers stopped out since the last rebalance; not bought back now.
    Returns a dict with keep, exits [(ticker, reason)], adds, final, shy_seats.
    """
    dates = pd.to_datetime(month_rankings["Signal_Date"]).unique()
    if len(dates) != 1:
        raise ValueError("month_rankings must contain exactly one Signal_Date")

    flags = add_exit_flags(month_rankings, rank_col=rank_col).set_index("Ticker")
    unknown = set(held) - set(flags.index)
    if unknown:
        raise ValueError(f"Held tickers missing from rankings: {sorted(unknown)}")

    keep, exits = [], []
    for ticker in held:
        if flags.at[ticker, "Exit_Signal"]:
            exits.append((ticker, flags.at[ticker, "Exit_Reason"]))
        else:
            keep.append(ticker)
    if len(keep) > max_positions:
        raise ValueError(f"Holding {len(keep)} ETFs, more than {max_positions}")

    candidates = flags.loc[flags["Entry_Signal"].eq(1)].copy()
    candidates = candidates.sort_values("Rank", kind="stable")
    adds = []
    for ticker in candidates.index:
        if len(keep) + len(adds) >= max_positions:
            break
        if ticker not in keep and ticker not in blocked:
            adds.append(ticker)

    final = keep + adds
    return {"keep": keep, "exits": exits, "adds": adds, "final": final,
            "shy_seats": max_positions - len(final)}


def simulate_holdings_path(market_data, rankings, end=END_DATE, start=None,
                           rank_col="Rank", max_positions=MAX_POSITIONS,
                           **stop_kwargs):
    """Run monthly exits, entries and daily stops through time.

    Buys and monthly sells fill at the Open of Next_Trading_Date. Stops are
    checked every day from the buy date until the position is sold.
    `start` drops executions before that date (e.g. "2022-01-01" while still
    using the 2021-12-31 signal for the first trade).

    Returns (trades, monthly):
        trades: one row per round trip, with gross trade return.
        monthly: one row per rebalance with holdings and decisions.
    """
    px = market_data.copy()
    px["Date"] = pd.to_datetime(px["Date"])
    px = px.set_index(["Ticker", "Date"]).sort_index()
    calendar = pd.DatetimeIndex(sorted(px.index.get_level_values("Date").unique()))
    end = pd.Timestamp(end)

    ranks = rankings.copy()
    ranks["Signal_Date"] = pd.to_datetime(ranks["Signal_Date"])
    ranks["Next_Trading_Date"] = pd.to_datetime(ranks["Next_Trading_Date"])
    ranks = ranks.loc[ranks["Within_Backtest_Execution"].astype(bool)]
    if start is not None:
        ranks = ranks.loc[ranks["Next_Trading_Date"].ge(pd.Timestamp(start))]
    schedule = (ranks[["Signal_Date", "Next_Trading_Date"]].drop_duplicates()
                .sort_values("Signal_Date").reset_index(drop=True))
    if schedule.empty:
        raise ValueError("No executable signal dates in the chosen period")

    open_pos = {}          # ticker -> {"tracker", "signal_date"}
    trades, monthly = [], []
    stopped_since_rebalance = []
    prev_exec = None

    def bar(ticker, date):
        return px.loc[(ticker, date)]

    def close_trade(ticker, date, price, reason):
        pos = open_pos.pop(ticker)
        t = pos["tracker"]
        trades.append({
            "Ticker": ticker, "Entry_Signal_Date": pos["signal_date"],
            "Entry_Date": t.entry_date, "Entry_Price": t.entry_price,
            "Entry_ATR": t.entry_atr, "Stop_Level_At_Entry": t.stop_level,
            "Exit_Date": date, "Exit_Price": price, "Exit_Reason": reason,
            "Gross_Return": price / t.entry_price - 1,
            "Trading_Days": int(((calendar >= t.entry_date) & (calendar <= date)).sum()),
        })

    def run_stops(first_day, last_day):
        for day in calendar[(calendar >= first_day) & (calendar <= last_day)]:
            for ticker in list(open_pos):
                b = bar(ticker, day)
                event = open_pos[ticker]["tracker"].update(
                    day, b["Open"], b["High"], b["Low"], b["Close"], b["ATR_14"])
                if event is not None:
                    close_trade(ticker, day, event["Fill_Price"], event["Exit_Reason"])
                    stopped_since_rebalance.append(ticker)

    for row in schedule.itertuples(index=False):
        signal_date, exec_date = row.Signal_Date, row.Next_Trading_Date
        if prev_exec is not None:
            run_stops(prev_exec, signal_date)

        month = ranks.loc[ranks["Signal_Date"].eq(signal_date)]
        held_before = sorted(open_pos)
        stopped = list(dict.fromkeys(stopped_since_rebalance))
        if month["Regime"].eq("WARMUP").all():
            decision = {"keep": [], "exits": [], "adds": [], "final": [],
                        "shy_seats": max_positions}
        else:
            decision = select_holdings(month, held_before, blocked=stopped,
                                       max_positions=max_positions, rank_col=rank_col)

        for ticker, reason in decision["exits"]:
            close_trade(ticker, exec_date, float(bar(ticker, exec_date)["Open"]),
                        "MONTHLY: " + reason)
        for ticker in decision["adds"]:
            entry_atr = float(bar(ticker, signal_date)["ATR_14"])
            tracker = StopTracker(ticker, exec_date, float(bar(ticker, exec_date)["Open"]),
                                  entry_atr, **stop_kwargs)
            open_pos[ticker] = {"tracker": tracker, "signal_date": signal_date}

        monthly.append({
            "Signal_Date": signal_date, "Execution_Date": exec_date,
            "Regime": month["Regime"].iloc[0],
            "Held_Before": ", ".join(held_before) or "None",
            "Stopped_Since_Last": ", ".join(stopped) or "None",
            "Monthly_Exits": "; ".join(f"{t} ({r})" for t, r in decision["exits"]) or "None",
            "Kept": ", ".join(decision["keep"]) or "None",
            "Added": ", ".join(decision["adds"]) or "None",
            "Holdings_After": ", ".join(decision["final"]) or "None",
            "SHY_Seats": decision["shy_seats"],
        })
        stopped_since_rebalance.clear()
        prev_exec = exec_date

    # Keep checking stops after the last rebalance until the end of the period.
    last_day = calendar[calendar <= end][-1]
    run_stops(prev_exec, last_day)
    for ticker in sorted(open_pos):
        close_trade(ticker, last_day, float(bar(ticker, last_day)["Close"]), "OPEN_AT_END")

    trades = pd.DataFrame(trades).sort_values(["Entry_Date", "Ticker"]).reset_index(drop=True)
    return trades, pd.DataFrame(monthly)


def summarize_trades(trades):
    """Count and average gross return by exit reason."""
    group = trades["Exit_Reason"].str.replace(r"^MONTHLY: .*", "MONTHLY", regex=True)
    return (trades.assign(Exit_Group=group)
            .groupby("Exit_Group")["Gross_Return"]
            .agg(Trades="count", Avg_Return="mean", Win_Rate=lambda r: (r > 0).mean())
            .reset_index())


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--start", default=START_DATE,
                        help="first execution date to trade (signals start one month earlier)")
    parser.add_argument("--end", default=END_DATE)
    parser.add_argument("--rank-col", default="Rank", choices=["Rank", "Global_Rank"])
    args = parser.parse_args()

    market = pd.read_csv(INPUT_FILE, parse_dates=["Date"])
    signal_start = (pd.Timestamp(args.start) - pd.offsets.MonthBegin(1)).strftime("%Y-%m-%d")
    rankings, _, _ = generate_entry_signals(market, start=signal_start, end=args.end)
    flags = add_exit_flags(rankings, rank_col=args.rank_col)
    trades, monthly = simulate_holdings_path(market, rankings, end=args.end,
                                             start=args.start, rank_col=args.rank_col)
    summary = summarize_trades(trades)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    flags.to_csv(OUTPUT_DIR / "monthly_exit_flags.csv", index=False)
    trades.to_csv(OUTPUT_DIR / "trades.csv", index=False)
    monthly.to_csv(OUTPUT_DIR / "monthly_holdings.csv", index=False)
    summary.to_csv(OUTPUT_DIR / "exit_summary.csv", index=False)

    print("\n=== AMA4370 EXIT RULES: HOLDINGS PATH CHECK ===")
    print(f"Period: {args.start} to {args.end} | Top 5 rank: {args.rank_col}")
    print(f"Stops: {STOP_ATR_MULT} x ATR stop loss, {TRAIL_ATR_MULT} x ATR trailing stop")
    print("Rebalances:", len(monthly), "| Round trips:", len(trades))
    print("\nBy exit reason (gross, no costs, not portfolio PnL):")
    print(summary.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print("\nLast 3 rebalances:")
    print(monthly.tail(3)[["Signal_Date", "Monthly_Exits", "Stopped_Since_Last",
                           "Holdings_After", "SHY_Seats"]].to_string(index=False))
    print("\nSaved to:", OUTPUT_DIR)


if __name__ == "__main__":
    main()

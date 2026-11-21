"""AMA4370: daily ATR stop loss and trailing stop (Harris).

Rules from docs/Sector_Rotation_Strategy_TC.pdf, section 4:
- Stop loss: 2.5 x ATR below the entry price, checked every day.
- Trailing stop: 3 x ATR below the highest price since entry, checked every day.
- If both are hit on the same day, assume the stop loss happened first.

Price fields
    Stops use the raw Open, High, Low and Close, the same fields ATR_14 is
    built from. Adj_Close is only for momentum and MA200.

No look-ahead
    The levels used on day t are fixed before day t opens:
    - stop level  = entry price - 2.5 x ATR_14 on the signal date (frozen)
    - trail level = highest High from entry up to day t-1 - 3 x ATR_14 of day t-1
    Today's High never raises today's trailing level, because daily bars do
    not show whether the high came before or after the low.

Trailing stop activation
    The plan calls it a trailing take-profit ("移動止盈") that locks in gains.
    By default it only becomes active once its level is above the entry
    price. Before that, the 2.5 x ATR stop loss is the only stop. With
    trail_only_in_profit=False the trailing stop is active from day one and,
    because 3 x ATR trailing overtakes the 2.5 x ATR stop as soon as the price
    rises 0.5 x ATR, it then sells most losing trades before the stop loss.

Fills
    If the Open is already at or below the triggered level (gap down), the
    fill is the Open. Otherwise the fill is the level itself.
    Commission and slippage are applied in backtest.py, not here.

Same-day rule
    When the Low is at or below both levels, the exit is recorded as a stop
    loss and filled at the stop loss level (or the Open if lower). This is the
    group's conservative assumption and gives the worse of the two prices.
    Set stop_first=False to fill at the higher level instead.
"""
from dataclasses import dataclass, field
import math

import pandas as pd

STOP_ATR_MULT = 2.5
TRAIL_ATR_MULT = 3.0

STOP_LOSS = "ATR_STOP_LOSS"
TRAILING_STOP = "ATR_TRAILING_STOP"


def _finite_positive(value):
    return value is not None and not pd.isna(value) and math.isfinite(value) and value > 0


@dataclass
class StopTracker:
    """Track one open position and check its stops one trading day at a time.

    Typical use inside a daily backtest loop:

        tracker = StopTracker("XLK", entry_date, entry_price, atr_on_signal_date)
        for each trading day from entry_date onward:
            event = tracker.update(date, open_, high, low, close, atr_14)
            if event is not None:
                # sell at event["Fill_Price"], move the cash to SHY
                break
    """

    ticker: str
    entry_date: pd.Timestamp
    entry_price: float
    entry_atr: float
    stop_mult: float = STOP_ATR_MULT
    trail_mult: float = TRAIL_ATR_MULT
    trail_atr: str = "rolling"  # "rolling": ATR of the previous day; "entry": frozen ATR
    trail_only_in_profit: bool = True
    stop_first: bool = True

    peak: float = field(init=False)
    last_atr: float = field(init=False)
    last_date: pd.Timestamp = field(init=False, default=None)
    closed: bool = field(init=False, default=False)

    def __post_init__(self):
        self.entry_date = pd.Timestamp(self.entry_date)
        if not _finite_positive(self.entry_price):
            raise ValueError(f"{self.ticker}: entry price must be positive, got {self.entry_price}")
        if not _finite_positive(self.entry_atr):
            raise ValueError(f"{self.ticker}: ATR at entry must be positive, got {self.entry_atr}")
        if self.trail_atr not in {"rolling", "entry"}:
            raise ValueError("trail_atr must be 'rolling' or 'entry'")
        self.peak = float(self.entry_price)
        self.last_atr = float(self.entry_atr)

    @property
    def stop_level(self):
        return self.entry_price - self.stop_mult * self.entry_atr

    @property
    def trail_level(self):
        atr = self.entry_atr if self.trail_atr == "entry" else self.last_atr
        level = self.peak - self.trail_mult * atr
        if self.trail_only_in_profit and level <= self.entry_price:
            return float("-inf")  # not active yet: it would not lock in any profit
        return level

    def levels(self):
        """Levels that apply to the next trading day."""
        trail = self.trail_level
        return {"Stop_Level": self.stop_level,
                "Trail_Level": trail if trail != float("-inf") else float("nan"),
                "Active_Level": max(self.stop_level, trail), "Peak": self.peak}

    def update(self, date, open_, high, low, close, atr=None):
        """Check one daily bar. Return an exit event dict, or None if still held."""
        date = pd.Timestamp(date)
        if self.closed:
            raise RuntimeError(f"{self.ticker}: position already closed")
        if date < self.entry_date:
            raise ValueError(f"{self.ticker}: {date.date()} is before entry {self.entry_date.date()}")
        if self.last_date is not None and date <= self.last_date:
            raise ValueError(f"{self.ticker}: dates must increase, got {date.date()}")
        self.last_date = date

        stop, trail = self.stop_level, self.trail_level
        stop_hit, trail_hit = low <= stop, low <= trail

        if stop_hit or trail_hit:
            if stop_hit and trail_hit:
                if self.stop_first:
                    reason, level = STOP_LOSS, stop
                else:
                    reason, level = (TRAILING_STOP, trail) if trail > stop else (STOP_LOSS, stop)
            elif stop_hit:
                reason, level = STOP_LOSS, stop
            else:
                reason, level = TRAILING_STOP, trail
            trail_out = trail if trail != float("-inf") else float("nan")
            gap = open_ <= level
            fill = float(open_) if gap else float(level)
            self.closed = True
            return {
                "Ticker": self.ticker, "Exit_Date": date, "Exit_Reason": reason,
                "Fill_Price": fill, "Gap_Fill": bool(gap),
                "Stop_Level": stop, "Trail_Level": trail_out, "Peak_Before": self.peak,
                "Entry_Date": self.entry_date, "Entry_Price": self.entry_price,
                "Entry_ATR": self.entry_atr,
            }

        # Still held after today's bar: today's data now becomes known.
        if pd.notna(high):
            self.peak = max(self.peak, float(high))
        if _finite_positive(atr):
            self.last_atr = float(atr)
        return None


def run_stop(prices, ticker, entry_date, entry_price, entry_atr, end_date=None,
             return_path=False, **tracker_kwargs):
    """Run the stops for one position over market_data rows.

    prices: market_data with Date, Ticker, Open, High, Low, Close, ATR_14.
    Checks every trading day from entry_date to end_date inclusive.
    Returns the exit event (or None), plus the daily level path if requested.
    """
    rows = prices.loc[prices["Ticker"].eq(ticker)].copy()
    rows["Date"] = pd.to_datetime(rows["Date"])
    rows = rows.sort_values("Date")
    rows = rows.loc[rows["Date"].ge(pd.Timestamp(entry_date))]
    if end_date is not None:
        rows = rows.loc[rows["Date"].le(pd.Timestamp(end_date))]

    tracker = StopTracker(ticker, entry_date, entry_price, entry_atr, **tracker_kwargs)
    path, event = [], None
    for row in rows.itertuples(index=False):
        if return_path:
            path.append({"Date": row.Date, "Low": row.Low, "High": row.High, **tracker.levels()})
        event = tracker.update(row.Date, row.Open, row.High, row.Low, row.Close, row.ATR_14)
        if event is not None:
            break
    if return_path:
        return event, pd.DataFrame(path)
    return event

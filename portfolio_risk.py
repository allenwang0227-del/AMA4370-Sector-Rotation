"""Covariance-based volatility targeting and the daily NAV circuit breaker."""

from dataclasses import dataclass
from math import isfinite, sqrt

import numpy as np
import pandas as pd


VOLATILITY_TARGET = .15
DRAWDOWN_LIMIT = .15


def scale_to_volatility_target(weights, annual_covariance):
    """Return the scaled weights, base volatility, final volatility, and risk scale."""
    base = weights.to_numpy()
    covariance = annual_covariance.loc[weights.index, weights.index].to_numpy()
    shy = weights.index.to_numpy() == "SHY"
    direction = base - shy

    def volatility(scale):
        allocation = shy + scale * direction
        return sqrt(max(0, allocation @ covariance @ allocation))

    base_volatility = volatility(1)
    scale = 1.0
    if base_volatility > VOLATILITY_TARGET:
        curvature = direction @ covariance @ direction
        minimum = np.clip(-(shy @ covariance @ direction) / curvature, 0, 1) if curvature > 0 else 0
        scale = float(minimum)
        if volatility(scale) <= VOLATILITY_TARGET:
            upper = 1.0
            for _ in range(45):
                midpoint = (scale + upper) / 2
                if volatility(midpoint) <= VOLATILITY_TARGET:
                    scale = midpoint
                else:
                    upper = midpoint

    target = pd.Series(shy + scale * direction, index=weights.index)
    return target, base_volatility, volatility(scale), scale


@dataclass(frozen=True)
class DrawdownState:
    peak_nav: float | None = None
    shy_until: pd.Timestamp | None = None

    def in_cooldown(self, execution_date):
        return self.shy_until is not None and pd.Timestamp(execution_date) < self.shy_until


def update_drawdown(state, nav, next_trading_date):
    """Observe one close's NAV; the result governs the following trading open."""
    if not isfinite(nav) or nav <= 0:
        raise ValueError("NAV must be finite and positive")
    next_open = pd.Timestamp(next_trading_date)
    if pd.isna(next_open):
        raise ValueError("A valid next trading date is required")
    if state.in_cooldown(next_open):
        return state
    if state.shy_until is not None or state.peak_nav is None:
        return DrawdownState(peak_nav=nav)
    peak = max(state.peak_nav, nav)
    if nav <= peak * (1 - DRAWDOWN_LIMIT):
        return DrawdownState(peak, next_open + pd.DateOffset(months=1))
    return DrawdownState(peak_nav=peak)

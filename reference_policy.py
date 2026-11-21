"""Explicit provisional Harris/Allen policies, NOT their approved implementation.

Injected into backtest.run_backtest; replace these callbacks after team review.
"""
import numpy as np
import pandas as pd

CATEGORIES = {**dict.fromkeys(['XLK','XLY'], 'offense'),
              **dict.fromkeys(['XLE','XLF','XLI','XLB'], 'cyclical'),
              **dict.fromkeys(['XLP','XLV','XLU'], 'defense'), 'GLD':'hedge'}

class ReferencePolicy:
    name = 'PROVISIONAL reference exits and risk; team review required'

    def monthly_exits(self, holdings, ranking, config):
        exits = {}
        for t in holdings:
            if t == 'SHY':
                continue
            r = ranking.loc[t]
            if not r.Allowed_by_Regime:
                exits[t] = 'regime exclusion'
            elif r.Rank > config.hold_rank:
                exits[t] = 'rank below buffer'
            elif not r.Pass_SHY:
                exits[t] = 'momentum <= SHY'
            elif not r.Pass_MA200:
                exits[t] = 'price <= MA200'
        return exits

    def stop_fill(self, position, bar, config):
        """Standing orders from prior session only. Lower initial stop wins if both hit.

        Daily OHLC cannot establish event order; this is a pessimistic convention.
        A gap below the chosen stop fills at open, never at the unavailable stop.
        """
        initial = position['entry'] - config.initial_atr * position['entry_atr']
        trailing = position['trail']
        if bar.Adj_Low <= initial:
            return min(bar.Adj_Open, initial), 'initial ATR stop'
        if bar.Adj_Low <= trailing:
            return min(bar.Adj_Open, trailing), 'trailing ATR stop'
        return None

    def weights(self, selected, snapshot, history, config):
        if not selected:
            return {'SHY': 1.0}
        vol = snapshot.loc[selected, 'HV_60']
        if vol.isna().any() or (vol <= 0).any():
            raise ValueError('Invalid volatility for sizing')
        # Each occupied chair adds 1/3 risk-asset budget; caps only reduce weights.
        w = (1 / vol) / (1 / vol).sum() * len(selected) / 3
        w = w.clip(upper=config.asset_cap)
        for category in set(CATEGORIES[t] for t in selected):
            names = [t for t in selected if CATEGORIES[t] == category]
            total = w.loc[names].sum()
            if total > config.category_cap:
                w.loc[names] *= config.category_cap / total
        names = selected + ['SHY']
        returns = history[names].pct_change(fill_method=None).tail(60)
        if len(returns.dropna()) < 60:
            raise ValueError('Need 60 complete returns for covariance')
        cov = returns.cov().to_numpy() * 252
        # Include SHY covariance. Choose largest feasible k in [0,1].
        base = np.zeros(len(names)); base[-1] = 1
        direction = np.r_[w.to_numpy(), -w.sum()]
        a = direction @ cov @ direction
        b = 2 * base @ cov @ direction
        c = base @ cov @ base - config.vol_target**2
        if c > 0:
            # No leverage; SHY itself can exceed target. Report, don't guarantee cap.
            k = 0.0
        elif a + b + c <= 0:
            k = 1.0
        else:
            k = float(np.clip((-b + np.sqrt(max(0, b*b - 4*a*c))) / (2*a), 0, 1))
        w *= k
        return {**w.to_dict(), 'SHY': float(1-w.sum())}

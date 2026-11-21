"""Rebecca's event-driven engine; explicit policy injection, no future-price decisions."""
from dataclasses import dataclass, asdict
import numpy as np
import pandas as pd
from entry_signals import generate_entry_signals, ETFS

@dataclass(frozen=True)
class Config:
    start: str = '2022-01-01'
    end: str = '2022-12-31'
    capital: float = 100000.0
    commission: float = 0.0005
    slippage: float = 0.0005
    initial_atr: float = 2.5
    trailing_atr: float = 3.0
    hold_rank: int = 5
    asset_cap: float = 0.40
    category_cap: float = 0.50
    vol_target: float = 0.15
    circuit_drawdown: float = 0.15
    include_gld: bool = True
    lookbacks: tuple = (63,126,252)


def prepare_data(raw, lookbacks=(63,126,252)):
    """Build a separate adjusted total-return price panel; never overwrite shared CSVs.

    Adjusted units are synthetic reinvested units, not literal tradable share counts.
    Do not add dividends a second time. ATR is recalculated in the same units.
    """
    df = raw.copy()
    df['Date'] = pd.to_datetime(df.Date)
    df = df.sort_values(['Ticker','Date']).reset_index(drop=True)
    if df.duplicated(['Date','Ticker']).any():
        raise ValueError('Duplicate asset/date')
    cols = ['Open','High','Low','Close','Adj_Close']
    if not np.isfinite(df[cols]).all().all() or (df[cols] <= 0).any().any():
        raise ValueError('Missing/nonpositive price')
    if ((df.High < df[['Open','Close','Low']].max(axis=1)) |
        (df.Low > df[['Open','Close','High']].min(axis=1))).any():
        raise ValueError('Invalid OHLC')
    factor = df.Adj_Close / df.Close
    for c in ['Open','High','Low']:
        df['Adj_'+c] = df[c] * factor
    g = df.groupby('Ticker').Adj_Close
    df['Momentum'] = sum(g.pct_change(n, fill_method=None) for n in lookbacks) / len(lookbacks)
    df['MA_200'] = g.transform(lambda s:s.rolling(200).mean())
    df['HV_60'] = g.transform(lambda s:s.pct_change(fill_method=None).rolling(60).std()*np.sqrt(252))
    prev = g.shift()
    tr = pd.concat([df.Adj_High-df.Adj_Low, (df.Adj_High-prev).abs(), (df.Adj_Low-prev).abs()], axis=1).max(axis=1)
    df['ATR_14'] = tr.groupby(df.Ticker).transform(lambda s:s.rolling(14).mean())
    raw_prev = df.groupby('Ticker').Close.shift()
    raw_tr = pd.concat([df.High-df.Low,(df.High-raw_prev).abs(),(df.Low-raw_prev).abs()],axis=1).max(axis=1)
    df['Raw_ATR_14'] = raw_tr.groupby(df.Ticker).transform(lambda s:s.rolling(14).mean())
    panel = df.pivot(index='Date',columns='Ticker',values='Adj_Close')
    if panel.isna().any().any():
        raise ValueError('Assets must share a complete calendar; no forward filling')
    return df


def run_backtest(data, config, policy, entry_fn=generate_entry_signals):
    """policy: monthly_exits(holdings, ranking, config), stop_fill(pos, bar, config),
    weights(selected, snapshot, historical_adjusted_closes, config).
    Policy receives historical data only. See docs/REBECCA_BACKTEST.md for timing.
    """
    if config.capital <= 0 or not (0 <= config.commission < 1 and 0 <= config.slippage < 1):
        raise ValueError('Invalid capital/costs')
    start,end = pd.Timestamp(config.start),pd.Timestamp(config.end)
    df = data.copy(); df['Date'] = pd.to_datetime(df.Date)
    dates = pd.DatetimeIndex(sorted(df.Date.unique()))
    trading = dates[(dates>=start)&(dates<=end)]
    prior = dates[dates<trading[0]] if len(trading) else []
    if not len(prior):
        raise ValueError('Need evaluation sessions and pre-start warm-up data')
    snapshots = {d:g.set_index('Ticker') for d,g in df.groupby('Date')}
    prices = df.pivot(index='Date',columns='Ticker',values='Adj_Close')
    if snapshots[prior[-1]][['Momentum','MA_200','HV_60','ATR_14']].isna().any().any():
        raise ValueError('Insufficient warm-up at start')
    signal_data = df.copy()
    # Existing Rosie API requires all ten rows. Remove GLD competitively without
    # changing her public function or counting it toward ranks in no-gold runs.
    if not config.include_gld:
        signal_data.loc[signal_data.Ticker.eq('GLD'),'Momentum'] = -np.inf
    rankings,_,_ = entry_fn(signal_data, start=str(prior[-1].to_period('M').start_time), end=str(end.date()))
    decisions = {pd.Timestamp(d):g.set_index('Ticker') for d,g in rankings.groupby('Signal_Date') if not g.Regime.eq('WARMUP').any()}
    holdings = {}; positions = {}; cash = config.capital
    trades=[]; rows=[]; weights_rows=[]; blocked={}; pending=None
    highwater=config.capital; paused_until=None; pause_order=False
    circuit_state=policy.initial_circuit(config.capital) if hasattr(policy,'circuit') else None
    sweep=False
    total_fees=total_slippage=0.0

    def equity(bar, field):
        return cash + sum(q*bar.loc[t,field] for t,q in holdings.items())

    def execute(t, delta, reference, date, signal_date, reason):
        nonlocal cash,total_fees,total_slippage
        if abs(delta)*reference < 1e-7:
            return
        side=1 if delta>0 else -1
        fill=reference*(1+side*config.slippage)
        fee=abs(delta)*fill*config.commission
        cash -= delta*fill+fee
        holdings[t]=holdings.get(t,0)+delta
        if abs(holdings[t])<1e-9:
            holdings.pop(t,None); positions.pop(t,None)
        slip=abs(delta)*abs(fill-reference)
        total_fees+=fee; total_slippage+=slip
        trades.append(dict(Date=date,Signal_Date=signal_date,Ticker=t,Side='BUY' if side>0 else 'SELL',
                           Adjusted_Units=abs(delta),Reference_Price=reference,Fill_Price=fill,
                           Commission=fee,Slippage=slip,Reason=reason))

    def rebalance(target, date, signal_date, reason):
        nonlocal cash
        bar=snapshots[date]; nav=equity(bar,'Adj_Open')
        if any(not np.isfinite(w) or w<0 for w in target.values()) or sum(target.values())>1+1e-9:
            raise ValueError('Invalid target weights')
        # Reserve a conservative maximum turnover cost (sell all + buy all).
        budget=nav/(1+2*(config.commission+config.slippage+config.commission*config.slippage))
        desired={t:budget*w/bar.loc[t,'Adj_Open'] for t,w in target.items() if w>0}
        for t in list(holdings):
            delta=min(0,desired.get(t,0)-holdings[t])
            execute(t,delta,bar.loc[t,'Adj_Open'],date,signal_date,reason)
        previous=snapshots[dates[dates<date][-1]]
        for t,q in desired.items():
            delta=max(0,q-holdings.get(t,0))
            is_new=t not in holdings
            execute(t,delta,bar.loc[t,'Adj_Open'],date,signal_date,reason)
            if is_new and delta>0 and t!='SHY':
                entry=bar.loc[t,'Adj_Open']*(1+config.slippage)
                atr=previous.loc[t,'ATR_14']
                positions[t]=dict(entry=entry,entry_atr=atr,peak=entry,trail=entry-config.trailing_atr*atr)

                if hasattr(policy,'open_tracker'):
                    positions[t]['tracker']=policy.open_tracker(t,date,bar.loc[t],previous.loc[t],config)

    def plan(date):
        r=decisions[date]
        exits=policy.monthly_exits(holdings,r,config)
        selected=[t for t in holdings if t!='SHY' and t not in exits]
        candidates=r.loc[r.Entry_Signal.eq(1)].sort_values('Rank').index
        for t in candidates:
            if len(selected)>=3: break
            if t not in selected and (config.include_gld or t!='GLD') and blocked.get(t)!=date.to_period('M'):
                selected.append(t)
        history=prices.loc[:date]
        return (policy.weights(selected,snapshots[date],history,config),date,
                'monthly rebalance; '+('; '.join(f'{t}: {v}' for t,v in exits.items()) or 'retain/fill chairs'))

    if prior[-1] in decisions:
        pending=plan(prior[-1])
    else:
        pending=({'SHY':1.0},prior[-1],'initial SHY until next month-end')
    rows.append(dict(Date=prior[-1],Equity=config.capital,Daily_PnL=0,Commission=0,Slippage=0,SHY_Weight=0,Cash=config.capital,Paused=False))
    for date in trading:
        bar=snapshots[date]
        if pause_order:
            rebalance({'SHY':1.0},date,dates[dates<date][-1],'drawdown circuit breaker')
            pending=None; pause_order=False
        elif pending:
            target,signal_date,reason=pending
            rebalance(target,date,signal_date,reason); pending=None
        if sweep and cash > 1e-8:
            ref=bar.loc['SHY','Adj_Open']
            q=cash/(ref*(1+config.slippage)*(1+config.commission))
            execute('SHY',q,ref,date,dates[dates<date][-1],'cash sweep after close')
        sweep=False
        # Stops set before today's session; new entries use yesterday's ATR.
        stopped_today=False
        for t in list(positions):
            fill=policy.stop_fill(positions[t].copy(),bar.loc[t],config)
            if fill:
                price,reason=fill
                execute(t,-holdings[t],price,date,dates[dates<date][-1],reason)
                blocked[t]=date.to_period('M')
                stopped_today=True
        # Intraday exit proceeds cannot be invested retroactively at today's open.
        # Buy SHY next open using a cash sweep; preserves other asset quantities.
        for t,pos in positions.items():
            pos['peak']=max(pos['peak'],bar.loc[t,'Adj_High'])
            pos['trail']=max(pos['trail'],pos['peak']-config.trailing_atr*bar.loc[t,'ATR_14'])
        nav=equity(bar,'Adj_Close')
        if cash < -1e-6 or any(q<0 for q in holdings.values()):
            raise AssertionError('Negative cash/short position')
        if hasattr(policy,'circuit'):
            later=dates[dates>date]
            next_date=later[0] if len(later) else date+pd.offsets.BDay(1)
            old=circuit_state
            circuit_state=policy.circuit(old,nav,next_date)
            pause_order=(circuit_state.shy_until is not None and circuit_state.shy_until!=old.shy_until)
            paused_until=circuit_state.shy_until
            if date in decisions and not pause_order and not circuit_state.in_cooldown(next_date):
                pending=plan(date)
        else:
            highwater=max(highwater,nav)
            if paused_until is None and nav/highwater-1 <= -config.circuit_drawdown:
                paused_until=date+pd.DateOffset(months=1); pause_order=True
            if date in decisions and not pause_order:
                if paused_until is None or date>=paused_until:
                    if paused_until is not None:
                        highwater=nav; paused_until=None
                    pending=plan(date)
        rows.append(dict(Date=date,Equity=nav,Daily_PnL=nav-rows[-1]['Equity'],
                         Commission=total_fees,Slippage=total_slippage,Cash=cash,
                         SHY_Weight=holdings.get('SHY',0)*bar.loc['SHY','Adj_Close']/nav,
                         Paused=paused_until is not None))
        weights_rows.append({'Date':date,**{t:holdings.get(t,0)*bar.loc[t,'Adj_Close']/nav for t in ETFS+['SHY']},'Cash':cash/nav})
        sweep = stopped_today and pending is None and not pause_order
    return dict(equity=pd.DataFrame(rows).set_index('Date'),trades=pd.DataFrame(trades),
                weights=pd.DataFrame(weights_rows).set_index('Date'),rankings=rankings,
                config=asdict(config),policy=policy.name)

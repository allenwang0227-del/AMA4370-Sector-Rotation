"""Performance metrics and fair, same-window total-return benchmarks."""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from entry_signals import ETFS


def benchmark(data, index, tickers, config):
    """Equal initial allocations, buy first evaluation open, hold (no rebalance).

    Both benchmarks pay initial commission/slippage, mark last close (no forced sale).
    """
    first=data.loc[data.Date.eq(index[1])].set_index('Ticker')
    units={t:config.capital/len(tickers)/(first.loc[t,'Adj_Open']*(1+config.slippage)*(1+config.commission)) for t in tickers}
    panel=data.pivot(index='Date',columns='Ticker',values='Adj_Close').reindex(index[1:])
    values=panel[list(tickers)].mul(pd.Series(units)).sum(axis=1)
    return pd.concat([pd.Series([config.capital],index=index[:1]),values])


def metrics(equity, risk_free_daily=None):
    r=equity.pct_change().dropna()
    years=(equity.index[-1]-equity.index[0]).days/365.25
    excess=r if risk_free_daily is None else r-risk_free_daily.reindex(r.index)
    if excess.isna().any(): raise ValueError('Missing risk-free observations')
    vol=r.std(ddof=1)*np.sqrt(252)
    sd=excess.std(ddof=1)
    return {'Total_Return':equity.iloc[-1]/equity.iloc[0]-1,
            'CAGR':(equity.iloc[-1]/equity.iloc[0])**(1/years)-1,
            'Annualized_Volatility':vol,
            'Sharpe_Zero_RF':excess.mean()/sd*np.sqrt(252) if sd>1e-12 else np.nan,
            'Maximum_Drawdown':(equity/equity.cummax()-1).min()}


def evaluate(result, data, config, out):
    out=Path(out); out.mkdir(parents=True,exist_ok=True)
    eq=result['equity']; curves=pd.DataFrame({'Strategy':eq.Equity})
    curves['SPY buy-and-hold']=benchmark(data,eq.index,['SPY'],config)
    curves['10-ETF initial equal weight']=benchmark(data,eq.index,ETFS,config)
    summary=pd.DataFrame({c:metrics(curves[c]) for c in curves}).T
    summary.index.name='Portfolio'
    summary.to_csv(out/'performance_summary.csv')
    curves.to_csv(out/'equity_curves.csv',index_label='Date')
    for name, frame in [('daily_equity',eq),('daily_weights',result['weights'])]:
        frame.to_csv(out/(name+'.csv'),index_label='Date')
    result['trades'].to_csv(out/'trade_log.csv',index=False)
    result['rankings'].to_csv(out/'monthly_rankings.csv',index=False)
    colors=['#14876b','#4169af','#b77a24']
    for kind in ['equity','drawdown']:
        fig,ax=plt.subplots(figsize=(10,5))
        values=curves/config.capital*100 if kind=='equity' else (curves/curves.cummax()-1)*100
        for c,color in zip(values,colors): ax.plot(values.index,values[c],label=c,color=color,linewidth=1.7)
        ax.set_title('2022 stress case — integrated team rules' if config.start=='2022-01-01' and config.end=='2022-12-31' else 'Sector rotation — provisional reference policies')
        ax.set_ylabel('Wealth index (initial = 100)' if kind=='equity' else 'Drawdown (%)')
        ax.grid(alpha=.2);ax.legend(fontsize=8)
        fig.autofmt_xdate();fig.tight_layout();fig.savefig(out/(kind+'_curve.png'),dpi=180);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(10,4))
    for ax,col,label in zip(axes,['Total_Return','Maximum_Drawdown'],['Total return (%)','Maximum drawdown (%)']):
        vals=summary[col]*100
        ax.bar(['Strategy','SPY','Equal weight'],vals,color=colors)
        ax.axhline(0,color='gray',linewidth=.7)
        ax.set_title(label);ax.grid(axis='y',alpha=.2)
        for i,v in enumerate(vals): ax.text(i,v/2,f'{v:.2f}%',ha='center',color='white',weight='bold')
    fig.suptitle('2022 results after trading costs')
    fig.tight_layout();fig.savefig(out/'performance_comparison.png',dpi=180);plt.close(fig)
    fig,ax=plt.subplots(figsize=(10,5))
    im=ax.imshow(result['weights'].drop(columns='Cash').T,aspect='auto',vmin=0,vmax=1,cmap='YlGnBu',interpolation='nearest')
    ax.set_yticks(range(11),result['weights'].drop(columns='Cash').columns)
    ix=np.linspace(0,len(result['weights'])-1,7,dtype=int)
    ax.set_xticks(ix,[result['weights'].index[i].strftime('%Y-%m-%d') for i in ix],rotation=30)
    ax.set_title('Actual closing portfolio weights')
    fig.colorbar(im,ax=ax,label='Weight');fig.tight_layout();fig.savefig(out/'holdings_heatmap.png',dpi=180);plt.close(fig)
    return summary

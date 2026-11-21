from dataclasses import replace
import pandas as pd
from backtest import prepare_data,run_backtest,Config
from team_policy import TeamPolicy
from evaluation import metrics
raw=pd.read_csv('data/clean_prices.csv');cfg=Config();rows=[]
for name,c in [('Base',cfg),('Without GLD',replace(cfg,include_gld=False)),('ATR 2 / 2.5',replace(cfg,initial_atr=2,trailing_atr=2.5)),('ATR 3 / 3.5',replace(cfg,initial_atr=3,trailing_atr=3.5)),('No rank buffer',replace(cfg,hold_rank=3))]:
 r=run_backtest(prepare_data(raw),c,TeamPolicy());rows.append(dict(Variant=name,**metrics(r['equity'].Equity)))
pd.DataFrame(rows).to_csv('reports/final_2022/sensitivity.csv',index=False)
print(pd.DataFrame(rows)[['Variant','Total_Return','Maximum_Drawdown']])
q=pd.read_csv('reports/final_2022/daily_equity.csv');print('SHY average',q.SHY_Weight.iloc[1:].mean())

"""Run the integrated 2022 backtest and export evaluation results."""
from pathlib import Path
import pandas as pd
from backtest import Config, prepare_data, run_backtest
from evaluation import evaluate
from team_policy import TeamPolicy
from exit_signals import simulate_holdings_path
from entry_signals import generate_entry_signals

if __name__ == "__main__":
    root=Path(__file__).resolve().parent
    out=root/"reports"/"final_2022"
    cfg=Config()
    market=pd.read_csv(root/"data/market_data.csv",parse_dates=["Date"])
    rankings,_,_=generate_entry_signals(market,start="2021-12-01",end=cfg.end)
    trades,months=simulate_holdings_path(market,rankings,start=cfg.start,end=cfg.end)
    data=prepare_data(pd.read_csv(root/"data/clean_prices.csv"),cfg.lookbacks)
    res=run_backtest(data,cfg,TeamPolicy())
    table=evaluate(res,data,cfg,out)
    trades.to_csv(out/"harris_unweighted_trades.csv",index=False)
    months.to_csv(out/"harris_monthly_holdings.csv",index=False)
    print(table)

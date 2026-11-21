"""Use Harris's raw-price stop signals with Rebecca's total-return ledger."""
from exit_signals import add_exit_flags
from stop_loss import StopTracker
from reference_policy import ReferencePolicy

class HarrisPendingAllen(ReferencePolicy):
    name = "Harris exits; provisional Allen weights and circuit"
    def monthly_exits(self, holdings, ranking, config):
        flags=add_exit_flags(ranking.reset_index(),rank_limit=config.hold_rank).set_index("Ticker")
        return {t:flags.at[t,"Exit_Reason"] for t in holdings if t!="SHY" and flags.at[t,"Exit_Signal"]}

    def open_tracker(self,t,date,bar,previous,config):
        # Signal based on unimpacted market open; ledger charges slippage separately.
        return StopTracker(t,date,bar.Open,previous.Raw_ATR_14,config.initial_atr,config.trailing_atr)

    def stop_fill(self,position,bar,config):
        tracker=position["tracker"]
        event=tracker.update(bar.Date,bar.Open,bar.High,bar.Low,bar.Close,bar.Raw_ATR_14)
        if event:
            return event["Fill_Price"]*(bar.Adj_Close/bar.Close),event["Exit_Reason"]

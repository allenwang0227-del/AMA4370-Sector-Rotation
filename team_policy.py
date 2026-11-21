"""Harris exit rules plus Allen PR #1 allocation and circuit rules."""
from harris_adapter import HarrisPendingAllen
from position_sizing import calculate_weights
from portfolio_risk import DrawdownState,update_drawdown
class TeamPolicy(HarrisPendingAllen):
    name="Integrated Harris exits and Allen PR1 allocation"
    def weights(self,selected,snapshot,history,config):
        return calculate_weights(history,history.index[-1],selected).weights.to_dict()
    def circuit(self,state,nav,next_date):
        return update_drawdown(state,nav,next_date)
    def initial_circuit(self,capital):
        return DrawdownState(peak_nav=capital)

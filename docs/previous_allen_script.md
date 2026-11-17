# P1

Now I’ll explain how we allocate capital and control risk.

After selecting the ETFs, we need to decide how much money to invest in each one.

We use **inverse volatility weighting,** based on daily returns over the **past sixty trading days**. Simply put, an ETF with higher volatility receives a smaller allocation.

For example, XLK has an **annualized volatility** of 25 percent, while XLI and GLD each have 18 percent. Their rounded weights are 26 percent, 37 percent, and 37 percent.

**This reduces the chance that the most volatile ETF dominates our portfolio risk.**

We also apply two concentration limits. Each ETF can represent **no more than 40 percent** of the portfolio. ETFs in the **same category** can represent **no more than 50 percent** in total.

These limits help us avoid putting too much money into one asset or similar sectors.

Next, I’ll explain our risk-management rules.





# P2

We use several layers of risk control.

First, we apply a market filter. When SPY falls below its two-hundred-day moving average, we only select from XLP, XLV, XLU, and GLD. This restricts the strategy to **more defensive assets.**

Second, each position has a stop loss at 2.5 times ATR. As Harris explained, this helps control losses from **sudden price declines** between monthly reviews.

Third, we target an **estimated annualized portfolio volatility** of 15 percent. If volatility exceeds this target, we reduce all ETF positions proportionally and allocate the remaining capital to SHY.

For example, if estimated volatility is 20 percent, the scaling factor is 15 divided by 20, or 0.75. We therefore keep 75 percent in the selected ETFs and put 25 percent in SHY.

Fourth, we have a **drawdown circuit breaker**. If the portfolio falls 15 percent from its previous peak, we move the entire portfolio into SHY for one month.

Finally, our backtest includes 0.05 percent commission and the same amount of slippage per trade. If a stop loss and a trailing take-profit trigger on the same day, we **conservatively assume the stop loss happens first**.

Together, these rules determine how much we invest and when we reduce our exposure.

I’ll now hand over to Rebecca to discuss the known risks and next steps.


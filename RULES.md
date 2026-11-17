# 策略规则与接口现状

本文区分现有方案、当前代码行为和待组内定稿事项。修改本文件时说明原因和受影响模块。

## 现有方案

- 候选资产：XLK、XLY、XLE、XLF、XLI、XLB、XLP、XLV、XLU、GLD。
- SHY为剩余资金的持有工具，不参与候选资产排名；SPY作为市场过滤及比较基准。
- 动量：63、126、252交易日调整后收盘价收益率的平均值。
- 月底生成信号，下一交易日执行。
- 新入场需满足Top3、Momentum高于SHY、价格高于MA200。
- SPY低于MA200时，候选池限制为XLP、XLV、XLU、GLD。
- 出场方案包括跌出Top5、动量弱于SHY、跌破均线、2.5倍ATR止损、3倍ATR移动止损；月中卖出资金转SHY，被止损资产当月不再买回。
- 仓位方案：60日波动率倒数加权、单ETF40%上限、同类50%上限、年化波动率目标15%、回撤15%后转SHY一个月。
- 交易成本方案：每笔成交0.05%佣金和0.05%滑点。同日止损与移动止损顺序采用原方案的保守处理。

上面出场和风险控制尚未形成完整代码，不应据此声称回测已经完成。

## 当前数据口径

| 字段 | 含义 |
| --- | --- |
| `Date`, `Ticker` | 交易日期与资产代码，二者组合唯一 |
| `Open`, `High`, `Low`, `Close` | Yahoo Finance返回的OHLC字段 |
| `Adj_Close` | 调整后收盘价，用于收益、动量和当前均线计算 |
| `R3m`, `R6m`, `R12m` | 63、126、252交易日收益率 |
| `Momentum` | 上述三项收益率的平均值 |
| `MA_200` | 当前CSV为Adj_Close的200交易日简单均线 |
| `HV_60` | 60个每日调整后价格收益的样本标准差乘sqrt(252)，**已经年化** |
| `ATR_14` | 当前CSV为14日True Range的简单移动平均 |

`archive/received/indicators.py`采用Close均线、Wilder ATR及另一套列名，不能直接混用。Cheryl需确认后续正式算法。

计算组合波动率需要收益协方差矩阵；仅有每只资产的HV_60不足以得到组合波动率。所有估计只能使用决策时点及之前的数据。

## 当前可调用函数

```python
# indicators.py；输入需按Ticker、Date排序，通常用load_clean_data加载
add_all_indicators(price_data)

# entry_signals.py
generate_entry_signals(market_data, start="2005-01-01", end="2022-12-31")
# 返回 rankings, entries, monthly 三个DataFrame
```

入场代码同时输出 `Signal_Date` 和 `Next_Trading_Date`。`Within_Backtest_Execution=False` 的行不应在所选区间内执行。

`Rank`为当前市场允许池内的排名，`Global_Rank`为10只候选资产的全局排名。Harris的Top5缓冲使用哪种排名须先统一。

入场候选不是最终持仓。保留旧仓、出场、空位补入和最终持仓确定后，才交给Allen计算权重。

## 待组内确认

| 事项 | 需要统一的内容 | 协调人 |
| --- | --- | --- |
| 回测区间 | 2022单年、2022–2024或更长区间；当前信号默认止于2022 | Cheryl、Rebecca |
| 指标版本 | Adj_Close/Close均线、简单/Wilder ATR及最终列名 | Cheryl |
| 三张椅子 | 旧仓缓冲、空位补入、新Top1能否替换、少于3只时的资金预算 | Rosie、Harris、Allen |
| 资金约束 | 类型表、cap处理顺序、余款再分配方式、SHY对上限的豁免 | Allen |
| 风控执行 | 波动率检查频率、回撤观察与成交时点、“一个月”及恢复方式 | Allen、Rebecca |
| 日内止损 | 使用已知ATR与峰值、跳空成交、High/Low先后未知的处理 | Harris、Rebecca |
| 接口 | 最终持仓结构、权重输出、每日风控状态和净值传递 | 全组，Rebecca整合 |
| 额外实验 | 消融和参数敏感性的执行分工 | Allen、Rebecca |

当前数据2005年为12月动量暖身；最早完整Momentum日期为2006-01-03。如果采用2022年回测，须保留2021-12-31信号，用于2022-01-03执行。

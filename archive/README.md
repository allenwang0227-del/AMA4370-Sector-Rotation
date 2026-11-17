# 收到的文件

`received/` 保存群里提供的三个Python原文件，以及清除执行输出与运行元数据的notebook。

独立的 `data_loader.py` / `indicators.py` 与notebook不是同一个版本：独立指标脚本采用另一套列名、Close均线、Wilder ATR；当前CSV对应notebook的Adj_Close均线和简单滚动ATR。

根目录的数据脚本从notebook代码提取，仅修改读写路径，不代表全组已最终确认这一算法。正式开发前请Cheryl统一。

`received_signals/` 保存收到的2005–2022信号输出，用于验证整理后的入场代码没有改变已有结果。它们不是实际成交或最终持仓记录。

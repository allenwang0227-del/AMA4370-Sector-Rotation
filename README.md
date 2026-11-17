# AMA4370 Sector Rotation

AMA4370 Applied Algorithmic Trading Strategies 小组项目。全组在同一个仓库管理代码、数据和策略说明。

**当前状态：数据与入场信号已整理，完整回测尚未完成。** 出场、仓位、组合风控和回测整合模块由各负责人继续提交。

## 分工

| 负责人 | 模块 | 当前状态 |
| --- | --- | --- |
| Cheryl | `data_loader.py`、`indicators.py`，统一数据与规则 | 已导入数据与原代码，待确认正式指标口径 |
| Rosie | `entry_signals.py`，排名和入场候选 | 已导入，默认信号区间2005–2022 |
| Harris | `exit_signals.py`、`stop_loss.py` | 待提交 |
| Allen | `position_sizing.py`、`portfolio_risk.py` | 待提交 |
| Rebecca | `backtest.py`、`evaluation.py`及回测整合入口 | 待提交 |

每个人验证自己的模块，并协助 Rebecca 处理集成问题。函数接口和策略细节见 [RULES.md](RULES.md)。

## 第一次运行

建议使用 Python 3.11 或 3.12。在仓库根目录执行：

```bash
python -m venv .venv
```

激活虚拟环境：

```bash
# macOS / Linux
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1
```

安装依赖后，先运行已有的入场信号模块：

```bash
python -m pip install -r requirements.txt
python entry_signals.py
python -m unittest discover -s tests -v
```

输出位于 `results/entry_signals/`：

- `monthly_rankings.csv`：每月全部候选资产排名和条件判断。
- `entry_signals.csv`：满足新入场条件的候选记录，**不是已执行交易**。
- `monthly_selection_summary.csv`：每月候选清单。

目前没有完整回测入口，运行入场脚本不会生成策略收益或实际持仓。

## 数据与版本

- 共享数据：`data/market_data.csv`；清理后的价格：`data/clean_prices.csv`。
- 当前快照覆盖2005-01-03至2026-11-13，共66,024行、12个资产。详见 [数据记录](data/README.md)。
- 根目录 `data_loader.py`、`indicators.py` 从随附 `Untitled43.ipynb` 提取，保留原计算逻辑，仅调整文件路径。该版本与随附CSV一致。
- 群里另发的独立 `data_loader.py`、`indicators.py` 使用不同字段和算法，保存在 `archive/received/`，尚未作为运行入口。
- 原入场脚本保存在 `archive/received/AMA4370_Entry_Signal.py`；根目录版本只修改输入、输出路径。
- 原有三个信号CSV保存在 `archive/received_signals/`，作为导入核对依据。
- notebook已清除执行输出、执行计数和Colab元数据，代码保留。

**全组开发先使用已提交的数据快照。** 下面的下载命令会覆盖本地CSV；由Cheryl在自己的分支更新、核对后通过PR发布，其他人无需各自重新下载：

```bash
python data_loader.py
python indicators.py
```

以上两个脚本从仓库根目录运行。下载器使用Yahoo Finance；新的下载结果可能与当前快照不同。

## 提交方式

每项任务从最新 `main` 新建分支，例如 `cheryl/data`、`rosie/entry`、`harris/exits`、`allen/risk`、`rebecca/backtest`。

1. 更新本地 `main`。
2. 从 `main` 新建任务分支，修改并运行验证。
3. Commit，再Push；只Commit不会上传。
4. 开Pull Request，目标分支为 `main`。
5. 由另一位组员检查代码和验证结果后合并；涉及多模块的改动请Allen或Rebecca协调。
6. 合并后下一项任务重新从最新 `main` 开分支。

**不要直接推送 `main`，不要Force Push。** 修改他人模块、公共字段或策略规则前先协调。

图形界面及命令行操作见 [CONTRIBUTING.md](CONTRIBUTING.md)。群通知见 [docs/GROUP_NOTICE.md](docs/GROUP_NOTICE.md)。

## 目录

```text
data/                       统一价格和指标快照
archive/received/           收到的原代码、清除输出的notebook
archive/received_signals/   收到的信号输出，供核对
docs/                      旧策略方案、旧讲稿及群通知
tests/                     数据、指标和入场信号的核对
results/                   本地生成结果，Git忽略
```

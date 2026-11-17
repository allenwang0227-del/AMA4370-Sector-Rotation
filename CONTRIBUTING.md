# 小组协作操作

仓库：https://github.com/allenwang0227-del/AMA4370-Sector-Rotation

## 加入

1. 把GitHub用户名发给Allen，接受仓库协作者邀请。
2. 安装 [GitHub Desktop](https://desktop.github.com/)，登录自己的GitHub账号。
3. 点击 `File → Clone repository → URL`，填入仓库链接，选择电脑上的固定文件夹并Clone。
4. 用VS Code、PyCharm或Jupyter编辑这个克隆文件夹中的代码。

公开仓库任何人都能查看；**直接推送自己的分支仍需要协作者权限**。没有权限时先等邀请，不要各自另建仓库。

## 每项任务的操作

1. Desktop中选择此仓库，切到 `main`。
2. 点 `Fetch origin`；如显示 `Pull origin`，继续点它获取更新。
3. `Current Branch → New Branch`，基于 `main` 创建任务分支。名称例如 `allen/risk`，后续新任务用 `allen/risk-fix` 等新名称。
4. 修改自己负责的文件，运行对应验证。
5. 回到Desktop的 `Changes`，检查只选中本次需要提交的文件。
6. 在 `Summary` 写清具体修改，例如 `Add inverse volatility position weights`，点 `Commit to 分支名`。
7. 第一次点 `Publish branch`，后续点 `Push origin`。这一步完成后其他人才看得到代码。
8. 点 `Preview Pull Request → Create Pull Request`，确认 `base: main`，填写修改内容、运行命令、验证结果及未完成项。
9. 请另一位组员检查后合并。涉及公共接口或整合代码，请Allen或Rebecca检查。

PR合并后可删除任务分支；下一项任务从更新后的main重新开始。

## 自己分支如何获得别人的更新

先Commit保存自己的改动。切到main，Fetch/Pull获取最新main，再切回自己的分支，在 `Current Branch` 中选择将main合并到当前分支，然后Push。

仅拉取自己的分支，不会自动得到main的新提交。

遇到Conflict不要直接覆盖或Force Push：保留文件，记录冲突文件名和两边的分支，找对应模块负责人一起处理。

## 熟悉命令行的同学

首次克隆：

```bash
git clone https://github.com/allenwang0227-del/AMA4370-Sector-Rotation.git
cd AMA4370-Sector-Rotation
```

开始一项任务，以Allen为例：

```bash
git switch main
git pull --ff-only origin main
git switch -c allen/risk
```

写完并测试后，只暂存确实完成的文件：

```bash
git status
git add position_sizing.py portfolio_risk.py
git commit -m "Add position sizing and portfolio risk controls"
git push -u origin allen/risk
```

然后在GitHub打开PR，目标分支main。下一次任务更换分支名。

## 全组约定

- `main`是全组整合版本；开发在任务分支进行。
- 使用自己的账号提交，保留各自贡献记录。
- 不提交虚拟环境、缓存、密码、令牌和个人配置。
- 全组使用 `data/` 的统一数据，数据更新由Cheryl负责。
- `results/` 是本地运行输出。需要作为报告依据的结果，连同运行条件放入 `reports/` 后通过PR提交。
- 不擅自更改公共函数、列名、交易规则和回测区间。
- 暂未完成的模块在PR中说明，不使用空函数伪装完成。

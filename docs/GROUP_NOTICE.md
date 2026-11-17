大家之后统一用这个GitHub仓库管理AMA4370项目代码：

https://github.com/allenwang0227-del/AMA4370-Sector-Rotation

现有代码、共享CSV、分工和操作说明已整理进去。目前能生成入场信号，完整回测还要大家继续完成。请先看README和RULES.md，尤其是数据字段和待确认事项。

请把GitHub用户名发给我，我会邀请大家加入；接受邀请后才能直接Push自己的分支。Public代表任何人可以查看，不代表任何人都能修改。

第一次操作：

1. 安装GitHub Desktop并登录自己的账号。
2. File → Clone repository → URL，填上面链接，Clone到电脑固定文件夹。
3. 用自己的VS Code、PyCharm或Jupyter打开这个文件夹，按照README安装依赖。

之后每项任务：

1. 切到main，点Fetch origin，有Pull origin就再点一下。
2. Current Branch → New Branch，从最新main新建任务分支。
3. 在这个分支修改自己负责的文件并运行测试。
4. 回到Desktop检查Changes，填Summary，点Commit to自己的分支。
5. 第一次点Publish branch，之后点Push origin。只Commit还没上传。
6. 点Preview Pull Request → Create Pull Request，目标选main，写清改了什么、怎么运行、验证结果和未完成部分，请另一位组员检查；涉及整合的改动找我或Rebecca。
7. 合并后，下一项任务从更新后的main重新开分支。

分工沿用：Cheryl数据与指标；Rosie排名和入场；Harris出场和止损；Allen仓位与组合风控；Rebecca回测整合和绩效。分支可以命名cheryl/data、rosie/entry、harris/exits、allen/risk、rebecca/backtest。

大家使用仓库data目录的统一数据。修改公共字段、函数接口、策略参数或其他人的模块前先协调。main作为全组整合版本，不直接Push main，不Force Push。有Conflict先保留现场，在群里找对应负责人一起处理。

以后微信群发PR链接，GitHub上的版本作为整合依据，不再靠附件区分“最终版”。详细图文步骤见仓库CONTRIBUTING.md。

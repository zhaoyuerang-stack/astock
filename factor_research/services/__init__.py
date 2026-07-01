"""services —— UI/Agent 唯一业务入口(受控接缝)。

分层铁律:
- ``api``/``web`` 只能依赖 ``services`` + ``contracts``,不得直碰引擎。
- ``services`` 是**受控接缝**:有意允许 import core.engine / strategy_registry /
  strategies / factors / factory / lake;但不得反向 import ``api``/``web``。
- ``services.read`` 是只读查询端口:允许封装 artifact/repository 路径,不得 import
  ``services.actions`` 或触发写入/执行。
- ``services.actions`` 是写入/重任务端口:高风险动作必须经 ``action_guard``(人工授权/审计)
  或 ``jobs``(异步任务接缝),不得把 promote/register/settings 写操作做成裸函数旁路。
- ``services.agent`` 只能编排 read/actions 工具与运行态上下文,不得成为第三套核心逻辑。
- 守卫见 scripts/ci/check_layer_deps.py。

铁律护栏:services 内**绝不**旁路重算因子/估值或调低成本——回测一律走
core.engine + 固化 CostModel(见 services/actions/run_backtest.py)。
"""

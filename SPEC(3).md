# SPEC.md

# 个人量化研究分析平台架构设计文档

版本：v0.1  
定位：个人量化研究分析平台 / Research-first Quant OS  
设计范式：本体论驱动 + 控制论闭环 + AI Agent 协同  
目标用户：个人投资者、量化研究者、AI-native 投研工作流使用者、非开发型策略研究者  
核心界面形态：左侧导航栏 + 中央研究工作区 + 右侧常驻 AI Agent

---

## 1. 项目目标

本平台不是一个单纯的行情看板、回测工具或自动交易机器人，而是一个面向个人投资研究的“认知控制系统”。

它的核心目标是把个人投资研究过程结构化为：

```text
假设驱动 → 证据约束 → 状态识别 → 规则控制 → 执行动作 → 反馈修正 → 持续学习
```

平台需要帮助用户完成以下事情：

1. 管理数据源，保证行情、财务、事件、因子、组合数据可追溯、可验证。
2. 把投资想法显式建模为“假设”，而不是直接写成策略。
3. 对因子、策略、组合进行可复现研究和回测。
4. 通过控制规则约束仓位、风险预算、回撤、暴露和交易行为。
5. 让 AI Agent 常驻右侧，作为研究助手、审查员、解释器和执行建议生成器。
6. 将每一次研究沉淀为实验、结论、报告和可复用知识。

---

## 2. 设计原则

### 2.1 研究优先，而不是交易优先

第一阶段不做自动实盘交易。平台首先服务于研究、验证、复盘和风险控制。

优先级为：

```text
数据可信 > 实验可复现 > 回测可信 > 风险可控 > 决策可解释 > 交易自动化
```

### 2.2 假设优先，而不是策略优先

普通量化平台通常从“策略”开始，本平台从“假设”开始。

错误路径：

```text
数据 → 策略 → 回测 → 收益曲线
```

正确路径：

```text
投资假设 → 可计算因子 → 信号 → 策略 → 组合 → 风险 → 反馈 → 假设修正
```

### 2.3 控制对象不是市场，而是用户行为

市场不可控。平台真正控制的是：

```text
仓位
暴露
风险预算
策略启停
调仓频率
亏损容忍度
实验流程
决策纪律
```

### 2.4 AI 不直接做买卖决策

AI Agent 不负责直接推荐买入卖出。AI 的角色是：

```text
解释
审查
总结
归因
发现风险
生成研究计划
提出下一步实验
```

AI 输出必须被标注为“研究辅助内容”，不构成投资建议。

---

## 3. 总体系统架构

平台采用七层逻辑架构：

```text
1. 本体层 Ontology Layer
2. 状态层 State Layer
3. 规则层 Policy Layer
4. 控制层 Control Layer
5. 执行层 Execution Layer
6. 反馈层 Feedback Layer
7. 学习层 Learning Layer
```

### 3.1 本体层 Ontology Layer

定义平台中的核心存在物。

核心对象：

```text
Market              市场
Instrument          标的
Data                数据
Factor              因子
Hypothesis          假设
Signal              信号
Strategy            策略
Portfolio           组合
Position            持仓
Order               订单
Risk                风险
Evidence            证据
Experiment          实验
Feedback            反馈
Policy              规则
Agent               智能体
Report              报告
```

本体层的职责：

1. 定义对象边界。
2. 定义对象之间的关系。
3. 为研究、回测、组合、风控提供统一语义。
4. 让 AI Agent 能够明确知道当前讨论的是假设、因子、策略还是组合。

### 3.2 状态层 State Layer

负责识别当前系统状态。

状态类型包括：

```text
市场状态 Market Regime
数据质量状态 Data Quality State
策略健康状态 Strategy Health State
组合风险状态 Portfolio Risk State
实验运行状态 Experiment State
Agent任务状态 Agent Task State
```

典型状态示例：

```text
市场状态：强趋势 / 震荡偏强 / 震荡 / 弱势 / 流动性收缩
策略健康度：优秀 / 良好 / 中等 / 警告 / 停用
风险状态：正常 / 观察 / 预警 / 超限 / 熔断
数据状态：可用 / 延迟 / 缺失 / 异常 / 待修复
```

### 3.3 规则层 Policy Layer

负责定义系统可执行的规则。

规则类型：

```text
入场规则
出场规则
仓位规则
止损规则
调仓规则
市场状态过滤规则
风险预算规则
策略熔断规则
数据质量准入规则
实验准入规则
```

示例规则：

```yaml
risk_policy:
  max_single_position_weight: 0.10
  max_industry_weight: 0.30
  max_strategy_weight: 0.40
  max_portfolio_drawdown_warning: -0.08
  max_portfolio_drawdown_stop: -0.12
  max_turnover_daily: 0.30
```

### 3.4 控制层 Control Layer

控制层是系统核心。

控制目标：

```text
提升风险调整后收益
降低行为冲动
防止过拟合策略进入组合
防止组合暴露失控
防止数据错误污染研究结果
```

控制对象：

```text
仓位
暴露
风险预算
策略权重
实验流程
交易频率
决策权限
```

控制动作：

```text
加仓
减仓
暂停
退出
重测
降级
归档
生成报告
请求人工确认
```

### 3.5 执行层 Execution Layer

执行层不等于实盘交易。第一阶段主要执行研究动作和模拟动作。

执行内容：

```text
数据更新
因子计算
策略回测
组合模拟
调仓计划生成
风险检查
报告生成
AI任务执行
实验归档
```

### 3.6 反馈层 Feedback Layer

反馈层记录策略、组合、实验和 Agent 的实际结果。

反馈指标：

```text
收益
回撤
胜率
盈亏比
换手率
IC
Rank IC
IC_IR
滑点
交易成本
风险暴露
预警次数
实验成功率
报告采纳率
```

### 3.7 学习层 Learning Layer

学习层负责沉淀研究结论。

学习动作：

```text
修正假设
更新策略健康度
调整参数边界
淘汰失效策略
沉淀研究报告
更新 Agent 记忆上下文
形成可复用实验模板
```

---

## 4. 三栏 Web 端信息架构

平台 Web 端采用三栏布局：

```text
左侧：导航栏
中间：主研究工作区
右侧：AI Agent 常驻协作栏
```

### 4.1 为什么采用三栏布局

三栏布局是本平台的核心产品形态。

原因：

1. 左侧导航负责稳定的信息架构。
2. 中间区域承载高密度图表、表格和分析任务。
3. 右侧 Agent 始终保持上下文，不打断主工作流。
4. 用户在研究、回测、组合、风控页面中都可以随时询问、解释、生成报告。
5. AI 不应该隐藏在弹窗中，而应该作为“常驻研究副驾驶”。

### 4.2 左侧导航栏

左侧栏固定宽度，深蓝底色，负责一级模块导航。

导航项：

```text
总览
数据中心
因子研究
策略回测
组合管理
风险控制
研究实验
AI研究助手
系统设置
```

底部状态：

```text
系统运行正常
数据更新时间
折叠按钮
帮助入口
设置入口
退出入口
```

### 4.3 中央主工作区

中央区域是主分析区，每个页面根据模块变化。

共同结构：

```text
顶部搜索栏
日期选择器
通知入口
用户信息
页面标题
筛选器 / 配置区
KPI 卡片
主图表区
表格 / 结果区
操作按钮
```

### 4.4 右侧 AI Agent 栏

右侧 Agent 栏常驻，不随页面跳转消失，但内容根据当前页面上下文变化。

固定结构：

```text
Agent Header
当前任务 / 上下文
对话区
快捷操作
建议的下一步
关注列表 / 预警
输入框
```

Agent 能力：

```text
解释当前页面数据
生成研究报告
审查回测过拟合
检查数据质量
分析风险来源
生成调仓建议
总结实验结果
推荐下一步研究
```

---

## 5. 页面级设计规格

## 5.1 总览页

导航高亮：`总览`

页面目标：展示平台当前整体状态，是每日进入平台后的默认工作台。

中央模块：

```text
研究流程条
KPI 卡片
组合净值与基准
市场状态识别
策略健康度监控
因子研究看板
风险预警
今日研究结论
今日研究动态
当前持仓表
```

KPI 卡片：

```text
组合净值
今日收益
最大回撤
跟踪误差
策略健康度
```

右侧 Agent：

```text
当前任务：分析组合当前表现与风险暴露
快捷操作：新建研究 / 策略回测 / 因子分析 / 组合诊断 / 风险归因 / 数据可视化
建议下一步：生成组合风险归因报告 / 分析收益回落原因 / 查看行业暴露
关注列表：策略、组合、指数、风险项
```

---

## 5.2 数据中心页

导航高亮：`数据中心`

页面目标：统一管理数据资源、数据质量、数据流水线和数据更新任务。

中央模块：

```text
数据覆盖率
今日更新
数据质量评分
API/任务成功率
数据源目录
数据集列表
数据流水线状态
数据质量监控
更新日志
最近入库任务
```

数据源目录：

```text
行情数据
财务数据
宏观数据
事件新闻
另类数据
```

数据质量指标：

```text
缺失值比例
异常值比例
复权一致性
停牌识别率
可用日检查通过率
API 成功率
任务成功率
```

右侧 Agent：

```text
数据 QA
异常解释
数据洞察
检查缺失值
生成数据质量报告
修复任务建议
```

---

## 5.3 因子研究页

导航高亮：`因子研究`

页面目标：研究单因子和多因子的有效性、稳定性、相关性与组合适用性。

中央模块：

```text
股票池筛选
时间区间
调仓频率
中性化方式
分层数
IC 均值
Rank IC
IC_IR
多空收益
换手率
胜率
因子库
IC 时序与多空累计收益
分组收益与单调性
因子相关性热力图
风格暴露
行业暴露
研究笔记与结论
```

重点审查指标：

```text
IC 是否稳定
Rank IC 是否稳定
分层收益是否单调
多空收益是否被少数极端样本贡献
交易成本后是否仍有效
样本外是否衰减
因子是否与已有因子高度相关
```

右侧 Agent：

```text
因子表现解读
因子改进建议
推荐新因子
生成因子研究报告
解释 IC 指标
分析单调性
检查过拟合
```

---

## 5.4 策略回测页

导航高亮：`策略回测`

页面目标：配置策略、运行回测、审查回测可信度和策略健康度。

中央模块：

```text
策略配置栏
年化收益
夏普比率
最大回撤
胜率
收益回撤比
换手率
累计净值曲线
回撤曲线
月度收益热力图
参数设置
参数敏感性
交易成本分析
样本内 vs 样本外
策略健康诊断
最近交易记录
```

必须支持的策略模板：

```text
Top N 因子组合
多因子增强
放量突破
行业轮动
趋势过滤
低估值组合
```

右侧 Agent：

```text
回测结果解读
过拟合检查
关键观察
建议下一步实验
导出回测报告
保存策略模板
创建组合
启动模拟盘
```

---

## 5.5 组合管理页

导航高亮：`组合管理`

页面目标：管理当前组合、持仓、调仓计划、目标组合和订单篮子。

中央模块：

```text
组合净值
现金占比
持仓数量
组合波动率
本周调仓数
行业分布
风格暴露
市值分布
风险暴露
当前持仓表
调仓执行进度
调仓计划
目标组合 vs 当前组合
订单篮子
备选观察池
```

组合表字段：

```text
代码
名称
权重
市值
成本
现价
收益率
行业
风险状态
目标权重
调仓建议
```

右侧 Agent：

```text
组合优化助手
调仓解读
情景模拟 What-if
优化建议
一键生成优化组合
```

---

## 5.6 风险控制页

导航高亮：`风险控制`

页面目标：监控组合风险、策略风险、风险预算和熔断规则。

中央模块：

```text
当前回撤
组合 VaR
行业集中度
单票集中度
风险预算使用率
预警数量
回撤曲线
滚动波动率
因子/行业敞口
压力测试概览
风险敞口热力图
风险预警
风险规则 / 熔断规则
情景分析
风控操作建议
风控执行记录
```

风险动作：

```text
降仓
停止开仓
对冲建议
生成风控报告
调整风控规则
```

右侧 Agent：

```text
风险解读
主要风险来源
建议控制措施
生成风控报告
分析风险来源
查看压力测试
优化风险敞口
```

---

## 5.7 研究实验页

导航高亮：`研究实验`

页面目标：管理假设池、实验、实验状态、对比、历史和结论。

中央模块：

```text
假设池
运行中
已完成
已归档
实验总数
运行中数量
成功率
平均运行时长
实验列表
实验流程 Pipeline
实验对比
实验历史 Timeline
结论与备注
```

实验流程：

```text
假设 → 因子 → 回测 → 验证 → 结论
```

实验表字段：

```text
实验名称
假设
数据版本
参数
状态
负责人
结果摘要
更新时间
```

右侧 Agent：

```text
生成实验计划
总结实验结果
推荐后续实验
对比实验
解释指标
生成报告
导出表格
```

---

## 5.8 AI研究助手页

导航高亮：`AI研究助手`

页面目标：提供完整 Agent 工作台，而不仅是右侧聊天栏。

中央模块：

```text
任务阶段 Pipeline
当前任务
上下文
工具调用记录
生成中的报告
研究对话
阶段性指标
报告预览
可执行建议
任务进度
```

Agent 任务类型：

```text
数据检查
因子分析
风险诊断
组合优化
策略回测
报告生成
```

右侧 Agent：

```text
快捷指令
记忆与上下文
监控面板
关注列表
输入框
```

---

## 5.9 系统设置页

导航高亮：`系统设置`

页面目标：配置工作区、数据源、回测默认参数、风险规则、AI 模型、权限和集成。

中央模块：

```text
账户与工作区
数据源配置
回测默认参数
风险规则
AI模型与Agent配置
通知与告警
权限与安全
界面偏好
集成/API
系统状态
备份与快照
```

右侧 Agent：

```text
配置助手
配置体检
最佳实践推荐
优化回测并发数
数据源延迟提醒
启用 2FA 建议
导出当前配置
导入配置文件
生成安全报告
```

---

## 6. 核心模块边界

## 6.1 Data Hub 模块

职责：

```text
数据采集
数据清洗
数据标准化
数据质量检测
数据版本管理
数据集目录管理
数据可用性标记
```

不负责：

```text
策略逻辑
组合构建
交易执行
AI 总结
```

## 6.2 Factor Research 模块

职责：

```text
因子定义
因子计算
因子回测
IC 分析
分组收益
因子相关性
因子暴露
因子结论沉淀
```

## 6.3 Backtest 模块

职责：

```text
策略参数配置
信号生成
组合构建
交易成本模拟
回测指标计算
样本内外验证
参数敏感性分析
策略健康度判断
```

## 6.4 Portfolio 模块

职责：

```text
持仓管理
目标组合生成
调仓计划
订单篮子
行业与风格暴露
组合净值
组合绩效归因
```

## 6.5 Risk Control 模块

职责：

```text
风险指标监控
风险预算管理
回撤控制
集中度控制
压力测试
风险预警
熔断规则
风控动作建议
```

## 6.6 Experiment Lab 模块

职责：

```text
假设管理
实验管理
实验运行状态
实验对比
实验结论
实验归档
研究复现
```

## 6.7 AI Agent 模块

职责：

```text
上下文感知
页面解释
实验生成
报告生成
过拟合审查
风险解释
数据异常解释
下一步建议
```

---

## 7. 核心数据模型

## 7.1 Hypothesis

```yaml
hypothesis:
  hypothesis_id: string
  name: string
  description: string
  market_assumption: string
  expected_mechanism: string
  failure_condition: string
  related_factors: list[string]
  related_strategies: list[string]
  status: draft | testing | validated | rejected | archived
  created_at: datetime
  updated_at: datetime
```

## 7.2 FactorDefinition

```yaml
factor_definition:
  factor_id: string
  name: string
  hypothesis_id: string
  formula: string
  lookback_window: integer
  frequency: daily | weekly | monthly
  universe: string
  neutralization_method: none | industry | market_cap | industry_market_cap
  winsorize_method: string
  standardize_method: string
  direction: positive | negative
  created_at: datetime
```

## 7.3 Experiment

```yaml
experiment:
  experiment_id: string
  name: string
  hypothesis_id: string
  factor_id: string
  strategy_id: string
  data_version: string
  code_version: string
  config_hash: string
  start_date: date
  end_date: date
  parameters: object
  status: pending | running | completed | failed | archived
  owner: string
  created_at: datetime
  updated_at: datetime
```

## 7.4 ExperimentResult

```yaml
experiment_result:
  experiment_id: string
  annual_return: float
  max_drawdown: float
  sharpe: float
  win_rate: float
  ic_mean: float
  rank_ic_mean: float
  ic_ir: float
  long_short_return: float
  turnover: float
  cost_adjusted_return: float
  conclusion: string
  pass_review: boolean
  created_at: datetime
```

## 7.5 Strategy

```yaml
strategy:
  strategy_id: string
  name: string
  type: factor_topn | multi_factor | breakout | rotation | timing
  hypothesis_id: string
  entry_rule: string
  exit_rule: string
  position_rule: string
  stop_loss_rule: string
  regime_filter: string
  risk_budget: float
  status: draft | active | paused | retired
```

## 7.6 PortfolioState

```yaml
portfolio_state:
  portfolio_id: string
  date: date
  nav: float
  cash_ratio: float
  gross_exposure: float
  net_exposure: float
  max_drawdown: float
  volatility: float
  var_95_1d: float
  industry_exposure: object
  factor_exposure: object
  risk_status: normal | watch | warning | breach | stopped
```

## 7.7 ControlAction

```yaml
control_action:
  action_id: string
  date: datetime
  object_type: data | factor | strategy | portfolio | experiment | agent
  object_id: string
  trigger_state: string
  action: increase | decrease | pause | stop | retest | archive | report | alert
  reason: string
  recommendation: string
  requires_confirmation: boolean
  executed: boolean
  executed_by: human | system | agent
```

## 7.8 AgentTask

```yaml
agent_task:
  task_id: string
  page_context: overview | data | factor | backtest | portfolio | risk | experiment | assistant | settings
  user_request: string
  context_refs: list[string]
  tools_used: list[string]
  status: pending | running | completed | failed
  output_type: explanation | report | recommendation | check | summary
  output: string
  confidence: float
  created_at: datetime
```

---

## 8. 技术架构选型

## 8.1 MVP 技术栈

MVP 采用本地优先、研究优先的架构。

```text
前端：Streamlit / Next.js 二选一
后端：Python FastAPI
数据处理：Polars + pandas
分析数据库：DuckDB
本地存储：Parquet 文件湖
元数据：SQLite / DuckDB
任务调度：scripts + cron，后续 Prefect
回测：自研轻量向量化回测
AI：LLM API + RAG + 工具调用
配置：YAML
版本管理：Git
```

### 推荐第一阶段

如果以最快验证为目标：

```text
Python + Polars + DuckDB + Parquet + Streamlit + YAML + Git
```

如果以 Web 产品原型为目标：

```text
Next.js + FastAPI + DuckDB + Parquet + Python Worker
```

## 8.2 推荐目录结构

```text
personal-quant-platform/
├── SPEC.md
├── README.md
├── pyproject.toml
├── config/
│   ├── data.yaml
│   ├── backtest.yaml
│   ├── risk.yaml
│   ├── agent.yaml
│   └── universe.yaml
├── data/
│   ├── raw/
│   ├── processed/
│   ├── factors/
│   ├── signals/
│   └── backtests/
├── src/
│   ├── data/
│   ├── factors/
│   ├── strategies/
│   ├── backtest/
│   ├── portfolio/
│   ├── risk/
│   ├── experiments/
│   ├── reports/
│   ├── agents/
│   └── api/
├── web/
│   ├── app/
│   ├── components/
│   ├── layouts/
│   ├── pages/
│   └── styles/
├── notebooks/
├── experiments/
├── reports/
└── tests/
```

---

## 9. Agent 设计

## 9.1 Agent 类型

```text
Data QA Agent
Factor Research Agent
Backtest Review Agent
Portfolio Optimization Agent
Risk Control Agent
Experiment Planner Agent
Report Agent
Settings Assistant Agent
```

## 9.2 Agent 不可越权原则

AI Agent 默认只能建议，不直接执行高风险动作。

需要人工确认的动作：

```text
修改风险规则
创建调仓计划
提交订单
启动实盘模拟
删除数据源
归档策略
启停策略
修改系统配置
```

允许自动执行的动作：

```text
解释指标
总结报告
检查缺失值
生成实验计划草稿
对比实验结果
生成风险报告草稿
生成研究结论草稿
```

## 9.3 Agent 上下文来源

```text
当前页面
当前筛选器
当前图表
当前表格选中项
当前组合
当前实验
最近报告
用户输入
历史 Agent 任务
```

## 9.4 Agent 输出格式

Agent 输出必须结构化：

```yaml
agent_output:
  summary: string
  evidence: list[string]
  risk: list[string]
  recommendation: list[string]
  next_actions: list[string]
  confidence: float
  requires_human_confirmation: boolean
```

---

## 10. 控制规则设计

## 10.1 数据控制回路

目标：保证数据可信。

控制规则：

```text
价格缺失 → 标记不可用
复权异常 → 进入异常检查
停牌 → 不允许成交
涨停 → 不允许买入
跌停 → 不允许卖出
财报未公告 → 不允许使用
数据延迟超过阈值 → 预警
```

## 10.2 研究控制回路

目标：防止回测欺骗。

控制规则：

```text
未做样本外验证 → 不允许进入策略池
交易成本后收益消失 → 拒绝进入组合
参数敏感性过高 → 降级
收益来自少数极端样本 → 降级
未来函数风险未排除 → 阻断
因子相关性过高 → 要求正交化或剔除
```

## 10.3 组合控制回路

目标：控制真实风险。

控制规则：

```text
单票权重 > 10% → 预警
行业权重 > 30% → 预警
组合回撤 > 8% → 风险提示
组合回撤 > 12% → 降仓建议
策略连续亏损 3 次 → 降低策略权重
策略健康度 Red → 暂停新开仓
VaR 超限 → 触发风控检查
```

---

## 11. MVP 范围

## 11.1 v0.1 必做

```text
三栏 Web Shell
总览页
数据中心页
因子研究页
策略回测页
组合管理页
风险控制页
研究实验页
右侧 AI Agent 栏
基础数据模型
本地 Parquet + DuckDB
A 股日频数据
3 个基础因子
1 个多因子 TopN 策略
1 个放量突破策略
基础回测引擎
基础风险规则
Markdown / HTML 报告生成
```

## 11.2 v0.1 不做

```text
自动实盘交易
高频交易
多人权限系统
复杂微服务
Kubernetes
Kafka
完整 MLOps
复杂 NLP 新闻系统
商业级 SaaS 计费
```

## 11.3 v0.2

```text
A 股真实交易约束
涨跌停处理
停牌处理
ST 过滤
新股过滤
财报公告日处理
指数成分历史变化
行业分类历史变化
实验版本管理
AI 回测审查
```

## 11.4 v0.3

```text
Prefect 调度
MLflow 或自研实验追踪
模拟盘
更完整的风控规则
报告模板系统
Agent 工具调用链
RAG 知识库
```

## 11.5 v1.0

```text
FastAPI 服务化
PostgreSQL 元数据
对象存储
Next.js 前端
权限系统
团队协作
模拟盘 / 实盘接口
策略市场或模板库
```

---

## 12. 非功能性要求

## 12.1 可复现性

每次实验必须记录：

```text
数据版本
代码版本
参数配置
股票池
时间区间
交易成本
滑点
调仓规则
风险规则
运行时间
运行人 / Agent
```

## 12.2 可审计性

所有关键动作都需要写入日志：

```text
数据更新
因子计算
策略回测
调仓建议
风险预警
Agent 输出
用户确认
配置变更
```

## 12.3 可解释性

所有策略结论必须包含：

```text
假设
证据
指标
风险
失效条件
下一步验证
```

## 12.4 安全性

```text
API Key 加密存储
敏感配置不进入 Git
Agent 不直接读取未授权文件
Agent 高风险操作需人工确认
导出报告需标注免责声明
```

---

## 13. 页面状态与交互规范

所有页面需要支持以下状态：

```text
Loading
Empty
Error
Partial Data
Stale Data
Ready
Running
Completed
```

所有数据卡片需要显示：

```text
指标名称
当前值
变化值
更新时间
解释入口
```

所有图表需要支持：

```text
时间范围切换
指标说明
导出图片
查看原始数据
询问 AI
```

所有表格需要支持：

```text
搜索
筛选
排序
分页
导出
选中后发送给 AI
```

---

## 14. 关键判断

本平台的核心差异不是“功能更多”，而是“研究过程被控制”。

普通平台回答：

```text
这个策略赚钱吗？
```

本平台回答：

```text
这个策略基于什么假设？
证据是否充分？
数据是否可信？
是否存在未来函数？
是否通过样本外验证？
当前市场状态是否适配？
组合是否暴露过度？
如果错了如何降风险？
```

最终产品定义：

```text
个人量化研究分析平台 = 假设管理系统 + 数据质量系统 + 实验系统 + 回测系统 + 组合控制系统 + 风险控制系统 + AI 研究助手
```

最终目标：

```text
让个人投资者像管理实验室一样管理投资研究，像控制系统一样管理风险与行为。
```

---

## 15. 下一步开发建议

第一阶段开发顺序：

```text
1. 建立项目目录与配置系统
2. 实现数据中心最小数据流
3. 实现因子计算与因子研究页
4. 实现轻量回测引擎
5. 实现总览页和组合页
6. 实现风险控制规则
7. 实现实验记录系统
8. 实现右侧 AI Agent 栏
9. 实现报告生成
10. 做一次完整端到端闭环
```

第一条端到端闭环：

```text
下载 A 股日线数据
→ 清洗复权
→ 计算动量 / 波动率 / 成交量因子
→ 运行 TopN 多因子策略
→ 生成组合净值
→ 计算风险指标
→ 生成研究报告
→ 由 AI Agent 解释结果与风险
```


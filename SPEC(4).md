# SPEC.md

# 个人量化研究分析平台系统架构设计文档

版本：v0.2  
状态：Draft  
产品定位：AI-native 个人量化研究与投资认知控制系统  
核心架构：DLDAF-C/E Architecture  
核心链路：Data → Logic → Decision → Action → Feedback → Control → Evolution  
核心界面：左侧导航栏 + 中央研究工作区 + 右侧常驻 AI Agent  
目标阶段：产品级 MVP，可支持早期付费内测用户使用  

---

## 0. 文档目的

本文档用于定义“个人量化研究分析平台”的系统规格、产品边界、核心本体、控制论闭环、Agent 体系、Web 端结构、技术架构、数据模型、权限边界、成本治理和 MVP 交付范围。

本平台不应被设计为普通行情软件、回测工具、荐股工具或自动交易机器人。它应被设计为一个以数据为感知、以逻辑为认知、以决策为约束、以行动为执行、以反馈为修正、以控制为稳定、以进化为长期改进的个人投资研究控制系统。

核心问题不是“系统如何告诉用户买什么”，而是：

```text
一个投资想法是否可被清晰定义？
它是否有数据证据？
它是否通过回测审查？
它是否适合当前市场状态？
它是否超过用户风险预算？
它是否值得进入观察池、模拟盘或策略池？
当它失效时，系统如何识别、降级、暂停和复盘？
```

---

## 1. 产品定位

### 1.1 一句话定义

本平台是一个面向个人高阶投资者、职业交易者和 AI-native 投研用户的产品级量化研究工作台，用 AI Agent 辅助用户完成数据检查、假设建模、因子研究、策略回测、组合管理、风险控制、研究实验、报告生成和持续复盘。

### 1.2 产品不是

本平台第一阶段不是：

```text
不是自动荐股软件
不是自动实盘交易机器人
不是普通行情看板
不是只给程序员用的量化框架
不是纯聊天式 AI 投顾
不是承诺收益率的投资产品
不是机构级 OMS/EMS 交易系统
```

### 1.3 产品是

本平台第一阶段是：

```text
研究工作台
因子验证系统
策略审查系统
风险控制系统
实验管理系统
报告生成系统
Agent 协作系统
个人投资认知审计系统
```

### 1.4 目标用户

第一阶段目标用户：

```text
高阶个人投资者
职业交易者
量化研究爱好者
非开发型系统化投资者
AI-native 投研工具使用者
有 50 万至 500 万以上可投资资产的个人用户
```

第二阶段目标用户：

```text
小型私募
投顾工作室
家办研究团队
财经研究团队
小型 AI 投研团队
```

### 1.5 核心价值主张

```text
不是告诉用户买什么，而是帮助用户判断一个投资想法是否值得相信。
```

平台提供的价值：

```text
让投资假设可定义
让数据来源可追溯
让因子研究可验证
让回测结果可审查
让策略状态可监控
让组合风险可控制
让 Agent 输出可审计
让研究结论可复用
让系统在反馈中受控进化
```

---

## 2. 总体架构原则

### 2.1 DLDAF-C/E 架构

本平台采用 DLDAF-C/E 架构：

```text
Data       数据层：系统观察到什么
Logic      逻辑层：系统如何解释数据
Decision   决策层：系统如何形成受约束的判断
Action     行动层：系统允许执行什么动作
Feedback   反馈层：行动结果如何被记录
Control    控制层：系统如何识别偏差并稳定自身
Evolution  进化层：系统如何在规则边界内改进
```

整体闭环：

```text
Data → Logic → Decision → Action → Feedback → Control → Evolution → Updated Logic / Policy
```

### 2.2 核心架构原则

```text
No Decision Without Data
没有数据，不形成决策。

No Decision Without Logic
没有明确逻辑，不形成决策。

No Action Without Decision
没有决策对象，不触发行动。

No Execution Without Policy
没有权限、规则和确认，不执行高风险动作。

No Evolution Without Feedback
没有反馈，不更新系统状态。

No Agent Action Without Audit
Agent 的关键输出、工具调用和建议必须可审计。
```

### 2.3 研究优先，交易后置

第一阶段优先级：

```text
数据可信 > 实验可复现 > 回测可信 > 风险可控 > 决策可解释 > 报告可生成 > 交易自动化
```

第一阶段不做自动实盘交易。系统可以生成调仓建议、风险控制建议、模拟组合和研究报告，但不得自动实盘下单。

### 2.4 本体优先，页面后置

页面只是入口，本体才是系统内核。

页面模块包括：

```text
总览
数据中心
因子研究
策略回测
组合管理
风险控制
研究实验
AI 研究助手
系统设置
```

但系统内核必须始终围绕：

```text
Data
Logic
Decision
Action
Feedback
Control
Evolution
```

---

## 3. 核心本体模型

### 3.1 一级本体对象

```text
User              用户
Workspace         工作区
DataSource        数据源
Dataset           数据集
DataVersion       数据版本
Instrument        标的
Market            市场
MarketRegime      市场状态
Feature           特征
Factor            因子
Hypothesis        投资假设
Signal            信号
Strategy          策略
Backtest          回测
Experiment        实验
Portfolio         组合
Position          持仓
RiskMetric        风险指标
RiskAlert         风险预警
Policy            规则
Decision          决策
Action            行动
Feedback          反馈
EvolutionEvent    进化事件
Agent             智能体
AgentTask         Agent 任务
Report            报告
Quota             额度
AuditLog          审计日志
```

### 3.2 本体关系

```text
DataSource produces Dataset
Dataset has DataVersion
Dataset describes Instrument / Market / Event
Feature is derived from Dataset
Factor is composed from Feature
Hypothesis is supported by Factor / Evidence
Strategy is generated from Hypothesis / Signal
Backtest evaluates Strategy
Experiment records Hypothesis / Factor / Strategy / Backtest
Portfolio uses Strategy / Signal
Position belongs to Portfolio
RiskMetric observes Portfolio / Strategy / Factor
RiskAlert is triggered by RiskMetric / Policy
Decision is generated from Data + Logic + Policy
Action is triggered by Decision
Feedback is produced by Action / Result / User Response
EvolutionEvent updates Health / Priority / Status / Policy Proposal
AgentTask reads Context and calls Tools
Report summarizes Experiment / Strategy / Portfolio / Risk
```

### 3.3 状态型对象

本平台必须显式维护状态，而不是只存结果。

```text
DataQualityState: available / delayed / missing / abnormal / quarantined
FactorHealthState: draft / testing / validated / monitoring / decaying / retired
StrategyState: idea / testing / observation / simulation / active / degraded / paused / retired
PortfolioRiskState: green / yellow / orange / red / black
ExperimentState: draft / queued / running / completed / failed / archived
AgentTaskState: idle / planning / fetching / running_tool / generating / waiting_confirmation / completed / failed / limited
DecisionState: proposed / pending_confirmation / approved / rejected / executed / expired
EvolutionState: auto_applied / proposed / rejected / reverted
```

---

## 4. DLDAF-C/E 分层设计

## 4.1 Data Layer：数据层

### 4.1.1 职责

Data Layer 负责定义系统能观察什么，以及这些观察是否可信。

包括：

```text
行情数据
财务数据
指数数据
行业分类
宏观数据
事件新闻
因子数据
回测结果
组合持仓
风险指标
用户行为
Agent 对话与工具调用记录
```

### 4.1.2 关键能力

```text
数据接入
数据版本管理
数据质量检查
数据血缘追踪
数据可用日管理
数据异常隔离
数据访问权限控制
```

### 4.1.3 数据准入规则

任何数据进入研究流程前必须经过：

```text
完整性检查
异常值检查
复权一致性检查
停牌/涨跌停识别
财报可用日检查
数据版本记录
数据源记录
```

财务数据必须区分：

```text
财报期末日
公告日
入库日
策略可使用日
```

否则视为未来函数风险。

---

## 4.2 Logic Layer：逻辑层

### 4.2.1 职责

Logic Layer 负责把数据转化为解释、判断和规则。

包括：

```text
因子计算逻辑
策略交易逻辑
回测成交逻辑
风险计算逻辑
组合优化逻辑
市场状态识别逻辑
Agent 推理逻辑
报告生成逻辑
成本控制逻辑
```

### 4.2.2 四类逻辑

```text
Descriptive Logic 描述逻辑：发生了什么
Diagnostic Logic  诊断逻辑：为什么发生
Predictive Logic  预测逻辑：可能会怎样
Prescriptive Logic 处方逻辑：应该怎么做
```

示例：

```text
描述：组合今日收益 -1.2%
诊断：主要来自 TMT 暴露和动量因子回撤
预测：若市场继续下跌 5%，组合可能回撤 3.8%
处方：建议降低 TMT 暴露并暂停新增高波动持仓
```

### 4.2.3 逻辑版本化

所有关键逻辑必须版本化：

```text
factor_formula_version
strategy_rule_version
backtest_engine_version
risk_policy_version
agent_prompt_version
report_template_version
model_router_version
```

研究结果必须记录所使用的逻辑版本。

---

## 4.3 Decision Layer：决策层

### 4.3.1 职责

Decision Layer 负责把 Logic 输出转化为受约束的决策对象。

系统不得从 Logic 直接跳到 Action。所有关键行动必须通过 Decision Object。

### 4.3.2 Decision Object

示例结构：

```json
{
  "decision_id": "DEC_20260610_001",
  "decision_type": "strategy_review",
  "source": "Backtest Auditor Agent",
  "target_object": {
    "type": "strategy",
    "id": "strategy_breakout_001",
    "name": "放量突破策略"
  },
  "data_inputs": [
    "backtest_result_EXP_001",
    "risk_report_RISK_001"
  ],
  "logic_used": [
    "backtest_audit_policy_v1",
    "overfit_check_v1"
  ],
  "recommendation": "enter_observation_pool",
  "confidence": 0.76,
  "risk_level": "yellow",
  "requires_confirmation": true,
  "allowed_actions": [
    "create_observation_record",
    "generate_audit_report"
  ],
  "forbidden_actions": [
    "auto_trade",
    "auto_promote_to_live"
  ],
  "status": "pending_confirmation"
}
```

### 4.3.3 决策类型

```text
factor_validation_decision
strategy_promotion_decision
strategy_degradation_decision
portfolio_rebalance_decision
risk_control_decision
data_quarantine_decision
report_generation_decision
agent_model_selection_decision
quota_limit_decision
evolution_proposal_decision
```

---

## 4.4 Action Layer：行动层

### 4.4.1 职责

Action Layer 执行系统允许的动作。任何会改变系统状态的操作都属于 Action。

### 4.4.2 行动分级

#### Level 0：只读动作

```text
读取当前页面上下文
读取回测摘要
读取因子指标
读取组合状态
读取风险预警
```

#### Level 1：低风险动作

```text
生成解释
生成报告草稿
生成实验建议
生成风险说明
生成调仓建议草稿
```

#### Level 2：中风险动作，需要确认

```text
创建实验
运行回测
生成正式报告
创建风险检查任务
保存因子定义
保存策略草稿
```

#### Level 3：高风险动作，强确认

```text
修改策略参数
修改风控阈值
修改组合目标权重
修改数据源优先级
改变策略生命周期状态
```

#### Level 4：第一阶段禁止动作

```text
自动实盘下单
自动加仓/减仓
自动删除关键数据
自动删除历史实验
自动关闭风险预警
绕过风控规则
承诺收益
```

---

## 4.5 Feedback Layer：反馈层

### 4.5.1 职责

Feedback Layer 记录行动后的结果，用于控制与进化。

反馈来源：

```text
回测结果
模拟盘表现
组合收益
风险事件
用户是否采纳建议
用户是否修改报告
Agent 输出评分
任务失败记录
AI 成本消耗
数据质量变化
```

### 4.5.2 反馈类型

```text
performance_feedback
risk_feedback
user_feedback
agent_quality_feedback
cost_feedback
data_quality_feedback
experiment_feedback
```

### 4.5.3 反馈必须可追踪

每条反馈需要关联：

```text
source_action_id
source_decision_id
target_object_type
target_object_id
metric_before
metric_after
user_response
created_at
```

---

## 4.6 Control Layer：控制层

### 4.6.1 职责

Control Layer 负责计算目标与实际之间的偏差，并产生控制动作建议。

控制对象：

```text
数据质量
因子健康度
策略健康度
组合风险
Agent 输出质量
AI 成本
用户行为边界
```

### 4.6.2 Error Signal 误差信号

系统必须显式计算误差信号。

示例：

```text
目标：组合最大回撤 < 10%
实际：当前回撤 8.7%
误差：距离预警线 1.3pp
控制动作：进入 orange 状态，建议降低风险暴露
```

```text
目标：Rank IC > 0.04
实际：Rank IC 过去 4 周均值 0.012
误差：因子有效性衰减
控制动作：降低因子健康度，触发重测建议
```

### 4.6.3 控制回路

系统至少包含五个控制回路：

```text
Data Control Loop 数据控制闭环
Factor Control Loop 因子控制闭环
Strategy Control Loop 策略控制闭环
Portfolio Risk Control Loop 组合风险控制闭环
Agent Quality Control Loop Agent 质量控制闭环
```

---

## 4.7 Evolution Layer：受控进化层

### 4.7.1 职责

Evolution Layer 不直接交易，不直接改核心规则。它负责基于反馈生成低风险自动更新或高风险改进建议。

可自动进化：

```text
健康度评分
状态标签
推荐优先级
报告模板偏好
Agent 快捷操作排序
缓存策略
低风险说明文案
研究结论索引
```

需要确认的进化：

```text
调整因子权重
调整策略状态
调整风控阈值
切换数据源优先级
修改回测默认参数
更新 Agent 工作流
```

禁止自动进化：

```text
自动交易
自动实盘调仓
修改核心风控底线
删除数据
删除实验
关闭风险预警
把策略自动推入实盘
```

### 4.7.2 Evolution Event

示例结构：

```json
{
  "evolution_id": "EVO_20260610_001",
  "target_type": "factor",
  "target_id": "momentum_20d",
  "previous_state": "validated",
  "new_state": "decaying",
  "trigger": "rank_ic_decline_6_weeks",
  "evidence": [
    "Rank IC dropped from 0.061 to 0.012",
    "Long-short return negative for 4 weeks"
  ],
  "action": "reduce_priority_and_schedule_retest",
  "requires_confirmation": false,
  "created_at": "2026-06-10"
}
```

---

## 5. 控制闭环详细设计

## 5.1 数据控制闭环

```text
数据采集
→ 数据质量检测
→ 异常识别
→ 数据可用性判断
→ 数据修复建议
→ 用户/系统确认
→ 更新数据质量规则
```

控制目标：

```text
完整性
一致性
时效性
准确性
可用性
异常隔离能力
```

关键指标：

```text
missing_rate
anomaly_rate
adjustment_consistency_score
suspension_detection_score
limit_up_down_detection_score
available_date_accuracy
ingestion_success_rate
```

## 5.2 因子控制闭环

```text
因子计算
→ IC / Rank IC 监控
→ 分组收益监控
→ 稳定性判断
→ 因子健康度更新
→ 因子权重调整建议
→ 后续表现反馈
```

因子生命周期：

```text
Draft → Testing → Validated → In Strategy Pool → Monitoring → Decaying → Retired
```

健康度分级：

```text
A：稳定有效，可进入策略池
B：局部有效，需要市场状态过滤
C：弱有效，可作为辅助因子
D：不稳定，仅保留观察
E：无效或疑似数据问题，淘汰
```

## 5.3 策略控制闭环

```text
策略运行
→ 回测/模拟结果
→ 样本外表现监控
→ 交易成本监控
→ 策略健康度更新
→ 暂停/重测/升级建议
→ 策略池状态更新
```

策略生命周期：

```text
Idea → Hypothesis → Factor Test → Strategy Backtest → Observation Pool → Simulation Pool → Active Strategy → Degraded → Paused → Retired
```

策略升级条件示例：

```text
样本外表现稳定
参数敏感性低
交易成本后有效
最大回撤低于阈值
通过 Backtest Auditor 审查
```

策略降级条件示例：

```text
IC 连续 4 周为负
近期回撤超过历史 90% 分位
交易成本上升超过 2 倍
样本外收益显著低于样本内
风险预算持续超限
```

## 5.4 组合风险控制闭环

```text
持仓状态
→ 风险暴露计算
→ 风险阈值对比
→ 控制动作建议
→ 用户确认
→ 调仓/暂停/降仓
→ 风险结果反馈
```

风险状态：

```text
Green：正常
Yellow：观察
Orange：预警
Red：强控制
Black：熔断/停止新开仓
```

控制动作示例：

```text
Green → 正常运行
Yellow → 提醒观察
Orange → 建议降仓/减少暴露
Red → 暂停新开仓/降低策略权重
Black → 策略熔断/停止执行
```

## 5.5 Agent 质量控制闭环

```text
Agent 输出
→ 用户采纳/拒绝
→ 后续结果验证
→ 输出质量评分
→ 模型路由调整
→ Prompt/模板优化
→ 成本与效果反馈
```

核心指标：

```text
answer_acceptance_rate
report_edit_rate
tool_call_success_rate
hallucination_flag_rate
cost_per_task
latency_ms
strong_model_usage_ratio
cache_hit_rate
```

---

## 6. Agent 系统设计

## 6.1 Agent 总体定位

Agent 是系统的研究协作层、审查层、解释层和控制建议层。Agent 不是自动交易者，不直接承诺收益，不直接进行实盘买卖。

右侧用户看到一个统一的“AI 研究助手”，但系统内部按任务路由到多个专业 Agent。

## 6.2 Agent 角色

```text
Research Orchestrator      总控研究 Agent
Data QA Agent              数据质检 Agent
Factor Research Agent      因子研究 Agent
Backtest Auditor Agent     回测审查 Agent
Portfolio Agent            组合管理 Agent
Risk Controller Agent      风控 Agent
Report Agent               报告 Agent
System Config Agent        系统配置 Agent
```

## 6.3 Research Orchestrator

职责：

```text
理解用户意图
读取当前页面上下文
拆解研究任务
选择专业 Agent
调用工具
管理任务进度
汇总输出
请求用户确认
记录审计日志
```

## 6.4 Agent 权限边界

Agent 默认只读。

```text
Level 0：只读
Level 1：生成建议
Level 2：创建任务，需要确认
Level 3：修改配置，强确认
Level 4：高风险动作，第一阶段禁止
```

所有 Agent 调用必须经过 Agent Gateway。

## 6.5 Agent Gateway

```text
Agent Gateway
├── Intent Classifier
├── Context Builder
├── Permission Checker
├── Budget Checker
├── Cache Layer
├── Context Compressor
├── Model Router
├── Tool Executor
├── Result Validator
├── Usage Logger
└── Audit Logger
```

任何模块不得绕过 Agent Gateway 直接调用大模型。

## 6.6 Agent 工具调用

### 数据工具

```text
get_dataset_summary(dataset_id)
get_data_quality_report(dataset_id)
get_missing_values(dataset_id)
get_anomaly_report(dataset_id)
get_ingestion_logs(dataset_id)
```

### 因子工具

```text
get_factor_definition(factor_id)
run_factor_test(config)
get_factor_metrics(experiment_id)
get_factor_correlation(factor_ids)
get_factor_group_returns(factor_id)
```

### 回测工具

```text
run_backtest(strategy_config)
get_backtest_summary(experiment_id)
get_drawdown_series(experiment_id)
get_trade_records(experiment_id)
get_parameter_sensitivity(experiment_id)
```

### 组合工具

```text
get_portfolio_snapshot(portfolio_id)
get_portfolio_exposure(portfolio_id)
get_rebalance_plan(portfolio_id)
simulate_rebalance(portfolio_id, target_weights)
get_performance_attribution(portfolio_id)
```

### 风控工具

```text
get_risk_dashboard(portfolio_id)
get_risk_alerts(portfolio_id)
run_stress_test(portfolio_id, scenario)
get_var_report(portfolio_id)
get_control_action_suggestions(portfolio_id)
```

### 报告工具

```text
generate_report_outline(report_type, object_id)
generate_report_section(report_id, section_id)
export_report(report_id, format)
get_report_status(report_id)
```

### 系统工具

```text
get_user_quota(user_id)
estimate_ai_cost(task)
log_ai_usage(event)
check_permission(user_id, action)
```

## 6.7 Agent 前端状态

右侧 Agent 面板必须显示：

```text
当前页面上下文
当前任务
任务进度
预计 AI 点数
实际消耗点数
当前模式
模型等级
调用工具列表
确认按钮
停止按钮
失败原因
```

Agent 状态：

```text
Idle
Planning
Fetching
Running Tool
Generating
Waiting Confirmation
Completed
Failed
Limited
```

---

## 7. 多模型与 AI 成本治理

## 7.1 多模型接入原则

平台必须支持多模型，但不应把复杂模型名称直接暴露给普通用户。

前端暴露任务模式：

```text
快速模式
标准分析
深度研究
审查模式
```

后端映射模型层级：

```text
L0：不用模型，模板/规则
L1：低成本模型，轻量解释
L2：标准研究模型，主力分析
L3：高级推理模型，复杂审查和报告
```

## 7.2 模型路由

```text
用户请求
→ Intent Classifier
→ Cost Estimator
→ Budget Checker
→ Cache Checker
→ Context Compressor
→ Model Router
→ LLM Provider Adapter
→ Usage Logger
```

## 7.3 AI 点数系统

建议以 AI Points 控制成本。

示例：

```text
普通问答：1 点
指标解释：1 点
因子摘要：3 点
回测解释：5 点
风险归因：8 点
完整报告：20 点
过拟合审查：30 点
多实验对比：50 点
```

高成本任务需要用户确认：

```text
完整回测审查预计消耗 45 点，是否继续？
[继续] [改用快速审查]
```

## 7.4 成本红线

以 Pro 版年费 9,999 元计算，月收入约 833 元。

AI 成本目标：

```text
目标：40–125 元/月/用户
上限：150 元/月/用户
超过：限流、降级、缓存优先或引导购买点数包
```

## 7.5 ai_usage 表

```sql
ai_usage
- id
- user_id
- workspace_id
- task_id
- feature
- model_tier
- input_tokens
- output_tokens
- cached_tokens
- estimated_cost
- points_charged
- latency_ms
- status
- created_at
```

## 7.6 ai_budget 表

```sql
ai_budget
- id
- user_id
- workspace_id
- plan
- monthly_points
- used_points
- remaining_points
- hard_limit_enabled
- reset_at
```

---

## 8. 产品级 Web 端设计

## 8.1 三栏架构

Web 端采用固定三栏：

```text
左栏：系统导航
中栏：研究工作区
右栏：AI Agent 控制塔
```

### 左栏

导航项：

```text
总览
数据中心
因子研究
策略回测
组合管理
风险控制
研究实验
AI 研究助手
系统设置
```

### 中栏

根据页面展示主工作区。

### 右栏

右侧 Agent 常驻，提供：

```text
当前上下文
当前任务
AI 对话
快捷操作
建议下一步
成本/额度显示
监控列表
报告预览
```

## 8.2 页面规格

### 总览页

目标：展示组合、市场、风险、研究动态的统一控制台。

核心组件：

```text
研究流程条
KPI 卡片
组合净值与基准图
市场状态识别
策略健康度监控
因子研究看板
风险预警
今日研究结论
当前持仓表
右侧 AI 总览助手
```

### 数据中心

目标：管理数据源、数据集、数据质量和数据流水线。

核心组件：

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
右侧 Data QA Agent
```

### 因子研究

目标：验证因子有效性与稳定性。

核心组件：

```text
股票池/时间区间/调仓频率过滤器
IC / Rank IC / ICIR / 多空收益 KPI
因子库
IC 时序图
多空累计收益图
分组收益表
因子相关性热力图
风格暴露
研究结论
右侧 Factor Agent
```

### 策略回测

目标：配置、运行和审查策略回测。

核心组件：

```text
策略配置栏
年化收益/夏普/最大回撤/胜率 KPI
累计净值曲线
回撤曲线
月度收益热力图
参数敏感性
交易成本分析
样本内 vs 样本外
策略健康诊断
最近交易记录
右侧 Backtest Auditor Agent
```

### 组合管理

目标：管理持仓、目标权重、调仓和组合归因。

核心组件：

```text
组合净值
现金占比
持仓数量
组合波动率
行业分布
风格暴露
市值分布
风险暴露
当前持仓表
调仓计划
目标组合 vs 当前组合
订单篮子
备选观察池
右侧 Portfolio Agent
```

### 风险控制

目标：监控组合和策略风险，并生成控制动作。

核心组件：

```text
当前回撤
VaR
行业集中度
单票集中度
风险预算使用率
预警数量
回撤曲线
滚动波动率
因子/行业敞口
压力测试
风险预警列表
风险规则/熔断规则
情景分析
风控操作建议
右侧 Risk Controller Agent
```

### 研究实验

目标：管理假设、实验、参数、结果和研究结论。

核心组件：

```text
假设池
运行中实验
已完成实验
已归档实验
实验总数
成功率
平均运行时长
实验列表
实验流程 Pipeline
实验对比
实验历史 Timeline
结论与备注
右侧 Experiment Agent
```

### AI 研究助手

目标：集中管理复杂 Agent 任务和多步骤研究工作流。

核心组件：

```text
当前任务
上下文
工具调用记录
生成中的报告
多步骤任务流
研究对话
阶段性结论
报告预览
可执行建议
右侧紧凑助手栏
```

### 系统设置

目标：管理工作区、数据源、回测参数、风控规则、模型与 Agent、通知、安全和集成。

核心组件：

```text
账户与工作区
数据源配置
回测默认参数
风险规则
AI 模型与 Agent 配置
通知与告警
权限与安全
界面偏好
集成/API
备份与快照
右侧配置助手
```

---

## 9. 技术架构

## 9.1 推荐技术栈

### 前端

```text
Next.js
React
TypeScript
Tailwind CSS
shadcn/ui
TanStack Table
ECharts / Recharts
Zustand
TanStack Query
```

### 后端

```text
FastAPI
Pydantic
SQLAlchemy
Alembic
PostgreSQL
Redis
Celery / RQ / Dramatiq
```

### 量化引擎

```text
Python
Polars
pandas
NumPy
DuckDB
Parquet
```

### Agent 系统

```text
Agent Gateway
Tool Registry
Model Router
AI Usage Logger
Context Compressor
Report Generator
```

### 部署

```text
Docker Compose 起步
PostgreSQL
Redis
Object Storage
Worker Queue
后续可迁移云服务/Kubernetes
```

## 9.2 Monorepo 结构

```text
quant-research-platform/
├── apps/
│   ├── web/
│   │   ├── app/
│   │   ├── components/
│   │   ├── features/
│   │   ├── hooks/
│   │   ├── lib/
│   │   ├── stores/
│   │   └── types/
│   │
│   └── api/
│       ├── app/
│       │   ├── api/
│       │   ├── core/
│       │   ├── models/
│       │   ├── schemas/
│       │   ├── services/
│       │   ├── workers/
│       │   └── main.py
│
├── packages/
│   ├── quant-engine/
│   │   ├── data/
│   │   ├── factors/
│   │   ├── backtest/
│   │   ├── portfolio/
│   │   ├── risk/
│   │   └── reports/
│   │
│   ├── agent-engine/
│   │   ├── agents/
│   │   ├── gateway/
│   │   ├── tools/
│   │   ├── prompts/
│   │   ├── memory/
│   │   └── usage/
│   │
│   └── shared/
│       ├── types/
│       ├── constants/
│       └── schemas/
│
├── data/
│   ├── raw/
│   ├── processed/
│   ├── factors/
│   ├── backtests/
│   └── reports/
│
├── docs/
│   ├── SPEC.md
│   ├── WEB_DESIGN.md
│   ├── ROADMAP.md
│   ├── CLAUDE.md
│   └── API.md
│
├── docker-compose.yml
├── README.md
└── CLAUDE.md
```

---

## 10. 数据存储设计

## 10.1 PostgreSQL

存储事务型和元数据对象：

```text
用户
工作区
权限
数据源配置
实验记录
因子定义
策略定义
组合元数据
风险规则
Agent 任务
AI 用量
报告元数据
审计日志
```

## 10.2 DuckDB + Parquet

存储分析型大数据：

```text
日频行情
复权因子
财务指标
因子值
信号矩阵
回测净值
交易记录
风险指标时间序列
组合持仓快照
```

## 10.3 Redis

用于：

```text
任务队列
短期缓存
会话状态
限流
AI 上下文临时缓存
任务进度
```

---

## 11. 核心数据库表

### 11.1 ontology_object

```sql
ontology_object
- id
- object_type
- object_key
- name
- description
- workspace_id
- metadata_json
- created_at
- updated_at
```

### 11.2 hypothesis

```sql
hypothesis
- id
- workspace_id
- name
- description
- market_assumption
- expected_mechanism
- failure_condition
- status
- created_by
- created_at
- updated_at
```

### 11.3 factor_definition

```sql
factor_definition
- id
- workspace_id
- hypothesis_id
- name
- formula
- direction
- universe
- frequency
- neutralization_method
- version
- status
- created_at
```

### 11.4 experiment

```sql
experiment
- id
- workspace_id
- hypothesis_id
- factor_id
- strategy_id
- experiment_type
- data_version
- config_hash
- code_version
- status
- started_at
- completed_at
- created_by
```

### 11.5 decision

```sql
decision
- id
- workspace_id
- decision_type
- source_type
- source_id
- target_type
- target_id
- data_inputs_json
- logic_used_json
- recommendation
- confidence
- risk_level
- requires_confirmation
- allowed_actions_json
- forbidden_actions_json
- status
- created_at
- resolved_at
```

### 11.6 action_log

```sql
action_log
- id
- workspace_id
- decision_id
- action_type
- target_type
- target_id
- actor_type
- actor_id
- input_json
- output_json
- status
- created_at
```

### 11.7 feedback

```sql
feedback
- id
- workspace_id
- source_action_id
- source_decision_id
- target_type
- target_id
- feedback_type
- metric_before_json
- metric_after_json
- user_response
- notes
- created_at
```

### 11.8 evolution_event

```sql
evolution_event
- id
- workspace_id
- target_type
- target_id
- previous_state
- new_state
- trigger
- evidence_json
- action
- requires_confirmation
- status
- created_at
```

### 11.9 agent_task

```sql
agent_task
- id
- workspace_id
- user_id
- page_context
- task_type
- target_type
- target_id
- status
- estimated_points
- actual_points
- model_tier
- created_at
- completed_at
```

### 11.10 agent_tool_call

```sql
agent_tool_call
- id
- task_id
- tool_name
- input_json
- output_json
- status
- latency_ms
- created_at
```

---

## 12. API 模块边界

```text
/auth              用户、登录、权限
/workspaces        工作区
/data              数据源、数据集、数据质量
/factors           因子定义、因子测试
/strategies        策略定义、策略状态
/backtests         回测任务、回测结果
/experiments       实验管理
/portfolios        组合、持仓、调仓
/risk              风险指标、预警、压力测试
/reports           报告生成与导出
/agents            Agent 任务、对话、工具调用
/decisions         决策对象
/actions           行动日志
/feedback          反馈记录
/evolution         进化事件
/settings          系统设置
/usage             AI 点数、套餐、限额
```

---

## 13. MVP 范围

## 13.1 P0：可收费内测版

必须交付：

```text
产品级三栏 Web 框架
登录与工作区
总览页
数据中心初版
因子研究初版
策略回测初版
右侧 Agent 面板
Agent Gateway 初版
AI 点数记录
基础报告生成
实验记录
基础风险提示
Docker Compose 部署
```

P0 数据范围：

```text
A 股日频数据
指数数据
基础行业分类
基础财务指标
5–10 年历史数据
```

P0 因子：

```text
动量因子
波动率因子
成交量因子
低估值因子
盈利质量因子
```

P0 策略：

```text
Top N 因子组合
放量突破策略
简单多因子增强策略
```

P0 Agent 能力：

```text
解释指标
总结因子结果
总结回测结果
生成研究报告
基础过拟合提示
解释风险预警
记录 AI 点数
```

## 13.2 P0 不做

```text
实盘交易
自动下单
复杂团队协作
机构级权限
私有部署
多市场全覆盖
高频数据
复杂机器学习
完整低代码策略编辑器
```

## 13.3 P1：Pro 标准版

```text
组合管理
风险控制
研究实验完整化
策略健康度
因子健康度
Agent 多角色路由
Backtest Auditor
Risk Controller Agent
AI 成本仪表盘
套餐/额度系统
报告导出
```

## 13.4 P2：Team / Institution

```text
多人协作
团队知识库
权限审计
私有数据源
企业模型配置
API 集成
私有部署
高级风控
策略生命周期治理
```

---

## 14. 验收标准

## 14.1 产品验收

P0 版本必须满足：

```text
用户可以注册/登录
用户可以进入三栏 Web 工作台
用户可以查看真实或半真实市场数据
用户可以运行至少 3 个因子测试
用户可以运行至少 2 个策略回测
用户可以保存实验记录
用户可以生成研究报告
右侧 Agent 能识别当前页面上下文
Agent 能解释结果且显示 AI 点数消耗
系统能记录任务状态和错误日志
系统有基础风险免责声明
```

## 14.2 技术验收

```text
前后端类型定义清晰
关键 API 有测试
任务队列可运行
回测任务异步执行
AI 调用统一走 Agent Gateway
AI 用量可记录
关键对象有审计日志
Docker Compose 可本地启动
```

## 14.3 研究可信度验收

```text
每次回测记录数据版本
每次回测记录参数配置
每次回测记录策略版本
每次实验可复现
回测报告标明交易成本
Agent 不得输出收益承诺
高风险动作必须确认
```

---

## 15. 风险与边界

### 15.1 金融合规风险

系统不得承诺收益，不得以确定性语言推荐买卖，不得包装为自动赚钱产品。

所有 AI 输出必须包含：

```text
仅供研究参考，不构成投资建议。
```

### 15.2 数据风险

低成本数据源可能存在延迟、缺失、复权错误和授权问题。系统必须标明数据来源、数据质量和数据可用边界。

### 15.3 AI 幻觉风险

Agent 必须基于结构化数据和工具结果生成结论。不得让模型自行编造数值。

### 15.4 成本风险

AI 调用、回测任务和数据授权必须限额。所有高成本任务必须走预算检查。

### 15.5 过度自动化风险

系统可以自动生成建议，但第一阶段不得自动实盘执行。

---

## 16. 最终系统定义

本平台最终应被定义为：

```text
一个基于 Data → Logic → Decision → Action → Feedback → Control → Evolution 的 AI-native 个人量化研究控制系统。
```

它的核心不是预测市场，而是帮助用户在不确定市场中形成可验证、可审查、可控制、可复盘的研究与决策过程。

最终目标：

```text
让模糊投资想法变成可验证假设。
让复杂数据变成结构化证据。
让漂亮回测经过严格审查。
让风险暴露被持续控制。
让 Agent 输出可解释、可追踪、可审计。
让系统在反馈中受控进化，而不是无约束自动决策。
```

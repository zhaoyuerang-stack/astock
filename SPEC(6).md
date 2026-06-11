# SPEC.md

# 个人优先 Alpha Factory OS 系统规格文档

版本：v0.4  
状态：Draft / Product-grade MVP Spec  
产品名称：暂定 Alpha Factory OS / 我的 Alpha 工作台  
产品定位：个人优先的 AI-native Alpha 研究、验证、审查、沉淀与复盘系统  
底层架构：DLDAF-C/E Architecture  
核心链路：Data → Logic → Decision → Action → Feedback → Control → Evolution  
核心体验：左侧轻导航 + 中央个人 Alpha 工作台 + 右侧常驻 AI 研究副驾驶  
目标阶段：可收费个人内测版，支持 30–100 个 Founding Pro 用户使用  
非目标：自动荐股、自动实盘交易、收益承诺、黑箱 AI 投顾、机构级协作后台

---

## 0. 文档目的

本文档用于定义“个人优先 Alpha Factory OS”的产品规格、系统边界、核心架构、前端信息架构、个人用户工作流、Agent 体系、Skill/API 分层、数据治理、研究实验、回测审查、Alpha 池、风险提醒、报告系统、AI 成本治理、受控进化机制、技术架构、数据模型和 MVP 交付范围。

本产品底层是 Alpha Factory OS，但表层体验不能做成机构后台。第一阶段的核心用户是个人研究者，而不是大型团队。产品应该让个人用户感觉：

```text
我一个人也拥有了一个小型量化研究团队。
```

因此，本系统的设计原则是：

```text
底层：机构级 Alpha Factory 架构
表层：个人化 Alpha 工作台体验
Agent：个人研究副驾驶
流程：从想法到验证，再到 Alpha 池
团队能力：后置
机构治理：隐藏在底层，不压迫个人用户
```

本产品不是普通行情软件、普通回测工具、AI 荐股助手或自动交易机器人。它应被设计为一个帮助个人把投资想法转化为可验证研究、把回测结果转化为可审查证据、把策略沉淀为可管理 Alpha 池的个人研究操作系统。

一句话：

> Alpha Factory OS 的 P0 版本是给个人使用的 AI Alpha 工作台，而不是给机构使用的协作管理后台。

---

## 1. 产品定位

### 1.1 一句话定义

本产品是一个个人优先的 AI-native 量化研究工作台，用于帮助高阶个人投资者、职业交易者、量化研究爱好者和非开发型系统化投资者完成投资想法整理、假设验证、因子研究、策略回测、回测审查、Alpha 池管理、风险提醒、报告生成和研究复盘。

### 1.2 产品本质

本产品不是“给股票答案”的系统，而是“帮助个人生产证据”的系统。

```text
普通工具：用户输入策略，系统输出回测曲线。
本产品：用户输入想法，系统帮助整理假设、验证数据、运行实验、审查回测、沉淀结论、提醒风险、建议下一步。
```

### 1.3 用户心智

用户不应该感觉自己在使用复杂机构后台，而应该感觉自己正在使用一个：

```text
个人 AI 投研工作台
个人 Alpha 研究副驾驶
个人策略审查员
个人风险提醒员
个人研究档案系统
```

产品对外可以使用“个人可用的 Alpha Factory OS”作为定位，但界面内应尽量使用更轻的个人化语言。

### 1.4 产品不是

第一阶段明确不是：

```text
不是自动荐股软件
不是自动实盘交易系统
不是承诺收益的软件
不是机构级 OMS/EMS
不是团队审批流系统
不是复杂量化代码框架
不是纯聊天式 AI 投顾
不是面向高频交易的系统
不是多资产全市场机构终端
```

### 1.5 产品是

第一阶段应被设计为：

```text
个人研究想法整理器
个人假设验证系统
个人因子研究系统
个人策略回测与审查系统
个人 Alpha 池
个人风险提醒系统
个人研究报告中心
个人 AI 研究副驾驶
个人研究记忆与复盘系统
```

---

## 2. 目标用户与优先级

### 2.1 Primary User：个人用户

P0 只服务个人用户。

目标用户包括：

```text
高阶个人投资者
职业交易者
量化研究爱好者
非开发型系统化投资者
AI-native 投研工具使用者
有明确投资想法但缺少工程能力的用户
希望从主观交易转向系统化研究的用户
```

他们的核心问题是：

```text
我有想法，但不知道如何验证。
我会看回测，但不知道回测是否可信。
我不确定某个策略还能不能继续用。
我缺少研究流程和复盘纪律。
我没有研究员、风控员、报告员和工程师。
我需要 AI 帮我把研究工作组织起来。
```

### 2.2 Secondary User：小团队

小团队是 P1/P2 目标，不进入 P0。

后续可支持：

```text
2–5 人投研小组
投资工作室
小型私募研究团队
家办投研团队
```

但 P0 不做：

```text
多人协作
角色权限
审批流
团队任务分配
研究员绩效
团队审计
机构私有部署
```

### 2.3 产品阶段原则

```text
P0：个人可用，完成从想法到 Alpha 池的闭环。
P1：个人增强，加入更强风控、模拟组合、成本治理和受控进化。
P2：小团队协作，加入权限、共享、评论、审批和团队报告。
P3：机构增强，加入私有部署、合规审计、企业模型和数据源治理。
```

---

## 3. 顶层架构原则

### 3.1 表层个人化，底层工厂化

本产品的最重要原则：

```text
前端体验个人化
系统内核工厂化
```

前端使用个人用户能理解的词：

```text
我的工作台
研究想法
因子研究
策略回测
Alpha 池
风险提醒
研究报告
AI 助手
设置
```

底层仍然保留严格对象：

```text
Hypothesis
Factor
Strategy
Experiment
BacktestAudit
DecisionObject
ActionLog
FeedbackEvent
EvolutionEvent
```

### 3.2 DLDAF-C/E 架构

系统内核采用：

```text
Data → Logic → Decision → Action → Feedback → Control → Evolution
```

含义：

```text
Data：系统观察到什么。
Logic：系统如何解释和计算。
Decision：系统形成什么受约束判断。
Action：系统允许执行什么动作。
Feedback：动作之后结果如何。
Control：如何根据偏差进行控制。
Evolution：如何在边界内更新状态、权重、模板和生命周期。
```

### 3.3 三条硬规则

```text
No Action Without Data
没有数据，不允许行动。

No Decision Without Logic
没有逻辑，不允许决策。

No Execution Without Policy
没有权限与策略约束，不允许执行。
```

### 3.4 Agent 的边界

Agent 不直接给投资承诺，不直接下单，不绕过工具，不直接查数据库。

正确链路：

```text
User Request
→ Agent Orchestrator
→ Skill
→ Tool/API
→ Domain Service
→ Data / Quant Engine
→ Structured Result
→ Decision Engine
→ Agent Explanation
→ User Confirmation if needed
→ Action / Feedback
```

---

## 4. 前端产品定位

### 4.1 前端一句话

前端是“我的 Alpha 工作台”，不是“机构 Alpha 工厂后台”。

用户打开产品后应立即知道：

```text
我今天该看什么？
我上次研究做到哪里？
哪个策略出了问题？
哪个想法值得继续？
哪个回测不能信？
下一步该做什么？
```

### 4.2 P0 信息架构

P0 左侧导航建议：

```text
1. 我的工作台
2. 研究想法
3. 因子研究
4. 策略回测
5. Alpha 池
6. 风险提醒
7. 研究报告
8. 设置
```

右侧常驻：

```text
AI 研究助手
```

P0 不单独做复杂 Agent Center。AI 助手作为右侧栏贯穿所有页面。

### 4.3 前端术语映射

| 底层术语 | 个人版前端术语 |
|---|---|
| Alpha Factory Cockpit | 我的工作台 |
| Hypothesis Pipeline | 研究想法 |
| Data Trust Center | 数据状态 / 数据可信度 |
| Factor Lab | 因子研究 |
| Strategy Lab | 策略回测 |
| Backtest Audit | 回测审查 |
| Alpha Lifecycle | Alpha 池 |
| Risk Control Tower | 风险提醒 |
| Agent Command Center | AI 研究助手 |
| Governance | 设置 / 安全与额度 |

### 4.4 布局原则

采用三栏结构：

```text
左侧：导航与对象入口
中间：当前研究工作区
右侧：AI 研究助手
```

左侧稳定，中央处理主要任务，右侧提供上下文感知辅助。

---

## 5. P0 页面规格

### 5.1 我的工作台

目的：给个人用户一个每日研究入口。

核心模块：

```text
今日需要关注的 3 件事
进行中的研究
我的 Alpha 池摘要
最近回测与审查
风险提醒
最近研究报告
AI 推荐下一步
AI 点数与数据状态
```

关键问题：

```text
今天我该做什么？
哪个策略需要复查？
哪个想法可以继续推进？
哪个风险需要处理？
```

默认不要展示过多机构化指标。优先展示行动建议和状态摘要。

### 5.2 研究想法

目的：让个人用户用自然语言记录想法，并由 AI 转化为可验证研究问题。

功能：

```text
一句话输入投资想法
AI 整理为研究问题
AI 生成可验证假设
AI 建议数据需求
AI 建议因子定义
AI 建议第一个实验
保存到研究想法列表
```

对象映射：

```text
前端：研究想法
底层：Idea + Hypothesis
```

示例：

```text
用户输入：我觉得放量突破后的股票后面几天还会涨。
系统整理：验证短期成交量突破是否具有动量延续效应。
建议实验：构建 volume_breakout_20d 因子，并测试未来 5/10/20 日收益。
```

### 5.3 因子研究

目的：让用户验证一个因子是否值得继续。

默认简洁层：

```text
这个因子是否有效？
是否稳定？
是否值得继续？
主要风险是什么？
下一步该做什么？
```

专业展开层：

```text
IC
Rank IC
ICIR
分组收益
多空收益
换手率
行业中性结果
相关性
样本外结果
```

对象映射：

```text
前端：因子研究
底层：Factor + FactorExperiment + FactorHealth
```

### 5.4 策略回测

目的：让用户构建策略、运行回测、理解结果，并进入审查流程。

功能：

```text
策略配置
回测运行
绩效摘要
净值曲线
回撤曲线
交易记录摘要
样本内/样本外对比
交易成本影响
一键发起回测审查
```

默认必须突出：

```text
这个回测是否可信？
它是否可能过拟合？
是否考虑交易成本？
是否满足 A 股交易约束？
是否值得进入 Alpha 池？
```

对象映射：

```text
前端：策略回测
底层：Strategy + BacktestExperiment + BacktestAudit
```

### 5.5 Alpha 池

目的：管理个人策略和 Alpha 想法的生命周期。

前端状态：

```text
想法
验证中
观察中
模拟中
已暂停
已淘汰
```

底层状态：

```text
Idea
Testing
Backtested
Audited
Observation
Simulation
Degraded
Paused
Retired
```

卡片字段：

```text
名称
状态
可信度
健康度
风险等级
最近审查
下一步建议
```

Alpha 池不是持仓池，也不是荐股池。它是用户的研究资产库。

### 5.6 风险提醒

目的：提醒个人用户研究、策略、组合和系统层面的关键风险。

P0 风险范围：

```text
策略回撤风险
因子衰减风险
数据异常风险
回测可信度风险
AI 成本使用风险
研究停滞风险
```

P0 可以弱化复杂组合风险和实盘风险。

### 5.7 研究报告

目的：把研究过程沉淀为可复盘档案。

报告类型：

```text
研究想法报告
因子研究报告
回测审查报告
Alpha 池周报
风险复盘报告
AI 使用与成本报告
```

P0 必做：

```text
因子研究报告
回测审查报告
个人 Alpha 周报
```

### 5.8 设置

P0 设置包括：

```text
账户设置
数据源设置
AI 点数与额度
默认研究偏好
风险偏好
免责声明确认
导出与备份
```

不做复杂团队权限。

---

## 6. 右侧 AI 研究助手

### 6.1 定位

右侧 Agent 是个人研究副驾驶，不是普通聊天框。

它的职责：

```text
理解当前页面与当前对象
解释结果
提醒风险
建议下一步
调用 Skill
生成报告
估算 AI 点数
记录反馈
```

### 6.2 固定结构

右侧栏建议包含：

```text
当前对象
当前状态
可信度/健康度
主要风险
推荐下一步
快捷操作
AI 点数消耗
对话输入
```

在策略回测页示例：

```text
当前对象：放量突破策略
当前状态：回测完成，未审查
可信度：待评估
主要风险：交易成本未压力测试
建议下一步：运行回测审查
预计消耗：28 AI 点数
```

### 6.3 Agent 能力边界

Agent 可以：

```text
解释指标
整理研究想法
生成实验计划
总结因子表现
审查回测结果
生成报告草稿
提出下一步建议
创建低/中风险任务，需按规则确认
```

Agent 不可以：

```text
承诺收益
直接荐股
自动实盘下单
绕过风控
直接修改核心策略
直接访问数据库
删除实验和原始数据
```

---

## 7. Skill 与 API 分层

### 7.1 是否需要 Skill

需要，但 P0 只做轻量 Skill。

```text
需要 Skill 思维
不需要复杂 Skill 平台
```

Skill 的 P0 定义：

```text
固定任务模板 + 工具调用流程 + 输出 Schema + 成本/权限约束
```

### 7.2 分层关系

```text
Agent = 调度者
Skill = 任务流程模板
Tool/API = 稳定能力接口
Domain Service = 领域逻辑
Data/Quant Engine = 数据与计算执行
```

标准链路：

```text
Agent Orchestrator
→ Skill Layer
→ Tool Registry
→ API Layer
→ Domain Service
→ Data / Quant Engine
```

### 7.3 P0 内置 Skill

P0 只做 5 个固定 Skill：

```text
IdeaToHypothesisSkill
FactorResearchSkill
BacktestAuditSkill
RiskReviewSkill
ReportGenerationSkill
```

可选补充：

```text
DataQASkill
```

### 7.4 API 原则

API 提供确定性能力。

```text
get_factor_metrics()
run_factor_test()
run_backtest()
get_backtest_summary()
get_parameter_sensitivity()
get_risk_alerts()
generate_report()
estimate_ai_points()
log_ai_usage()
```

硬规则：

```text
Agent 不直接访问数据库。
Skill 不直接访问原始数据。
所有数据获取必须通过 Tool/API。
所有高风险 Action 必须经过 Decision Engine。
所有 Tool Call 必须记录审计日志。
所有 AI 调用必须经过 AI Gateway。
```

---

## 8. 数据与研究对象模型

### 8.1 核心对象

```text
User
Workspace
Idea
Hypothesis
Dataset
DataQualityReport
Factor
FactorExperiment
Strategy
BacktestExperiment
BacktestAudit
AlphaItem
RiskAlert
Report
AgentTask
DecisionObject
ActionLog
FeedbackEvent
EvolutionEvent
AIUsage
```

### 8.2 个人 Alpha 工作流对象链

```text
Idea
→ Hypothesis
→ Factor
→ FactorExperiment
→ Strategy
→ BacktestExperiment
→ BacktestAudit
→ AlphaItem
→ RiskAlert / Report / Feedback
```

### 8.3 Decision Object

重要判断必须显式记录为 Decision Object。

字段建议：

```text
decision_id
user_id
workspace_id
decision_type
target_type
target_id
data_inputs
logic_used
recommendation
confidence
risk_level
requires_confirmation
allowed_actions
forbidden_actions
status
created_at
```

### 8.4 Feedback Event

记录用户是否采纳、后续效果、报告是否修改、策略是否继续等。

字段建议：

```text
feedback_id
target_type
target_id
feedback_type
source
value
notes
created_at
```

### 8.5 Evolution Event

P0 只做低风险演化记录，不做自动策略修改。

字段建议：

```text
evolution_id
target_type
target_id
previous_state
new_state
trigger
evidence
action
requires_confirmation
created_at
```

---

## 9. 控制论闭环与受控进化

### 9.1 控制闭环

系统应具备 5 类控制闭环：

```text
Data Quality Loop
Factor Health Loop
Strategy Health Loop
Risk Alert Loop
Agent Cost / Quality Loop
```

### 9.2 P0 可自动更新

```text
因子健康度评分
策略健康度评分
风险提醒状态
报告模板偏好
AI 快捷建议排序
Alpha 池状态提示
```

### 9.3 P0 需要确认

```text
将策略移入观察中
将策略标记为暂停
重新运行高成本回测
生成完整报告
修改风险偏好
切换数据源优先级
```

### 9.4 P0 禁止自动执行

```text
自动实盘交易
自动买卖股票
自动修改核心风控底线
自动删除实验
自动覆盖原始数据
自动承诺收益
自动把策略推入实盘
```

---

## 10. AI 成本治理

### 10.1 统一 AI Gateway

所有 AI 调用必须经过 AI Gateway。

```text
Agent / Skill
→ AI Gateway
→ Intent Classifier
→ Budget Checker
→ Context Builder
→ Cache Layer
→ Model Router
→ LLM Provider
→ Usage Logger
```

### 10.2 多模型策略

P0 支持内部模型分层，不对普通用户暴露复杂模型名。

前端显示：

```text
快速模式
标准分析
深度研究
审查模式
```

内部映射：

```text
L0：不用模型，规则/模板
L1：低成本模型，简单解释
L2：标准研究模型，主力任务
L3：高级推理模型，回测审查/复杂报告
```

### 10.3 AI 点数

每个 Skill 必须有预计 AI 点数。

示例：

```text
指标解释：1 点
因子摘要：5 点
回测审查：20–40 点
完整报告：30–60 点
多实验对比：50+ 点
```

高成本任务必须提示用户确认。

---

## 11. 技术架构

### 11.1 推荐技术栈

Frontend：

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

Backend：

```text
FastAPI
Pydantic
SQLAlchemy
Alembic
PostgreSQL
Redis
Celery / RQ / Dramatiq
```

Quant Engine：

```text
Python
Polars
DuckDB
Parquet
NumPy / pandas where needed
```

Agent Engine：

```text
Agent Orchestrator
Skill Layer
Tool Registry
AI Gateway
Model Router
Usage Logger
```

Deployment：

```text
Docker Compose for MVP
PostgreSQL + Redis + Object Storage
```

### 11.2 推荐目录结构

```text
quant-alpha-workbench/
├── apps/
│   ├── web/
│   └── api/
├── packages/
│   ├── quant-engine/
│   ├── agent-engine/
│   │   ├── orchestrator/
│   │   ├── skills/
│   │   ├── tools/
│   │   ├── schemas/
│   │   └── gateway/
│   └── shared/
├── docs/
│   ├── SPEC.md
│   ├── ROADMAP.md
│   ├── WEB_DESIGN.md
│   └── CLAUDE.md
├── data/
├── docker-compose.yml
└── README.md
```

---

## 12. MVP 范围

### 12.1 P0 必须完成

```text
个人账号与工作区
我的工作台
研究想法输入与 AI 整理
因子研究基础流程
策略回测基础流程
回测审查 Skill
Alpha 池
风险提醒基础版
研究报告基础版
右侧 AI 研究助手
AI 点数记录
Tool/API 受控调用
基础 Decision Object
基础 Feedback Event
```

### 12.2 P0 不做

```text
多人协作
审批流
团队权限
实盘交易
自动下单
复杂组合优化
机构级私有部署
多资产全市场
高频交易
用户自定义 Skill
Skill Marketplace
复杂可视化编排器
```

### 12.3 P0 验收标准

用户能够完成以下闭环：

```text
1. 输入一个研究想法。
2. AI 将其整理为可验证研究问题。
3. 用户创建或选择一个因子。
4. 系统运行因子研究。
5. 用户基于因子创建一个简单策略。
6. 系统运行回测。
7. Agent 执行回测审查。
8. 系统给出可信度、风险、下一步建议。
9. 用户将其加入 Alpha 池或淘汰。
10. 系统生成研究报告并记录反馈。
```

这才算 P0 可用，而不是页面能打开。

---

## 13. 商业与套餐边界

### 13.1 P0 商业目标

```text
用户：30–100 个 Founding Pro
价格：¥1,999–¥4,999/年
目标：验证个人用户是否愿意为 AI Alpha 工作台付费
```

### 13.2 后续 Pro 定价假设

```text
Pro：¥9,999/年
Research Max：¥19,999–¥29,999/年
Team：P2 后考虑
```

### 13.3 成本红线

按 Pro 月收入约 ¥833 估算：

```text
AI 成本目标：¥40–125/月/用户
AI 成本上限：¥150/月/用户
超过则限流、降级或引导购买点数包
```

---

## 14. 关键产品原则

```text
1. 个人优先，团队后置。
2. 表层轻，底层深。
3. 先帮用户验证想法，不直接给买卖答案。
4. 先做研究闭环，不做实盘交易。
5. Agent 是研究副驾驶，不是投资主脑。
6. Skill 是任务模板，不是复杂插件平台。
7. API 是数据与计算的唯一可信入口。
8. 所有重要结论必须有证据、对象、版本和审计记录。
9. 所有高成本 AI 任务必须可计量、可确认、可限流。
10. 系统可以受控进化，但不能无约束自我修改。
```

---

## 15. 最终定义

本产品的最终定义：

> 一个个人优先的 AI Alpha 工作台。它以 Alpha Factory OS 为底层内核，让个人用户从一个模糊投资想法出发，经过假设整理、数据验证、因子研究、策略回测、回测审查、Alpha 池沉淀、风险提醒和研究复盘，逐步建立自己的可复现、可审查、可进化的个人 Alpha 资产库。

P0 的成功标准不是“功能很多”，而是：

```text
个人用户打开系统后，知道自己该研究什么；
做完研究后，知道结果能不能信；
策略进入 Alpha 池后，知道它是否还健康；
风险出现时，系统能提醒；
每一次研究，都能被记录、复盘和改进。
```

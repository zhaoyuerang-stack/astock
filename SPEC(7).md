# SPEC.md

# 个人策略信号与交易计划助手系统规格

版本：v0.4  
状态：Draft  
产品定位：个人优先的策略信号、股票候选、交易计划与价格提醒系统  
底层架构：Personal Alpha Factory OS  
核心链路：Data → Logic → Signal → Decision → Trade Plan → Alert → Action → Feedback → Control → Evolution  
核心界面：左侧导航栏 + 中央行动工作区 + 右侧常驻 AI 研究助手  
目标阶段：产品级 MVP，可支持早期付费内测用户使用  

---

## 0. 文档目的

本文档定义一个面向个人用户的 AI-native 量化投资辅助系统。系统的表层价值不再只是“研究工作台”或“回测工具”，而是帮助用户把已经定义或选择的策略转化为：

```text
股票候选
策略信号
买入触发条件
卖出/止盈/止损规则
价格提醒
风险提醒
交易计划复盘
```

系统底层仍保留 Alpha Factory OS 的研究、审查、治理和进化能力，但第一版产品必须优先服务个人用户的高频真实需求：

```text
今天哪些策略触发了？
哪些股票进入候选？
为什么是这些股票？
什么价格触发买入提醒？
什么价格触发止损/止盈提醒？
这个信号可信度高不高？
如果信号失效，系统能否提醒我？
```

本系统不是“AI 荐股神器”，不是自动投顾，也不是自动交易机器人。它的正确边界是：

```text
基于用户选择、创建或启用的策略规则，生成可解释、可审查、可提醒的交易计划。
```

也就是说，系统不主观承诺某只股票会涨，而是把策略规则、数据证据、风险边界和提醒条件结构化，让用户自己确认、跟踪和复盘。

---

## 1. 产品定位

### 1.1 一句话定义

本产品是一个面向个人投资者的 **策略信号与交易计划助手**，帮助用户把可验证策略转化为股票候选、买卖计划、风险边界和价格提醒。

### 1.2 产品主张

```text
用你的策略，生成可解释的股票候选、交易计划和到价提醒。
```

更完整的表述：

```text
把投资想法和策略规则，转化为可验证、可审查、可提醒、可复盘的个人交易计划。
```

### 1.3 表层体验与底层架构

表层体验必须个人化、行动导向：

```text
我的工作台
策略信号
股票候选
交易计划
价格提醒
策略回测
Alpha池
设置
```

底层架构仍然保持机构级思维：

```text
Data Governance
Strategy Backtest
Signal Engine
Decision Object
Trade Plan Object
Alert Engine
Risk Control
Feedback Loop
Controlled Evolution
Agent Governance
```

原则：

```text
表层给个人用户行动清晰度；
底层用 Alpha Factory OS 保证可信度、可审查和可复盘。
```

### 1.4 产品不是

第一阶段明确不是：

```text
不是自动荐股软件
不是保证收益的投资产品
不是自动实盘交易机器人
不是证券投资顾问替代品
不是单纯行情看板
不是纯聊天式 AI 投顾
不是机构级 OMS/EMS
不是无限制策略市场
```

### 1.5 产品是

第一阶段是：

```text
策略信号生成系统
股票候选筛选系统
交易计划生成系统
价格提醒系统
回测审查系统
策略生命周期系统
风险边界提示系统
个人交易复盘系统
AI 研究助手系统
```

### 1.6 目标用户

P0 目标用户：

```text
个人系统化投资者
职业交易者
高阶 A 股/港股/美股投资者
量化研究爱好者
非开发型投资研究者
希望用规则而非情绪交易的个人用户
```

P1/P2 扩展用户：

```text
2-5 人小型投研团队
投资顾问工作室
小型私募研究团队
财经内容研究者
```

---

## 2. 核心用户问题

个人用户真正关心的问题按优先级排列如下。

### 2.1 高频行动问题

```text
今天有哪些股票进入候选？
这些股票分别由什么策略筛出？
当前价格离买入触发价还有多远？
到什么价格提醒我？
跌到什么价格说明信号失效？
上涨到什么价格需要止盈或移动止盈？
每只股票最多配置多少仓位？
我是否需要今天处理？
```

### 2.2 信号可信度问题

```text
这个信号为什么出现？
对应策略历史表现如何？
这个信号是否通过回测审查？
当前市场状态是否适合这个策略？
这个股票是否存在流动性、波动率、行业暴露风险？
策略最近是否退化？
```

### 2.3 交易计划问题

```text
买入触发条件是什么？
计划买入区间是多少？
止损价是多少？
止盈规则是什么？
如果没有触发，该计划什么时候失效？
如果触发后走弱，什么时候提醒我复查？
```

### 2.4 复盘问题

```text
这个信号后来有没有生效？
提醒是否及时？
交易计划是否过于激进？
止损/止盈是否合理？
这类策略最近表现是否衰减？
下一次应该如何调整规则？
```

---

## 3. 核心架构

### 3.1 新核心链路

系统核心链路从原来的研究闭环升级为交易计划闭环：

```text
Data
→ Logic
→ Signal
→ Decision
→ Trade Plan
→ Alert
→ Action
→ Feedback
→ Control
→ Evolution
```

各层含义：

```text
Data：行情、财务、行业、策略、持仓、价格、交易日历等数据。
Logic：策略规则、因子规则、风控规则、信号生成规则。
Signal：由策略生成的股票级候选信号。
Decision：系统对信号可信度、风险、是否可生成计划的判断。
Trade Plan：买入触发、止损、止盈、仓位、失效条件。
Alert：价格提醒、风险提醒、信号失效提醒、策略退化提醒。
Action：用户确认、加入观察、生成计划、设置提醒、模拟记录。
Feedback：信号结果、提醒效果、用户采纳、交易复盘。
Control：风险控制、合规边界、AI 成本、权限和确认机制。
Evolution：策略健康度、信号质量、提醒规则和 Agent 质量的受控演化。
```

### 3.2 产品闭环

P0 产品闭环应优先实现：

```text
启用策略
→ 每日扫描
→ 生成策略信号
→ 形成股票候选
→ 生成交易计划
→ 设置价格提醒
→ 触发提醒
→ 用户记录处理结果
→ 复盘信号质量
```

研究闭环仍保留，但不是 P0 的主入口：

```text
研究想法
→ 因子研究
→ 策略回测
→ 回测审查
→ Alpha池
→ 信号源
```

### 3.3 合规边界

所有前端文案和 Agent 输出必须遵守以下原则：

```text
使用“策略信号”“候选股票”“交易计划”“触发条件”“提醒价”“风险边界”；
避免使用“推荐买入”“强烈买入”“稳赚”“必涨”“目标收益保证”；
明确说明：系统基于策略规则生成条件提醒，不构成投资建议；
用户必须确认后才能加入计划、设置提醒或记录模拟交易；
P0 不提供实盘自动下单能力。
```

---

## 4. 核心对象模型

### 4.1 Strategy 策略

策略是信号来源。策略可以来自系统模板、用户自定义或后续研究生成。

```json
{
  "strategy_id": "STR_001",
  "name": "放量突破策略",
  "type": "breakout",
  "status": "active_signal_source",
  "universe": "A_SHARE_AI_CHAIN",
  "rules": {
    "entry_signal": "price_breaks_20d_high AND volume >= 2 * volume_ma20",
    "invalid_condition": "close < ma20 OR volume < volume_ma20",
    "stop_loss_rule": "entry_price * 0.93",
    "take_profit_rule": "first_target + trailing_stop"
  },
  "backtest_trust_score": 72,
  "strategy_health_score": 68,
  "risk_level": "medium",
  "created_at": "2026-06-10"
}
```

### 4.2 Signal 策略信号

Signal 是策略在某个交易日对某只股票产生的结构化结果。

```json
{
  "signal_id": "SIG_20260610_001",
  "strategy_id": "STR_001",
  "symbol": "300308.SZ",
  "name": "中际旭创",
  "signal_date": "2026-06-10",
  "signal_type": "breakout_watch",
  "signal_status": "waiting_trigger",
  "current_price": 178.20,
  "trigger_price": 181.50,
  "distance_to_trigger_pct": 1.85,
  "confidence_score": 72,
  "risk_level": "medium",
  "evidence": [
    "价格接近20日新高",
    "成交量放大至20日均量1.8倍",
    "所属AI产业链近期动量强"
  ],
  "warnings": [
    "尚未正式突破",
    "需等待成交量确认"
  ]
}
```

### 4.3 CandidateStock 股票候选

CandidateStock 是聚合后的股票候选，可能由一个或多个策略信号支持。

```json
{
  "candidate_id": "CAND_001",
  "symbol": "300308.SZ",
  "name": "中际旭创",
  "industry": "AI算力 / 光模块",
  "candidate_status": "watching",
  "signals": ["SIG_20260610_001"],
  "supporting_strategies": ["放量突破策略", "AI产业链动量因子"],
  "current_price": 178.20,
  "best_trigger_price": 181.50,
  "confidence_score": 72,
  "risk_level": "medium",
  "next_action": "set_entry_alert"
}
```

### 4.4 TradePlan 交易计划

TradePlan 是系统最关键的产品对象。它不是交易指令，而是用户确认后的策略条件计划。

```json
{
  "plan_id": "PLAN_20260610_001",
  "user_id": "USER_001",
  "symbol": "300308.SZ",
  "name": "中际旭创",
  "strategy_id": "STR_001",
  "signal_id": "SIG_20260610_001",
  "plan_status": "waiting_trigger",
  "current_price": 178.20,
  "entry_trigger_price": 181.50,
  "entry_zone_low": 181.50,
  "entry_zone_high": 184.00,
  "stop_loss_price": 169.80,
  "take_profit_price_1": 198.00,
  "take_profit_price_2": 205.00,
  "trailing_stop_rule": "跌破10日均线或从高点回撤超过8%",
  "max_position_weight_pct": 5,
  "invalid_condition": "收盘跌破20日均线或成交量萎缩至20日均量以下",
  "confidence_score": 72,
  "risk_level": "medium",
  "requires_user_confirmation": true,
  "user_confirmed": true,
  "created_at": "2026-06-10T10:32:00"
}
```

### 4.5 PriceAlert 价格提醒

PriceAlert 是用户高频价值点。

```json
{
  "alert_id": "ALERT_001",
  "plan_id": "PLAN_20260610_001",
  "symbol": "300308.SZ",
  "alert_type": "entry_trigger",
  "condition": "price >= 181.50 AND volume >= 2 * volume_ma20",
  "target_price": 181.50,
  "current_price": 178.20,
  "distance_pct": 1.85,
  "status": "waiting",
  "channels": ["in_app", "email", "browser_notification"],
  "created_at": "2026-06-10T10:35:00"
}
```

提醒类型：

```text
entry_trigger：买入触发提醒
stop_loss：止损提醒
take_profit：止盈提醒
signal_invalid：信号失效提醒
strategy_health：策略健康下降提醒
risk_warning：风险提醒
review_due：复盘提醒
```

### 4.6 Decision Object 决策对象

关键决策必须可审计。

```json
{
  "decision_id": "DEC_20260610_001",
  "decision_type": "generate_trade_plan",
  "target_type": "signal",
  "target_id": "SIG_20260610_001",
  "data_inputs": ["market_snapshot_20260610", "strategy_backtest_STR_001"],
  "logic_used": ["breakout_rule_v1", "risk_rule_v1"],
  "recommendation": "generate_waiting_trigger_plan",
  "confidence_score": 72,
  "risk_level": "medium",
  "requires_confirmation": true,
  "allowed_actions": ["create_trade_plan", "set_price_alert", "add_to_watchlist"],
  "forbidden_actions": ["auto_trade", "guarantee_profit"],
  "status": "confirmed_by_user"
}
```

### 4.7 Feedback Event 反馈事件

用于复盘和系统进化。

```json
{
  "feedback_id": "FB_001",
  "object_type": "trade_plan",
  "object_id": "PLAN_20260610_001",
  "feedback_type": "alert_triggered",
  "result": {
    "triggered_at": "2026-06-12T09:48:00",
    "price": 181.70,
    "user_action": "observed_not_executed"
  },
  "notes": "用户收到提醒但未记录买入。",
  "created_at": "2026-06-12T09:50:00"
}
```

### 4.8 Evolution Event 进化事件

用于受控更新策略、信号或提醒规则。

```json
{
  "evolution_id": "EVO_001",
  "target_type": "strategy",
  "target_id": "STR_001",
  "trigger": "signal_success_rate_decline",
  "evidence": [
    "近30个信号触发后5日胜率下降至42%",
    "止损触发比例上升至31%"
  ],
  "proposal": "提高成交量确认阈值，从2.0倍提升至2.3倍",
  "requires_confirmation": true,
  "status": "pending_user_review"
}
```

---

## 5. 功能模块规格

## 5.1 我的工作台

### 5.1.1 页面目标

回答用户每天打开产品时最关心的问题：

```text
今天有哪些信号？
哪些股票需要关注？
哪些计划需要确认？
哪些提醒已经触发？
哪些持仓或策略需要复查？
```

### 5.1.2 核心模块

```text
今日行动摘要
今日策略信号
高可信股票候选
待确认交易计划
已触发价格提醒
风险提醒
策略健康变化
AI 助手下一步建议
```

### 5.1.3 核心卡片

今日行动摘要示例：

```text
今日触发信号：12 个
高可信候选：4 个
待确认交易计划：3 个
已触发提醒：2 个
需复查风险：1 个
```

股票候选卡示例：

```text
中际旭创 300308
策略：放量突破策略
当前价：178.20
触发价：181.50
距离触发：1.85%
风险边界：169.80
可信度：72
动作：设置提醒 / 生成交易计划 / 查看依据
```

---

## 5.2 策略信号

### 5.2.1 页面目标

展示每天由策略生成的股票级信号，并让用户快速判断是否进入候选、生成计划或设置提醒。

### 5.2.2 信号列表字段

```text
股票名称
股票代码
触发策略
信号类型
触发原因
当前价
触发价
距离触发价
可信度
风险等级
状态
下一步动作
```

### 5.2.3 信号状态

```text
watching：观察中
waiting_trigger：等待触发
triggered：已触发
invalidated：已失效
converted_to_plan：已生成计划
ignored：已忽略
```

### 5.2.4 信号解释

每个信号必须提供解释：

```text
为什么出现
对应策略是什么
使用了哪些数据
信号是否已满足全部条件
还差哪些确认条件
如果什么情况发生则信号失效
```

### 5.2.5 允许动作

```text
加入股票候选
生成交易计划
设置价格提醒
查看策略回测
查看信号依据
忽略信号
```

禁止动作：

```text
自动买入
自动卖出
保证收益
强制推荐
```

---

## 5.3 股票候选

### 5.3.1 页面目标

展示由策略筛选出的股票池，帮助用户管理观察列表和候选列表。

### 5.3.2 分组

```text
高可信候选
等待触发
已触发
已失效
已加入交易计划
```

### 5.3.3 股票卡字段

```text
股票名称/代码
行业/主题
触发策略
信号摘要
当前价格
计划买入区间
止损线
止盈规则
可信度
风险标签
是否已设置提醒
```

### 5.3.4 操作

```text
加入交易计划
设置提醒
查看依据
查看策略表现
查看相似信号历史
移出候选
```

---

## 5.4 交易计划

### 5.4.1 页面目标

把策略信号转化为结构化、可提醒、可复盘的个人交易计划。

### 5.4.2 交易计划字段

```text
股票
策略来源
信号来源
当前价
买入触发价
买入区间
止损价
止盈价/止盈规则
移动止盈规则
仓位上限
失效条件
提醒条件
计划状态
用户备注
复盘状态
```

### 5.4.3 交易计划状态

```text
draft：草稿
waiting_trigger：等待触发
triggered：已触发
active_tracking：跟踪中
stop_loss_triggered：止损触发
take_profit_triggered：止盈触发
invalidated：已失效
closed：已关闭
reviewed：已复盘
```

### 5.4.4 计划生成原则

系统生成交易计划时必须遵守：

```text
计划必须来自明确策略信号；
必须显示触发条件，而不是直接要求买入；
必须包含风险边界；
必须包含失效条件；
必须显示可信度和风险等级；
必须由用户确认后才进入正式计划列表；
必须可关闭、可复盘、可删除。
```

### 5.4.5 计划展示文案标准

推荐文案：

```text
当价格突破 181.50 且成交量满足策略条件时，触发买入提醒。
181.50–184.00 为策略计划区间。
跌破 169.80 则当前突破信号失效。
```

禁止文案：

```text
建议你立即买入。
强烈推荐。
必涨目标价。
稳赚机会。
```

---

## 5.5 价格提醒

### 5.5.1 页面目标

让用户不必持续盯盘，系统根据交易计划、策略信号和风险边界自动提醒。

### 5.5.2 提醒类型

```text
买入触发提醒
止损提醒
止盈提醒
移动止盈提醒
信号失效提醒
策略健康下降提醒
风险暴露提醒
复盘提醒
```

### 5.5.3 提醒通道

P0：

```text
站内提醒
浏览器通知
邮件提醒
```

P1：

```text
短信
微信/企业微信
Telegram
Webhook
移动 App Push
```

### 5.5.4 提醒列表字段

```text
股票
策略
提醒类型
触发条件
当前价
目标价
距离
状态
通知方式
创建时间
触发时间
```

### 5.5.5 提醒状态

```text
waiting：等待触发
triggered：已触发
expired：已过期
disabled：已关闭
invalidated：信号已失效
```

---

## 5.6 策略回测

### 5.6.1 页面目标

不是单纯展示收益曲线，而是为信号和交易计划提供可信依据。

### 5.6.2 必须展示

```text
策略定义
信号规则
买入触发逻辑
卖出/止损/止盈逻辑
回测区间
股票池
手续费/滑点
年化收益
最大回撤
胜率
盈亏比
换手率
样本外表现
参数敏感性
交易成本压力
未来函数检查
Backtest Trust Score
```

### 5.6.3 审查结论

回测页面必须输出：

```text
是否可作为信号源
是否可生成股票候选
是否可生成交易计划
是否仅可观察
是否应暂停
```

---

## 5.7 Alpha 池

### 5.7.1 页面目标

管理用户的策略资产和信号源，而不是只管理研究成果。

### 5.7.2 Alpha 卡片新增字段

```text
策略名称
状态
健康度
可信度
今日信号数
高可信候选数
待确认计划数
已触发提醒数
最近风险
下一步动作
```

### 5.7.3 生命周期状态

```text
idea：想法
testing：验证中
signal_source：信号源
watching：观察中
simulation：模拟中
degraded：退化中
paused：已暂停
retired：已淘汰
```

---

## 5.8 研究报告

报告中心应从“研究报告”扩展为“信号与计划复盘档案”。

报告类型：

```text
策略回测报告
信号生成报告
交易计划报告
价格提醒触发报告
交易复盘报告
策略健康报告
周度策略信号总结
```

---

## 5.9 设置

设置页至少包含：

```text
股票市场选择
默认股票池
默认仓位上限
默认止损规则
默认止盈规则
提醒通道
AI 点数额度
合规免责声明确认
模型模式
数据源配置
```

---

## 6. AI Agent 设计

### 6.1 Agent 定位

右侧 AI 助手不再只是研究解释器，而是：

```text
策略信号解释器
交易计划生成器
风险边界审查员
价格提醒配置助手
复盘助手
```

### 6.2 Agent 必须回答的问题

```text
这个股票为什么进入候选？
对应哪个策略？
买入触发条件是什么？
到什么价格提醒？
止损/止盈怎么设？
这个信号有什么风险？
什么情况下信号失效？
是否建议先观察而不是生成计划？
```

### 6.3 Agent 不能做的事

```text
不能直接说“买入某股票”；
不能承诺目标价一定达到；
不能替用户下单；
不能绕过用户确认创建高风险计划；
不能隐藏策略依据；
不能隐藏 AI 成本；
不能绕过合规提示。
```

### 6.4 Agent 调用架构

```text
User
→ Right-side Agent Panel
→ Agent Orchestrator
→ Skill Layer
→ Tool Registry
→ API Layer
→ Domain Services
→ Data / Quant Engine
```

### 6.5 P0 Skills

P0 内置轻量 Skill：

```text
SignalExplainSkill：解释股票为什么入选
TradePlanGenerateSkill：生成交易计划草稿
AlertSetupSkill：配置价格提醒
BacktestAuditSkill：审查策略是否可作为信号源
RiskBoundarySkill：生成止损/止盈/失效条件
PlanReviewSkill：复盘已触发或关闭的计划
```

Skill 是任务模板，不直接访问数据库。所有数据和计算通过 Tool/API。

### 6.6 Tool/API

核心工具：

```text
get_strategy_signal(symbol, strategy_id)
get_signal_list(date, filters)
get_candidate_stocks(filters)
generate_trade_plan(signal_id, user_config)
create_price_alert(plan_id, alert_config)
get_backtest_audit(strategy_id)
get_strategy_health(strategy_id)
get_price_snapshot(symbol)
get_risk_boundary(symbol, strategy_id)
get_plan_review(plan_id)
```

---

## 7. API 模块设计

### 7.1 Signal API

```text
GET /signals
GET /signals/{signal_id}
POST /signals/{signal_id}/ignore
POST /signals/{signal_id}/convert-to-plan
```

### 7.2 Candidate API

```text
GET /candidates
GET /candidates/{candidate_id}
POST /candidates/{candidate_id}/watch
POST /candidates/{candidate_id}/remove
```

### 7.3 Trade Plan API

```text
GET /trade-plans
GET /trade-plans/{plan_id}
POST /trade-plans
PATCH /trade-plans/{plan_id}
POST /trade-plans/{plan_id}/confirm
POST /trade-plans/{plan_id}/close
POST /trade-plans/{plan_id}/review
```

### 7.4 Alert API

```text
GET /alerts
POST /alerts
PATCH /alerts/{alert_id}
POST /alerts/{alert_id}/disable
GET /alerts/events
```

### 7.5 Strategy API

```text
GET /strategies
GET /strategies/{strategy_id}
GET /strategies/{strategy_id}/backtest
GET /strategies/{strategy_id}/health
POST /strategies/{strategy_id}/enable-signal-source
POST /strategies/{strategy_id}/pause
```

### 7.6 Agent API

```text
POST /agent/chat
POST /agent/tasks/explain-signal
POST /agent/tasks/generate-trade-plan
POST /agent/tasks/setup-alerts
POST /agent/tasks/review-plan
GET /agent/tasks/{task_id}
```

---

## 8. 数据表设计

P0 核心表：

```text
users
workspaces
strategies
strategy_backtests
strategy_health
signals
candidate_stocks
trade_plans
price_alerts
alert_events
decision_objects
action_logs
feedback_events
evolution_events
agent_tasks
agent_tool_calls
ai_usage
ai_budget
```

### 8.1 signals

```sql
signals
- id
- workspace_id
- strategy_id
- symbol
- name
- signal_date
- signal_type
- signal_status
- current_price
- trigger_price
- distance_to_trigger_pct
- confidence_score
- risk_level
- evidence_json
- warnings_json
- created_at
```

### 8.2 trade_plans

```sql
trade_plans
- id
- workspace_id
- user_id
- signal_id
- strategy_id
- symbol
- name
- plan_status
- current_price
- entry_trigger_price
- entry_zone_low
- entry_zone_high
- stop_loss_price
- take_profit_price_1
- take_profit_price_2
- trailing_stop_rule
- max_position_weight_pct
- invalid_condition
- confidence_score
- risk_level
- user_confirmed
- created_at
- updated_at
```

### 8.3 price_alerts

```sql
price_alerts
- id
- workspace_id
- user_id
- plan_id
- signal_id
- symbol
- alert_type
- condition_json
- target_price
- current_price
- distance_pct
- status
- channels_json
- triggered_at
- created_at
```

---

## 9. 前端信息架构

P0 导航：

```text
我的工作台
策略信号
股票候选
交易计划
价格提醒
策略回测
Alpha池
设置
```

P1 可增加：

```text
研究想法
因子研究
研究报告
模拟组合
团队协作
```

### 9.1 三栏布局

```text
左栏：导航与用户信息
中栏：当前页面主工作区
右栏：AI 研究助手 / 当前对象解释 / 下一步动作
```

### 9.2 右侧 Agent 固定结构

```text
当前聚焦对象
当前状态
策略/信号摘要
风险边界
推荐下一步
AI 点数消耗
对话区
快捷按钮
合规提示
```

### 9.3 页面优先级

第一优先级页面：

```text
我的工作台
策略信号
股票候选
交易计划
价格提醒
```

第二优先级页面：

```text
策略回测
Alpha池
设置
```

第三优先级页面：

```text
研究想法
因子研究
研究报告
团队能力
```

---

## 10. 风险控制与合规设计

### 10.1 文案边界

允许：

```text
策略信号
股票候选
触发价
计划区间
风险边界
止损提醒
止盈规则
信号失效
模拟复盘
```

禁止：

```text
推荐买入
强烈买入
保证收益
稳赚
内幕机会
必涨
无风险
```

### 10.2 用户确认

必须确认的动作：

```text
生成正式交易计划
设置价格提醒
记录模拟买入
修改止损/止盈规则
启用策略作为信号源
修改默认仓位规则
```

不需要确认的动作：

```text
查看信号解释
查看股票候选
生成计划草稿
生成风险解释
查看回测依据
```

### 10.3 免责声明

所有交易计划、信号和提醒页面底部必须显示：

```text
系统生成内容基于用户选择的策略规则和历史数据，仅用于研究、提醒与复盘，不构成投资建议或收益承诺。市场有风险，交易需由用户自行决策。
```

---

## 11. AI 成本控制

### 11.1 AI Gateway

所有 AI 调用必须经过 AI Gateway：

```text
Intent Classifier
Budget Checker
Context Builder
Model Router
Tool Executor
Usage Logger
Result Validator
```

### 11.2 AI 点数

任务消耗示例：

```text
信号解释：1-3 点
生成交易计划草稿：5-10 点
回测审查摘要：10-20 点
完整策略报告：30-80 点
多策略候选对比：50-100 点
```

高成本任务必须提示用户。

### 11.3 模型分层

```text
L0：模板和规则，不调用模型
L1：低成本模型，用于简短解释
L2：标准研究模型，用于信号解释和计划生成
L3：高级推理模型，用于回测审查和复杂风险判断
```

---

## 12. 受控进化

系统可以自动演化的内容：

```text
策略健康度
信号成功率统计
提醒命中率
候选股票质量评分
Agent 回答模板
报告模板
```

需要用户确认的内容：

```text
修改策略参数
修改止损/止盈默认规则
启用/暂停策略信号源
调整仓位上限
切换数据源
```

禁止自动演化的内容：

```text
自动实盘交易
自动加仓/减仓
自动删除历史计划
自动关闭风险提醒
自动绕过合规提示
```

---

## 13. MVP 范围

### 13.1 P0 必须做

```text
用户登录
我的工作台
策略信号列表
股票候选列表
交易计划生成
价格提醒设置
提醒触发记录
策略回测摘要
Alpha池基础状态
右侧 AI 研究助手
AI 点数记录
基础合规提示
```

### 13.2 P0 策略范围

先内置 3-5 个策略模板：

```text
放量突破策略
动量趋势策略
低估值反转策略
均线回归策略
行业强势轮动策略
```

每个策略必须有：

```text
信号生成规则
买入触发规则
止损规则
止盈规则
失效条件
回测摘要
可信度评分
```

### 13.3 P0 不做

```text
自动实盘下单
复杂团队协作
机构审批流
策略市场
用户自定义复杂公式 DSL
高频交易
复杂衍生品
保证收益类文案
```

### 13.4 P1 做

```text
研究想法
因子研究
更多策略模板
自定义策略参数
模拟交易记录
周度复盘报告
移动端提醒
更多通知通道
```

### 13.5 P2 做

```text
小团队协作
策略分享
企业版权限
私有数据源
自定义 Skill
私有模型/自带 Key
实盘接口前的模拟交易桥接
```

---

## 14. 技术架构建议

### 14.1 前端

```text
Next.js
React
TypeScript
Tailwind CSS
shadcn/ui
TanStack Query
TanStack Table
ECharts / Recharts
Zustand
```

### 14.2 后端

```text
FastAPI
Pydantic
SQLAlchemy
Alembic
PostgreSQL
Redis
Celery / RQ / Dramatiq
```

### 14.3 数据与量化引擎

```text
Python
Polars
DuckDB
Parquet
pandas 兼容层
向量化回测引擎
事件驱动回测后置
```

### 14.4 Agent Engine

```text
Agent Gateway
Skill Layer
Tool Registry
Model Router
Context Builder
Usage Logger
Decision Engine
```

### 14.5 服务模块

```text
Market Data Service
Strategy Service
Signal Service
Candidate Service
Trade Plan Service
Alert Service
Backtest Service
Risk Service
Agent Service
Billing/Quota Service
```

---

## 15. 成功指标

### 15.1 产品指标

```text
DAU/WAU
每日查看信号数
候选股票加入率
交易计划生成率
价格提醒设置率
提醒触发后的用户处理率
计划复盘率
策略启用率
```

### 15.2 质量指标

```text
信号触发准确率
信号失效率
提醒准时率
策略健康度下降识别速度
回测审查通过率
用户采纳率
```

### 15.3 商业指标

```text
免费到付费转化率
Pro 用户留存率
AI 点数消耗/收入比
单用户 AI 成本
加量包购买率
续费率
```

---

## 16. 最终产品原则

```text
1. 用户要的是可执行计划，不只是研究报告。
2. 所有股票候选必须来自明确策略信号。
3. 所有交易计划必须包含触发价、止损价、止盈规则和失效条件。
4. 所有提醒必须可配置、可追踪、可复盘。
5. 所有 AI 输出必须基于数据和策略规则，不能凭空荐股。
6. 所有高风险动作必须用户确认。
7. 所有信号和计划必须可审计、可解释、可回溯。
8. 系统底层保留 Alpha Factory OS，但前端优先服务个人行动决策。
```

一句话总结：

> 本产品不是告诉用户“买哪只股票一定赚钱”，而是帮助用户把自己的策略变成可解释的股票候选、条件化交易计划、价格提醒和复盘闭环。


# MULTI_TENANT_PAYMENT — 多租户隔离与微信支付架构

> 定位:策略审计 SaaS 的租户隔离模型 + 微信支付完整闭环设计。
> 决策:个人租户(每用户独立 tenant_id),全表预留字段,未来加团队租户不重构。
> 支付场景:订阅月/年费 + Token 包购买 + 升级 + 7天无理由退款。
> 本文档先于代码,定数据模型、定支付链路、定幂等与对账。

---

## 1. 多租户隔离模型

### 1.1 个人租户(当前)

```
微信用户(openid) ──首次登录──> 自动创建 tenant_id
                                  │
                                  ↓
所有业务表均带 tenant_id 字段,查询必带 WHERE tenant_id = ?
```

**核心原则:**
- 一个 openid = 一个 tenant_id(1:1,当前阶段)
- 首次 `wx.login` + 后端 `jscode2session` 拿到 openid → 自动建 user + tenant
- 所有业务表(users / subscriptions / token_ledger / audit_history / payment_orders)**全部带 tenant_id**
- 后端所有查询/写入必须带 tenant_id 过滤,中间件强制注入
- 租户间数据物理隔离(不共享任何业务数据)

### 1.2 团队租户(未来扩展,当前预留)

未来加团队租户**不需要改业务表**,只加:
- `organizations` 表:org_id / name / owner_tenant_id / billing_tenant_id
- `user_org` 关联表:tenant_id / org_id / role(admin/member)
- 个人 tenant 升级为 org_tenant 时,业务表 tenant_id 指向 org_id

当前所有表已预留 tenant_id 字段,扩展零重构。

### 1.3 租户隔离的工程实现

```python
# 中间件:从 JWT 解析 tenant_id,注入请求上下文
async def tenant_context_middleware(request: Request, call_next):
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    payload = verify_jwt(token)
    request.state.tenant_id = payload["tenant_id"]  # 注入
    request.state.openid = payload["openid"]
    return await call_next(request)

# 所有 service 层查询强制带 tenant_id
class AuditHistoryService:
    def list(self, tenant_id: str, limit: int = 20):
        # WHERE tenant_id = ? 强制过滤
        return db.query(AuditHistory).filter_by(tenant_id=tenant_id).limit(limit).all()
```

**安全红线:**
- 任何不带 tenant_id 过滤的查询 = P0 bug
- CI 加守卫:grep 所有 db.query 调用,检查是否带 tenant_id filter
- 单元测试:跨租户查询必须返回空

---

## 2. 微信支付三场景闭环

### 2.1 场景1:Token 包购买(普通支付,即时到账)

```
小程序                          后端                         微信支付
  │                              │                              │
  │ 1.选10/30/100 token包         │                              │
  ├─────────────────────────────>│                              │
  │                              │ 2.创建 payment_order(待支付)  │
  │                              │ 3.调统一下单 API              │
  │                              ├─────────────────────────────>│
  │                              │ 4.返回 prepay_id + 签名参数   │
  │                              │<─────────────────────────────┤
  │ 5.返回 prepay 参数            │                              │
  │<─────────────────────────────┤                              │
  │ 6.wx.requestPayment 拉起收银台│                              │
  │ 7.用户输入密码支付            │                              │
  ├─────────────────────────────────────────────────────────────>│
  │ 8.支付成功                    │                              │
  │<─────────────────────────────────────────────────────────────┤
  │                              │ 9.异步回调 notify_url         │
  │                              │<─────────────────────────────┤
  │                              │ 10.验签+幂等+加token          │
  │                              │ 11.推送支付成功通知           │
  │ 12.刷新余额(轮询或推送)       │                              │
  │<─────────────────────────────┤                              │
```

**关键点:**
- `payment_order` 创建时状态=`pending`,带 `tenant_id` + `product` + `amount`
- 微信回调 `notify_url` 必须 HTTPS,验签 + 幂等(用 `wx_transaction_id` 去重)
- 验签通过后:order 状态→`paid`,token_ledger 加一笔 `reason=buy` 的记录
- token 加账是事务性的:order 状态更新 + ledger 写入在同一事务

### 2.2 场景2:订阅(周期扣款签约)

微信支付有两种订阅实现方式,**选哪个取决于商户资质**:

| 方式 | 说明 | 优劣 |
|---|---|---|
| 周期扣款(委托扣款) | 用户签约 → 微信到期自动扣 | 体验好续费率高,但需商户开通权限,审核严 |
| 普通支付 + 到期提醒 | 每次手动支付,到期推"续费" | 简单无门槛,但续费率低 |

**MVP 阶段建议:普通支付 + 到期提醒**(降低审核风险,先验证付费意愿)
**V1 升级:申请周期扣款权限**(续费率提升 30%+)

#### MVP 订阅流程(普通支付)

```
1. 用户选 PRO ¥29/月
2. 后端创建 subscription_order(月度,amount=29)
3. 调统一下单 → 用户支付 → 回调验签
4. 开通权益:subscriptions 表写一条,status=active,period_end=now+30天
5. 月度额度 30 token 立即到账(token_ledger reason=subscribe)
6. 到期前 3 天推送订阅消息"您的会员即将到期"
7. 到期日:status→expired,降级 FREE(额度清零,token包保留)
8. 用户重新支付续费 → 新一期
```

### 2.3 场景3:升级与退款

#### 升级(PRO → MAX)

```
1. 计算剩余价值:剩余天数 / 当期天数 × 已付金额 = 退款额
   例:PRO 用了 10 天,剩 20 天,29×(20/30)=¥19.33
2. 调微信退款接口,退 ¥19.33
3. 新订 MAX:创建新 order ¥99,用户支付
4. 开通 MAX 权益,周期重新计算 30 天
5. token:旧 PRO 额度清零,新 MAX 额度 120 到账
```

#### 降级(MAX → PRO)

- **当期不退费**(避免纠纷),MAX 权益用到 period_end
- period_end 后自动降为 PRO(用户需提前选好 PRO)
- 不主动诱导降级,设置入口在「我的」深处

#### 7 天无理由退款

```
条件:订阅 7 天内 + 未使用任何 token
流程:
1. 用户申请退款
2. 检查 token_ledger:该订阅周期内 reason=audit 的记录数=0
3. 调微信退款(全额)
4. subscription.status→refunded,token 清零
5. 降级 FREE

已用 token 的情况:
1. 按 已用次数 / 月度额度 × 月费 计算已消耗价值
2. 退款 = 月费 - 已消耗价值
3. 例:PRO 用了 5 次 token(5/30),29×(5/30)=¥4.83,退 29-4.83=¥24.17
4. 协议明确写"已使用部分按比例扣减"
```

#### 审计失败退 token

- job 失败 → 自动退还预扣 token(token 状态 pending→available)
- 不涉及钱,纯 token 账本操作
- 失败原因记入 audit_history,用户可查

---

## 3. Token 预扣机制(防并发超用)

```
提交审计
  │
  ↓
检查 token 余额(available ≥ 需消耗量?)
  │ 不足 → 引导购买 token 包
  │ 足够 ↓
预扣 token:available → pending(冻结)
  │
  ↓
入队 audit_queue,返回 job_id
  │
  ↓ (5-20 分钟,worker 处理)
  │
  ├─ 成功:pending → consumed(确认扣减),写 audit_history
  └─ 失败:pending → available(退还),写失败原因
```

**关键:**
- 预扣是事务性的:余额检查 + 状态变更原子操作,防并发超用
- token 有三种状态:`available`(可用) / `pending`(冻结) / `consumed`(已消耗)
- 余额查询 = SUM(delta WHERE state=available),不含 pending/consumed
- job 超时(30 分钟无结果)→ 自动退还 pending token

---

## 4. 关键数据表设计

### 4.1 users / tenants

```
users
  id              VARCHAR(36) PK
  openid          VARCHAR(64) UNIQUE    -- 微信小程序 openid
  unionid         VARCHAR(64) NULL      -- 跨应用识别(有则存)
  tenant_id       VARCHAR(36) UNIQUE    -- 1:1 当前阶段
  nickname        VARCHAR(64)
  avatar_url      VARCHAR(256)
  created_at      TIMESTAMP
  last_login_at   TIMESTAMP

tenants  -- 当前 1:1 users,未来 1:N(团队)
  id              VARCHAR(36) PK
  type            ENUM('personal','organization')  -- 预留
  created_at      TIMESTAMP
```

### 4.2 subscriptions

```
subscriptions
  id              VARCHAR(36) PK
  tenant_id       VARCHAR(36) INDEX     -- 租户隔离
  plan            ENUM('free','pro','max')
  status          ENUM('active','expired','cancelled','refunded')
  period_start    TIMESTAMP
  period_end      TIMESTAMP             -- 到期日
  auto_renew      BOOLEAN               -- MVP=false,V1 周期扣款=true
  contract_id     VARCHAR(64) NULL      -- 微信周期扣款签约号(V1)
  monthly_quota   INT                   -- 月度 token 额度
  used_quota      INT                   -- 已用(审计成功才计)
  cancel_at       TIMESTAMP NULL        -- 用户主动取消时间
  created_at      TIMESTAMP
```

### 4.3 token_ledger(append-only 账本)

```
token_ledger
  id              BIGINT PK AUTO_INCREMENT
  tenant_id       VARCHAR(36) INDEX     -- 租户隔离
  delta           INT                   -- +N 加 / -N 扣
  balance_after   INT                   -- 操作后余额(冗余,便于查询)
  reason          ENUM('subscribe','buy','audit_pre','audit_confirm','audit_refund','refund_sub','admin_adjust')
  ref_id          VARCHAR(64) NULL      -- order_id 或 job_id
  state           ENUM('available','pending','consumed','refunded')
  created_at      TIMESTAMP

  -- 查询余额:SELECT COALESCE(SUM(delta),0) WHERE tenant_id=? AND state='available'
  -- 账本 append-only,只增不删,审计可追溯
```

### 4.4 payment_orders / refunds

```
payment_orders
  id              VARCHAR(36) PK
  tenant_id       VARCHAR(36) INDEX
  order_no        VARCHAR(32) UNIQUE    -- 商户订单号
  product_type    ENUM('subscription','token_pack')
  product_detail  JSON                  -- {plan:'pro', period:'monthly'} 或 {tokens:10}
  amount          INT                   -- 分(避免浮点)
  status          ENUM('pending','paid','failed','refunded','partial_refunded')
  wx_prepay_id    VARCHAR(64) NULL
  wx_transaction_id VARCHAR(64) NULL    -- 微信支付单号
  paid_at         TIMESTAMP NULL
  callback_at     TIMESTAMP NULL
  created_at      TIMESTAMP

refunds
  id              VARCHAR(36) PK
  order_id        VARCHAR(36) FK         -- 原订单
  tenant_id       VARCHAR(36) INDEX
  refund_no       VARCHAR(32) UNIQUE
  amount          INT                    -- 退款金额(分)
  reason          ENUM('7day_no_reason','upgrade_prorate','subscription_cancel','admin')
  status          ENUM('processing','succeeded','failed')
  wx_refund_id    VARCHAR(64) NULL
  created_at      TIMESTAMP
```

### 4.5 audit_history

```
audit_history
  id              VARCHAR(36) PK
  tenant_id       VARCHAR(36) INDEX     -- 租户隔离
  job_id          VARCHAR(36) UNIQUE
  spec            JSON                  -- 用户确认的策略 spec
  status          ENUM('queued','running','succeeded','failed','cancelled')
  result          JSON NULL             -- 9-Gate 报告
  verdict         ENUM('viable','inconclusive','falsified') NULL
  tokens_consumed INT                   -- 实际消耗 token
  submitted_at    TIMESTAMP
  completed_at    TIMESTAMP NULL
  fail_reason     TEXT NULL
```

---

## 5. 微信支付商户准备清单

### 5.1 资质准备(MVP 前必须完成)

| 项 | 说明 | 周期 |
|---|---|---|
| 微信小程序账号 | 已有 AppID | - |
| 微信支付商户号 | 需企业资质申请 | 3-5 工作日 |
| 商户号绑定小程序 | 在商户平台关联 AppID | 即时 |
| 虚拟商品类目 | 小程序后台选"虚拟商品" | 即时 |
| HTTPS 域名 + 备案 | 回调地址必须 HTTPS | 7-20 天(备案) |
| APIv3 密钥 + 证书 | 商户平台生成 | 即时 |
| 退款权限 | 默认开通 | - |

### 5.2 周期扣款(V1 升级时申请)

- 需要额外申请"委托扣款"权限
- 审核较严,需提供业务场景说明
- 通过后续费率提升 30%+

### 5.3 域名白名单(小程序后台)

```
request 合法域名:https://api.yourdomain.com
```

---

## 6. 安全与对账

### 6.1 支付安全

- 所有金额用**分**存储(整数,避免浮点误差)
- 回调必须验签(APIv3 RSA 签名)
- 回调必须幂等(用 `wx_transaction_id` 去重)
- 退款必须双向确认(申请 + 回调)
- 支付订单 24 小时未支付自动关闭

### 6.2 对账机制

- 每日对账:拉微信支付账单 vs 本地 payment_orders
- 差异告警:金额不符 / 状态不符 / 缺失订单
- token 账本每日快照,异常余额变动告警
- 月末汇总:订阅收入 + token 包收入 + 退款支出

### 6.3 风控

- 同一 openid 短时间多次支付失败 → 限流
- 退款频率异常(7 天内多次)→ 人工审核
- token 异常消耗(1 小时内 >50 次)→ 限流 + 告警

---

## 7. MVP 支付功能取舍

### MVP 必须有
- Token 包购买(10/30/100,普通支付)
- 订阅月付(PRO ¥29,普通支付 + 到期提醒)
- 7 天无理由退款(未用 token 全退)
- token 预扣 + 失败退还

### MVP 可以没有
- 订阅年付(先月付验证留存)
- 订阅升级(等有 MAX 再加)
- 周期扣款签约(V1 申请权限后)
- 已用 token 按比例退款(MVP 只支持未用全退,简单)

### V1 迭代
- 年付 + 续费激励
- MAX 档 + 升级流程
- 周期扣款(自动续费)
- 已用 token 按比例退款

---

## 8. 与现有架构的集成

### 新增后端模块

```
api/routers/payment.py           支付下单/回调/退款
api/routers/subscription.py      订阅状态/取消/续费
services/billing/
  ├── token_ledger.py            token 账本(预扣/确认/退还)
  ├── plan_quota.py              套餐额度管理(月度重置)
  ├── wechat_pay.py              微信支付封装(下单/验签/退款)
  └── refund.py                  退款流程
services/tenant/
  ├── tenant_context.py          租户上下文中间件
  └── tenant_guard.py            查询强制带 tenant_id 守卫
app_config/pricing.yaml          定价配置
app_config/wechat_pay.yaml       微信支付配置(商户号/密钥/AppID)
```

### 数据库

- SQLite(MVP,单文件,本地 Mac 跑)+ 未来升 PostgreSQL
- 表加 `tenant_id` 索引
- token_ledger append-only,定期归档

### 审计流程集成点

```
提交审计前:token_ledger 检查余额 → 不足返回 402 + 引导购买
审计入队:token 预扣(available→pending)
审计成功:token 确认(pending→consumed)+ 写 audit_history
审计失败:token 退还(pending→available)+ 写失败原因
```

---

## 9. 风险与对策

| 风险 | 对策 |
|---|---|
| 跨租户数据泄露 | 中间件强制注入 tenant_id + CI 守卫 + 单元测试 |
| 支付回调丢失 | 主动查单(每 5 分钟扫 pending 订单)+ 微信对账 |
| token 并发超用 | 预扣机制 + 事务原子操作 |
| 退款薅羊毛 | 7 天限制 + 未用 token 检查 + 异常频率风控 |
| 微信支付审核卡住 | 提前备齐虚拟商品资质 + 订阅协议 + 退款政策 |
| 周期扣款权限申请失败 | MVP 用普通支付兜底,不依赖周期扣款 |
| 商户号申请慢 | 与域名备案并行启动,都是长周期 |

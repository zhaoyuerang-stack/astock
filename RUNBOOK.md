# RUNBOOK.md —— 每日运行手册(一页)

> 目标:每天按这页跑通「数据 → 信号 → 自动模拟盘 → 监控 → 解读」。系统会自动执行 paper_trade 模拟盘,但**不自动真实下单**,实盘执行决策留给人。
> 命令均在 `factor_research/` 下;Web 在 `web/` 下。

---

## ① 每天早上(5 分钟)

```bash
cd /Users/kiki/astcok/factor_research

# 推荐:带新鲜度校验的生产入口(数据未达预期最新交易日则跳过出信号,不会用旧数据硬出)
python3 scripts/ops/scheduled_daily_update.py

# 手动入口(出当日信号:联网增量更新 + 质量校验 + 择时 + 持仓 + 调仓判断 → signals/YYYY-MM-DD.json)
# 注意:数据更新失败时会继续用旧数据出信号,务必看 [2] 质量校验输出确认未 stale
python3 run_daily.py                 # 不想联网就加 --no-update,用现有数据
```
看输出 6 步:`[2]` 质量校验、`[3]` regime(🟢BULL/🔴BEAR)、`[5]` 调仓判断。
- **BEAR → 空仓**,闲置资金建议配 `511010 国债ETF`;**BULL → 按 Band exposure(0~1.5x) 配置 illiq top-25**。
- 距上次调仓 **≥20 交易日** 才换仓,否则继续持有/观望。

产物:`signals/今天.json`(timing/regime/holdings/action)、`signals/state.json`(当前仓位)。

---

## ② 打开产品看板(Web)

```bash
# 终端A(后端,必须 --reload,改代码自动加载)
cd /Users/kiki/astcok/factor_research && python3 -m uvicorn api.main:app --port 8011 --reload
# 终端B(前端,dev 模式热重载)
cd /Users/kiki/astcok/web && npm run dev
```
浏览器开 **http://localhost:3000**,后端默认 **http://127.0.0.1:8011**,九页看这些:
| 页面 | 每天看什么 |
|---|---|
| 总览 | 当前状态(空仓/持仓)、因子健康、数据质量预警 |
| 数据中心 | 质量判定应=「可用」;severe(负价/OHLC)应=0 |
| 风险控制 | verdict(正常/预警/超限)+ 待确认 ControlAction |
| 组合管理 | 当前 vs 目标组合(目标=选股层 top-25) |
| 因子研究 / 研究实验 | 因子家族 / 假设池漏斗 + 已登记实验 |
| 右栏 Agent | 问「当前风控如何」「数据质量怎样」→ DeepSeek V4 真解读;**调仓/下单只提案不执行** |

---

## ③ 红灯排查(看到就停)

| 现象 | 含义 / 处置 |
|---|---|
| `validate_final.py` 退出码 1 | severe 数据真问题(负价/OHLC)→ 查 `lake/quarantine.json` 隔离,或 `repair_ohlc` |
| 数据中心 verdict ≠ 可用 | 严重数据问题,**不建议回测**,先修数据 |
| 风控 verdict = 超限 | 看 ControlAction,人工二次确认后才动(系统不自动执行) |
| 因子健康 trend「减速」+ 夏普下滑 | 母策略可能衰减,进 LESSONS / 考虑退役 |

---

## ④ 每周 / 按需

```bash
python3 validate_final.py                      # 全市场数据质量(severe>0 即非零退出)
python3 strategy_lake.py                        # 真实口径复测(2018-2026 + 2010 压力)
python3 strategy_registry.py                    # 母策略台账对比
python3 scripts/ops/generate_factor_health.py   # 刷新 reports/factor_health.json
python3 scripts/ops/paper_trade.py              # 纸面账户跟踪 → paper/
python3 scripts/research/cost_sensitivity.py     # 成本敏感性
bash scripts/test_all.sh                         # 全套测试 + 分层守卫(改完代码必跑)
```
定时任务(launchd):`scripts/ops/install_launchd_jobs.sh`(每日更新 / 每周维护 / FastAPI :8011 / Web :3000)。

---

## ⑤ LLM(Agent 大脑)配置

设置页「AI 模型配置」填 → 保存 → 测试连接(绿✓即通):
- **DeepSeek**:provider=`openai_compatible`,model=`deepseek-v4-flash`(或 `-pro`),base_url=`https://api.deepseek.com/v1`
- 其余示例见 `app_config/settings.yaml::ai_model` 注释(Qwen/Kimi/GLM/Ollama/OpenAI/Anthropic)
- Key 存 gitignored 文件,不进 git;留空=不改 LLM 永不下单/越权。

---

## ⑥ 常见运行态坑(本项目踩过)

| 坑 | 解 |
|---|---|
| 后端改了路由没生效 / 页面接口 404 | uvicorn 用 `--reload`;或杀掉重启 |
| 前端白屏 / chunk 404 | **别在 dev 跑 `npm run build`**(污染 `.next`);dev 运行时只用 `npx tsc --noEmit` + `npm run lint` 做验证;若已污染,先 `lsof -ti :3000 | xargs kill -9` 停 dev,再 `rm -rf web/.next` 后重启 `npm run dev`,最后浏览器硬刷新 ⌘⇧R |
| 端口被占 | `lsof -ti :8011 \| xargs kill -9`(前端同理 :3000) |
| 删过的死文件又冒出来 | Google Drive 同步会复活已删文件 → `rm` 掉;建议把 repo 移出 Drive 同步 |

---

## ⑦ 按任务类型选检查(原 `CLAUDE.md` §13，2026-07-11 下沉到本文件)

每次任务至少选相关检查；一键入口 `bash scripts/test_all.sh`(含分层守卫 + 数据湖写入守卫 + 全量测试发现)。

| 任务类型 | 必查 |
|---|---|
| 数据 | 数据质量校验、schema 校验、样本覆盖、异常报告 |
| 因子 | 单元测试、防未来检查、截面 sanity check |
| 回测引擎 | engine tests、成本测试、边界条件测试 |
| 策略 | 样本内、样本外、压力测试、成本敏感性 |
| workflow | phase1-4 流程测试、入册测试、失败路径测试 |
| registry | schema 测试、唯一写入口测试、历史兼容测试 |
| production | 生产信号 smoke test、禁止研究层 import |
| web | 类型检查、lint、组件测试；开发期不得用 build 代替检查 |
| docs | 链接、规则编号、状态同步 |

## ⑧ 机器规格与并行边界

本机 = **Apple M5(10 核:4 性能 + 6 能效)/ 24GB**。并行/接口反封禁的具体铁律见根 [`CLAUDE.md`](CLAUDE.md) §9/§15；本行只留硬件事实，不重复规则。

---

## 能力边界(诚实)
跑通 = **研究决策闭环**(数据→信号→自动模拟盘→监控→解读),**刻意停在真实账户执行之前**。
未做:真实盘下单(无券商接口)、行业/市值集中度风控(缺 industry_map)、异步 Worker、多用户/Auth。

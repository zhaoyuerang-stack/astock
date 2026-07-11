# 全球数据基础设施更新计划

## Summary

- 目标:把现有 A 股数据湖扩展成多资产数据底座,但不替代当前 A 股 canonical lake;OpenBB 只作为可选 provider 入口之一。
- 第一里程碑:全资产骨架落地,覆盖全球宏观、海外股票/ETF/指数、利率/汇率/商品、衍生品/期权、新闻/监管/事件数据的 catalog、探测、入湖、质量状态和研究台入口。
- 生产策略:接入 daily update,但默认非阻塞;全球数据失败只能产生 `partial_ok`/数据健康告警,不能打断现有 A 股信号,除非配置显式设为 required。
- 官方前提:OpenBB 不托管数据,provider 覆盖和授权取决于已安装扩展/API key。

## Key Changes

- 在 `app_config.settings` 增加 `GlobalDataConfig`,包含 `enabled`、`required`、`provider_mode`、`datasets`、`api_key_envs`、`max_daily_failures`;`settings.yaml` 给出默认 disabled/non-required 配置。
- 建立全球数据 dataset registry,最少定义 `macro_daily`、`macro_monthly`、`market_price_daily`、`etf_daily`、`fx_daily`、`rates_daily`、`commodity_daily`、`derivatives_daily`、`news_events`、`regulatory_filings`;每个 dataset 必须声明 asset_class、provider、frequency、calendar、timezone、currency、PIT 可见性规则和生产 required 状态。
- OpenBB adapter 必须懒加载,缺包/缺 key 返回结构化 `ProviderUnavailable`,不能在 import API、scheduler、tests 时崩溃。
- 全球数据写入 `data_lake/global/...`,manifest 写入 `data_lake/global_manifest.json`;所有写入经 `lake/` 下 canonical writer。
- 提供 `load_global_series()`、`load_global_price_panel()`、`load_global_macro()`,并复用/扩展 PIT 对齐规则。
- 在 `scripts/ops/scheduled_daily_update.py` 增加 `global_data_update` step;失败进入 report、triage 和 alert body,默认不阻断 A 股生产。
- 新增 `/data/global/sources`、`/data/global/coverage`、`/experiments/global-data/probe`;扩展现有 `/data-health` 和 `/experiments`,不新建独立页面。
- global data probe 只能生成数据维度候选/可用性报告,不得直接注册策略、不得绕过 hypothesis、holdout、9-Gate 或 promotion workflow。

## Tests And Verification

- Python targeted tests:catalog schema、settings load、OpenBB missing import、fake provider ingestion、manifest drift、global loader PIT alignment、canonical writer guard、scheduler partial failure、API contract。
- Frontend tests:typecheck、API client mock、data-health global source row、experiments probe launch/polling 状态。
- Guards:`python3 factor_research/scripts/ci/check_layer_deps.py`、lake writer guard、no legacy/direct lake write guard。
- Final gate:先跑 focused tests,再跑 `bash factor_research/scripts/test_all.sh`;web 侧跑 `npm run lint` 和 `npx tsc --noEmit`。

## Risk Controls

- OpenBB 是补充入口,不是数据真相源;A 股 canonical source、回测引擎、registry、holdout 规则不变。
- provider 授权/覆盖不可控;catalog 记录 entitlement 状态,缺 key/无权限不静默 fallback。
- 跨市场 calendar/timezone/currency 错配;dataset 必须声明 calendar、timezone、currency,未声明不得进入因子计算。
- 新闻、期权、监管数据容易污染 PIT;v1 只做 probe/研究候选,不做生产因子依赖。
- global update 默认 auxiliary,只有配置 required 的 dataset 才影响生产 readiness。

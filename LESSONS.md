# LESSONS — 踩过的坑与关键决策

> 项目内可见的经验库(我的私有 auto-memory 作补充)。新踩的坑、新做的决策往这里加。

## 数据源 / 联网
- **东财封禁规律**:逐只接口下 40-50 只就封(返回空 / JSONDecodeError),降速也压不住。**解法 = 换批量/聚合接口**(按报告期 `yjbb_em` 把请求从 2万 → 几十次),**绝不加多线程**(更快触发封禁)。批量接口还白送 退市股 + 公告日 + 行业。
- **akshare hang**:某些请求卡死整个流程。唯一可靠超时 = **daemon 线程 + join(timeout)**(超时后后台自灭);ThreadPoolExecutor(shutdown 会等 hang)、socket.setdefaulttimeout、requests monkey-patch 都无效。
- **代理**:本地 clash(7897)下 **新浪源可用、东财 push2 被拦**(ProxyError/502);加 `DOMAIN-SUFFIX,eastmoney.com,DIRECT` 可恢复东财。联网需 `dangerouslyDisableSandbox`。
- **代码列表偏差**:旧 stocks.json 只有沪市主板(60开头)→ 严重样本偏差(纯蓝筹天花板仅 17%)。必须全市场(`ak.stock_info_a_code_name()`;新浪源加 sh/sz 前缀,北交所 4/8 跳过)。
- **Python 解释器**:回测/工厂脚本必须用 **`/usr/bin/python3`**(系统 Python,有 pandas/numpy);homebrew 的 `/opt/homebrew/bin/python3` 没装,会 `ModuleNotFoundError: pandas`。只用标准库的脚本(如 `strategy_registry`)两个都能跑,**容易掩盖这个坑**——跑回测一律 `/usr/bin/python3 -m ...`。

## 数据正确性
- **防未来函数**:财务用**公告日(ann_date)**对齐交易日 ffill,T 日只用 T 日前已披露。验证:ROE 变化点应落在财报披露日之后(茅台年报在 4 月)。
- **复权陷阱**:后复权价 ÷ 原始 EPS 算 PE 量纲不匹配(虚高数倍)。**估值 PE/PB 必须用不复权价**。同理**模拟盘/实盘下单股数、容量参与率也必须用不复权价**——后复权价虚高数倍(茅台后复权 8859 vs 真实 1306),按它算 `shares=预算/价//100×100` 会把小盘股也买成 0 股(2026-06 `paper_trade` 踩到:预览买 0 只;改读 `data_lake/price/daily_raw` 的 `raw_close` 后正常买满 25 只)。
- **当天信号必须用因子真正依赖的字段判数据完整**(2026-06):每日盘后增量只更后复权 `daily`,不复权 `daily_raw`(目前周度维护)滞后;而 `small_cap_factor/timing` 用的 `amount=volume×raw`,raw 缺则**最新日 amount 全 NaN → factor 全 NaN → 选不出 top25、择时值失真**(实测 06-03 close 有 4953 只但 amount=0;更早 06-04 是当天盘后只抓到 117 只)。`latest_signal` 用 `close.index[-1]` 会撞这个残缺日,今天碰巧空仓没爆,但择时值已脏(同一天 -2.99%→-3.46%→-3.89% 随口径变干净)。**修复**:`load_price_panels` 按 **amount 完整性(非 close)**截断尾部不完整日——取最近 60 日有效股数中位,截断到最后一个 ≥0.7×常态 的交易日。教训:完整性判断要用**下游真正消费的字段**,表面有 close 不代表 factor 能算。**已根治(2026-06-05)**:`fetch_raw_close` 改拉不复权 OHLC + 增量模式,`daily_update` 每日同步 `daily_raw`,amount 不再滞后。
- **模拟盘=真实盘的成交口径**(2026-06,用户要求"所有模拟按真实盘"):`paper_trade` 重构为 **T+1 开盘价成交**——T 日盘后出信号、收盘后才看到,只能次日开盘买(pending order 跨天结算);成交/估值全用**不复权** `daily_raw`(raw_open 成交、raw_close 估值);**停牌**(当日无 open)不可买卖、**一字涨停**买不进、**一字跌停**卖不出。**涨跌停价必须按分四舍五入** `round(prev_close×(1±limit), 2)`——否则 6.73×1.1=7.403 会漏判开盘 7.40 的涨停(端到端测试抓到)。板块幅度 主板10%/创业科创20%/ST5%。**回测口径(收盘撮合)不动——回测归回测、成交归真实买卖**(两套口径分离)。
- **成交额 amount 两层单位坑**(2026-06):`data_lake` 的 `amount` 是 `volume×复权close` 补出来的——① 用**复权价** → 复权因子逐股不同,**污染 `small_cap_factor`/`small_cap_timing` 的截面排序**(偏向复权因子小的次新/老股,选股+择时双中招);② `volume` 单位是**手**(×100 股)。真实成交额 = `volume×100×不复权价`。已在 `core/backtest.py::load_price_panels` 修正——消除污染后 v2.0 选股变、全部数字要重测。凡用 amount 的截面排序(选股)或绝对值(容量)都必须用此口径。
- **质量判定**:区分真问题(OHLC 错/负价/跳变>50%)vs A股正常现象(停牌=孤立缺失/新股首日/一字板)。把停牌当问题会让干净率从 97% 假跌到 68%。交易日历用几只超级大盘股**高频交集**(非并集)。

## 策略 / 回测
- **幸存者偏差水分**:`active=(volume>0)` 过滤剔退市股 → 高估约 8.5%(v1.0 40% → v2.0 真实 32%)。进化/回测必须含退市股。
- **回测必须预热**(2026-06):`small_cap_factor`(rolling60)、`small_cap_timing`(MA16)依赖历史窗口,从目标区间直接起跑会**冷启动虚高**(v2.0 从 2018 跑 24.2%/夏普1.53 vs 从 2010 预热再切 2018 的 **22.2%/1.38**)。正确做法:**从更早(如2010)加载、连续跑、再切目标区间统计**;factory 评估候选同样要预热,否则又是一批冷启动假候选。
- **v2.0 真身(干净 amount + 预热,2026-06)**:样本内 2018-2026 **22.2%/-20.0%/夏普1.38/卡玛1.11**(达满意线、未达卓越);压力 2010-2026 24.2%/-31.7%/1.27。**剔极端年(2015/2021/2025)常态仅 15%/夏普0.9——满意线达标全靠小盘疯牛年,常态平庸**;容量~2千万、可成交>98%。定位**组合一块、不单吊**。证伪轨迹:v1.0夏普2.06水分→污染21%/1.14→冷启动24%/1.53→真身22%/1.38。
- **PureTrend MA16 是 A 股策略的生存必需,不是可选开关(2026-06-06)** :测试 8 种策略在无择时下的表现——全部回撤 43-86%。illiquidity 无 PT 时 +31.3%/-73.4%,加 PT 后 +29.7%/-30.5%。PureTrend 用 ~2% 年化代价换 40+pp 回撤保护。没有 PT,任何 A 股日频因子都是不可投资的过山车。**结论:PureTrend MA16 是通用最优开关,在所有策略上验证,无例外。**
- **Band: PureTrend 的 dist 连续仓位缩放(2026-06-07)**:Binary PT 只用了 MA16 交叉的方向(0/1),丢弃了 dist=偏离度这个连续信号。`exposure = (1+dist×8)×I(dist>0), clamped [0,1.5]`——跌破MA空仓不变,站上MA后按 dist 强度缩放。三段验证(IS/OOS/压力)全部夏普+卡玛改善:Binary +28.4%/-14.9%/1.55 → Band +23.5%/-12.0%/1.60;压力期 DD 从 -31.4% 降到 -25.3%。WF 验证 MA 参数稳定区间 12-20,14/14年 OOS 正,Mode=14。**Band 是 Binary 的完整版——同一套 PureTrend 框架,只是不丢弃 dist 信息。** 当前 LIVE 主决策 (2026-06-07 切换)。

- **Band 收益方差 vs Binary(2026-06-07)**: **整体方差降 3.4%** (日) / **降 8.7%** (月), 7/9 年优于 Binary。但存在**"反常信号"**——正收益方差 +6%、负收益方差 +3%、峰度 +12.13 (Binary +7.52)。通俗解释:
  - Binary = 定速巡航: 60%时间固定 1.25x, 涨跌都等比例放大, 方差均匀分布
  - Band = 自适应油门: 90%时间温和暴露 0.3-0.8x (压缩波动), 10%时间火力全开 1.5x (放大两端)
  - **日常段**: Band 把随机噪声压小了 → 整体方差降
  - **极端段**: Band 1.5x > Binary 1.25x → 正/负收益方差都变大 → 峰度更高
  - **是好事**: 因为踩油门不是随机的——dist 大 = 趋势强 = 理应该更激进。Band 把方差从"随机波动"重新分配到"趋势信号强度区", 好的方差 (正收益 +6%) > 坏的方差 (负收益 +3%)
  - 类比: 路宽直踩到 90 码, 路窄弯多降到 30 码。大部分时间比 Binary 慢, 偶尔飙车时比 Binary 快得多
- **v2.2 PureTrend tw=2 偷看 bug(2026-06-06)**:`exposure = (mkt.rolling(2).sum() >= 0).astype(float)` **没有 `shift(1)`**——T 日仓位用到了 T 日 mkt 收益(含当天 close),经典未来函数。修复后 50.5%→**2.2%**,17年仅赢2年,PureTrend tw=2 无真正择时能力。教训:**任何涉及当日行情数据的择时信号必须验证 shift(1) 到位;修复后必须重跑全部数字再注册,不能用旧数字凑**。
- **成本别乐观**:佣金/融资是可谈硬费率(万0.65 / 5%),但**冲击滑点 0.2% 维持审慎**;往返 ≈0.47%。`evolve` 默认 0.15% 偏乐观、漏过户费。
- **真实成本杀伤很大**:small-cap-size 去幸存者偏差后 2018-2026 约 31.9%/-11.9%,但接入真实买卖成本+融资后降到约 **21.2%/-16.2%**;年均换手约 32x,成本拖累约 11%/年。阶段 1 必须把换手/成本作为目标,不能只优化收益。
- **T+1 开盘执行让小盘策略年化腰斩**(2026-06,`paper_replay` 历史重放实测):用真实盘口径(T+1 不复权开盘成交)重放 2024-2025,真实盘 **23.7%/-11.4%/夏普1.29** vs 回测收盘撮合 **45.1%/-10.9%/1.97**(两者都已含真实买卖成本)——**差距 21.4% 年化纯来自"信号日收盘选中 → 次日开盘买"的隔夜跳空**。小盘动量因子选的是近期强势/低成交额股,T+1 开盘往往高开,高换手(485 日 1561 笔)累积成巨大执行摩擦;受阻仅 3 笔(停牌/涨跌停),说明摩擦主体是**隔夜跳空非流动性**。教训:**这类高换手小盘策略的回测收益严重依赖"收盘成交"理想假设,真实 T+1 执行吃掉一半;回测数字必须配 T+1 真实盘重放才知道真实预期**。**全区间 2018-2026 真实盘 17.5%/-16.1%/夏普1.19 vs 回测 24.0%/-20.0%/1.41**——常态摩擦仅 6.5%(2024-2025 腰斩是小盘大年极端动量,非常态),且真实盘回撤反而更小(T+1 慢一拍平滑了部分极端点)。**结论:v2.0 真实盘 T+1 年化未达满意线 20%(仅 17.5%),但夏普 1.19、回撤 -16.1% 达标——合格但不惊艳的真实策略**。`scripts/research/paper_replay.py` 作可复用资产。
- **极端行情不可重复**:2025 +112%、2015 小盘疯牛是极端行情;回测含这些区间的高收益要单独核查、**不可外推**。
- **岛屿搜索的瓶颈在审计闸**:NSGA-II 单代评估还能接受,但 `review_shortlist` 每个候选要跑 2018/2023/2010 + 成本上浮,多岛长跑会慢。正确姿势是先让 `review_candidate` 尽量窄,只审计有希望的候选;不能为了速度跳过压力测试和成本敏感性。
- **孵化池不是入册池**:扩展流动性冷却/低 beta/趋势稳定后,非小盘弱候选能进入 `incubation_pool`;但只要 `registry_precheck=false`,就只能做降频/降杠杆/组合贡献研究,不能当有效母策略。
- **fundamental 接入边界**:`fundamental_batch.parquet` 已有 `avail_date`,可直接按公告可用日 ffill 到交易日;估值收益率类因子必须用 `price/daily_raw` 不复权价。当前批量表没有 `debt_ratio`,两融目录也未稳定落表,暂不纳入 1.9 第一批正交因子。
- **原始 fundamental 不够强**:1.10 三岛长跑 `registry_precheck=0`,弱 alpha 主要来自 `fund_bp_value`,但收益不足、压力回撤偏大、与小盘 baseline 相关约 0.7-0.8。后续 fundamental 必须做行业相对、时间分位、财务改善和 regime 过滤,不能只扩大原始 ROE/BPS/EPS 搜索。
- **fundamental/defensive 的高回撤是因子层结构性病,择时救不了,定位组合分散件**(独立择时 full sweep 验证,2026-06):剥掉共享的 `small_cap_ma16` 后 fundamental 候选真低相关(~0.4),但 2018/压力期裸奔回撤 -27%~-74%。**配独立择时(全市场趋势/vol-target/回撤止损,13 基因 × 9 候选 = 117 组合)0 过三道闸**:择时能把相关压到 0.3-0.4,却救不了回撤——fundamental 回撤与全市场 regime 不同步(价值陷阱/暴雷常在大盘平静时发生),`mkt_dd_stop` 止损反而在底部割肉、把年化打负、回撤打更深。**结论:别再给 fundamental 配择时凑达标;它们定位组合分散件(低相关小权重混入,样本外降组合回撤+提夏普),归孵化池/组合层(阶段3)。找第 2 个母策略要换思路——找本身回撤就可控的正交 alpha,而非靠择时事后救。** `factory/timing.py`(13 个独立择时基因)作可复用资产保留。
- **两融资金面也不是第 2 母策略(2026-06)**:`data_lake/capital/margin_all.parquet` 已稳定落表 2010-03-31~2026-06-03、634万行;factory 加入 `margin_balance_chg*`/`margin_buy_ratio*`/`short_balance_*` 并按 T+1 可用防未来函数。干净 amount + 2010 预热验证:margin NSGA `review_corr<0.5` 下 review=0;include-all audit 22 个候选 `registry_precheck=0`;确定性 168 网格 `hit_single=0`,最佳约 10.3%/-31.4%/corr 0.76。结论:两融弱且仍高度贴 small-cap/市场状态,只能入孵化观察,不能作为独立母策略。
- **北向也没挖出第 2 母策略(2026-06)**:东财每日批量 `stock_hsgt_stock_statistics_em` 仍返回 `9701/None`;改用 `ak.stock_hsgt_individual_em` 单股完整历史 fallback,对近 120 日成交额 top1000 低并发拉取,成功 774 只、`northbound_all.parquet` 675,072 行,覆盖 2017-03-16~2024-08-16。按 T+1 可用接入持股占比/市值/持股变化/净买入强度因子。关键口径:北向数据止于 2024-08,验证必须切到 2018~2024-08,不能让回测 2025-2026 持有陈旧北向篮子。结果:345 个北向网格 `review=0/hit_single=0`,最佳仅 0.7%/-28.3%/corr0.57;低相关组合 corr~0.47 但负收益且大回撤;top30 audit `registry_precheck=0`。结论:当前价量+财务+两融+北向基础下,稳健母策略仍只有小盘。
- **行业字段不是全覆盖**:`fundamental_batch.parquet` 有 `industry`,但缺失约 34.5%。行业内排名/行业中性只能对有行业标签的股票生效;缺失行业不应强行填充为同一类,否则会制造伪行业暴露。
- **自进化必须先证伪**:孵化池自进化只能本地规则化变异 + 三段审计 + 成本上浮,不能让 LLM 直接“脑补”好策略。长跑程序不调用 OpenAI API;若出现 429,优先查 Codex/LLM 并发请求,不是本地回测进程。
- **定时更新要先过 stale gate**:`run_daily.py` 会在更新失败后继续用旧数据出信号,生产定时不能裸跑它。包装脚本必须先更新数据、重建/检查交易日历、确认最新价量达到应有交易日,再用 `run_daily.py --no-update` 生成信号。

## 策略研究方法论（纯趋势 HMM 对比实验，2026-06）
- **简单方案先跑**：HMM(200+行/夏普2.23) < `mkt_ret.rolling(2).sum()<0`(3行/夏普3.40)。研究开始前先建最简基线；复杂方案无法显著超越则放弃。A股散户主导+政策频繁，HMM"状态识别"本身是噪声，宏观特征已隐含在 mkt_ret 中。
- **Walk-Forward 是唯一可信验证**：全样本回测支持任何结论（HMM tw=3 全样本看起来 32.4% 年化"很好"）。WF 揭示真相：HMM tw=3 IS Sharpe 1.35~2.86（不稳），Pure Trend tw=2 IS Sharpe 4.25~4.96（极稳）。凡参数选择必须 WF；全样本只是起点。
- **A股压力信号天然窗口 = 2天**：WF 12年独立全选 tw=2（夏普3.40）。经济解释：散户恐慌阈值=两天连跌；1天太噪、3天太慢；匹配 T+1 结算节奏。这是市场结构告知的，非参数挖掘。
- **Overlay 视角必须与策略视角对齐**：小盘策略用等权 mkt_ret（胜率92%）不是成交额加权（胜率67%）。"最准确"的市场收益不是客观存在的，取决于你从谁的视角看。
- **成本敏感度=验证稳健性，不是验证盈亏**：好策略在成本 3x 时仍有相对优势（PT 优势 +15.8pp）。策略必须在 3~5x 成本假设下仍相对好才算稳健。
- **回测审计=发现策略边界**：不是安全清单。策略边界"≤1000万规模、成本≤1%、A股全市场"——知道何时失效比知道何时有效更有价值。

## 策略哲学: 不对称收益 (2026-06-07)

整套策略的底层逻辑不是"找更高的夏普比率"，而是**构建不对称收益结构**——让涨的时候涨得多，跌的时候跌得少。

### 不对称来源

| 组件 | 不对称机制 | 方向 |
|------|----------|------|
| illiquidity 因子 | 流动性风险补偿 + ST 彩票溢价 | 正收益端更厚 (ST 大涨 1.6% vs 大跌 0.9%) |
| PureTrend 择时 | 趋势跟踪天然截断左尾 | 砍掉极端下跌日 |
| Band 连续 exposure | dist 大时火力全开，dist 小时收缩 | 正收益方差 +6% vs 负收益 +3% |
| 不排除 ST | 保留彩票尾部 | 不丢 alpha 源 |

### 与传统多因子的区别

| | 传统多因子 | 我们 |
|--|----------|------|
| **目标** | 更高夏普比率 (对称优化) | 正偏收益分布 (不对称) |
| **假设** | 收益对称分布 | A 股收益结构性不对称 |
| **因子来源** | 统计上的 IC 显著 | 市场结构摩擦 (流动性/T+1/散户) |
| **风险控制** | 分散化降低波动 | 择时截断左尾 |
| **评估标准** | IC/ICIR 最大化 | 正收益端厚度 > 负收益端厚度 |

### 为什么 A 股适合不对称策略

- **散户主导**: 趋势持续性强 (追涨杀跌) → 右侧跟随有正偏
- **T+1 制度**: 隔夜信息不对称 → 持有者有溢价
- **壳资源**: ST 炒作逻辑 → 彩票式正向尾部
- **政策频繁**: 单边暴涨暴跌多 → 择时截断左尾的价值大

### 方法论含义

- 不要追求对称优化 (夏普最大化): 那是假设收益正态分布的陷阱
- 要看正/负收益方差的比值: Band 的 +6%/-3% = 2:1 是不对称的标志
- 截断左尾 > 放大右尾: PureTrend 砍掉极端下跌比任何 alpha 因子都重要
- 保留彩票尾部: 排除 ST 表面降低风险，实际砍掉了不对称收益源

## 组合管理 / 边际贡献
- **"信息→行动"断层是最贵的成本**(2026-06-07):STATUS.md 早写"4 策略组合 Sharpe 1.33 < 单 illiq 1.35"——**已知组合层负贡献,但 LIVE 集合没动一周以上**。这是 plan/工程之外的真问题:**有诊断没行动**。本质是组合管理纪律,不是技术问题。修复 = 把"边际贡献负"作为硬触发,立即 SHADOW(不删除,但停止吸纳)。教训:**只产新工程不剪冗余 = 假装在工作**。
- **2 ACTIVE > 4 LIVE 等权 (+18% Sharpe)**(2026-06-07 全样本 2018-2026 实测):
  - 当前 4 LIVE 等权 22.1% / Sharpe 1.60 / mdd -13.9% / calmar 1.60
  - 剔除 size-low-vol+size-earnings(边际-0.120/-0.277): **29.8% / 1.88 / -15.8% / 1.89**
  - 同 + risk_parity 加权: **29.3% / 1.89 / -13.7% / 2.14**(calmar 最高)
  - 边际正只 small-cap v2.0 (+0.104),其余两个全负
  - 决策:**size-low-vol v1.0/v1.1、size-earnings v1.0 全部转 SHADOW**;组合层用 risk_parity(illiq + small-cap)
  - 教训:**Portfolio Sharpe 不靠加策略提升,靠剪冗余**。多元化 ≠ 多策略,A 股权益内只是同因子换包装。
- **plan 自家流水线诚实揭示问题**(2026-06-07,工厂 L3 + marginal 双门验证):工厂 55 hypothesis 跑 L0/L1/L2/L3/marginal,**仅 7 个 small_cap 变体过 L3 + marginal LIVE_C 双门**——全是同因子,corr 0.85+。"防御档"(LIVE_D)候选 ret_zscore_cross/mom_n 被 L3 卡线刷下(avg yearly sharpe 0.49/0.50)。**实证了 STATUS.md 结论 #1 "A 股 alpha 单维度"——工厂自家流水线给出独立证据**。教训:不要拒绝自己流水线说"难"的话——这是质量保护,不是 bug。

## 连续 timing / Band
- **Band timing — 连续信号是 binary 的科学性升级**(2026-06-07):
  - 公式: `exposure = clip(1 + dist × 8, 0, 1.5) × I(dist > 0)`,**用 leverage 1.0 + timing[0,1.5]** 代替 Binary 的 leverage 1.25 + timing{0,1}
  - 本质: 把固定杠杆换成 **dist 驱动的动态杠杆**——趋势确认强时加杠杆,趋势弱时减仓,dist≤0 时空仓
  - 理论根据: Moskowitz-Ooi-Pedersen 2012 *Time-Series Momentum* 实证一致 (momentum-scaled position sizing)
  - 三段实测 (illiquidity v1.0 因子,2018-22 IS / 2023-26 OOS / 2010-17 Stress):
    - IS: Binary 28.4%/-14.9%/1.55 → **Band 23.5%/-12.0%/1.60** (sh +0.05, dd -2.9pp)
    - OOS: Binary 39.9%/-13.5%/2.23 → **Band 32.7%/-10.8%/2.29** (sh +0.06, dd -2.7pp)
    - Stress: Binary 30.5%/-31.4%/1.23 → **Band 25.2%/-25.3%/1.27** (sh +0.04, dd -6.1pp)
  - 价值不在 Sharpe (+0.05 微改) 而在 **Calmar +13% + 极端尾部保护**
  - 组合层 (illiq+small-cap risk_parity): Binary 29.3%/-13.7%/1.89/cal2.14 → Band 28.5%/-11.8%/1.86/**cal2.42**
  - 决策: **SHADOW 跟踪 (2026-06-07 起)**,signals/ 含 shadow_band_exposure 字段;30 日后 `scripts/research/band_shadow_review.py --update` 看真实 paper 差异决定是否切 LIVE
- **engine clip 陷阱**(2026-06-07):BacktestEngine `_run_weight_backtest` 原把 timing 强制 `min(max(x, 0.0), 1.0)`,boost timing > 1.0 全被吞——结果与 binary 完全相同。已加 `Signal.exposure_cap` 字段 (默认 1.0,Band 传 1.5)。教训: 引擎假设是隐藏约束,任何 timing > 1.0 设计**必须先验证 engine 不 clip**。
- **复现 timing 必须先核对 leverage**(2026-06-07):用户给 Band 公式描述时未明说 leverage 改成了 1.0,我用 1.25 跑出加杠杆型 (sharpe ↓),与用户报告的减仓型 (sharpe ↑) 方向相反——浪费了 2 小时尝试各种 mapping 直到看 `scripts/research/band_timing_test.py` 才发现 `lev=1.0`。教训: **timing + leverage 不可分离讨论**,公式描述必须含 leverage。

## 自动化质疑机制 (2026-06-07 Band 反思)

### 为什么 6 周工厂跑不出 Band,但人 30 分钟想出来

**5 层失败模式** (按隐蔽性排序):
1. **API 误导**: `small_cap_timing` 返回 `(timing, small_nav, dist)`,所有调用方 `_, _, dist = ...` 丢弃 dist。**输出位置传递重要性暗示**——dist 作为"输出 #3"被默认忽略。
2. **底层约束塑造思维**: `core/engine.py` 硬编码 `exposure = min(max(exp, 0.0), 1.0)`,boost > 1.0 全被吞——6 周里没人想过"为什么是 [0,1]"。**底层约束的隐性传播**: 工具假设某维度是常量时,那个维度永远不会被发现。
3. **搜索空间预设**: 工厂 mutate_existing.py `timing_kind ∈ {"none", "small_cap_ma16", "small_cap_ma8"}` 三选一离散。**工厂结构性地"看不见" timing 是连续变量**。
4. **强结论封顶**: "PT 通用最优,无例外" → "已解决"标签 → 关闭探索。**已解决的问题是探索的坟墓**。
5. **mental model 解耦**: leverage 在 config / timing 在 signal,binary 思维下天然分离。Band 揭示 **timing 可以同时编码 exposure 和 dynamic leverage**——一旦突破 0/1,timing 吃掉了 leverage 功能。**变量边界的"自然分类"未必是最优分类**。

**meta-lesson**: 6 周扩展工厂(加 L3 / 加 regime / 加 LIVE_D),**没花 30 分钟质疑工厂的搜索空间假设**。"扩展工具"是默认动作,"质疑工具假设"是被忽略的动作。

### 5 个自动化质疑模块设计

**Line 0 (MetaSearch)** = 在 Line 1-3 之前,质疑预设搜索空间本身。`factor_research/metasearch/` 已建。

1. **Signal Flow Tracer** (Phase 1 ✅ PoC 已跑通,定位 Band 根因)
   - AST 扫描 `a, _, b = some_call(...)` 模式
   - 自动报告"被丢弃 ≥50% 的输出"
   - 已发现: `small_cap_timing` output[2] (dist) 88% 被丢,output[1] (small_nav) 100% 被丢——**第二个 Band 候选已自动浮出**
   - `python3 -m metasearch.signal_flow_tracer` 一行命令
   - 也发现 spearmanr p-value 100% 被丢 (21 处),应该按显著性过滤 IC

2. **Constant Auditor** (Phase 2,1 周)
   - AST 找所有硬编码常量 + `.clip(low, high)` 上下界
   - 列表 "硬约束清单",每月人审
   - 如发现 engine 的 `exposure_cap=1.0`、`leverage=1.25 scalar`、`top_n=25 hardcoded` 等
   - 防止下一个"timing ∈ [0,1] 6 周没人质疑"

3. **Continuization Auto-Sweep** (Phase 3,2 周)
   - 给定 Binary 信号 `x > threshold`,自动生成 5-6 个连续版本 (linear/sigmoid/cap)
   - 每个跑 walk-forward 自动比较
   - **如果 Band 这个工具一年前存在,5 分钟就能找到**
   - 输入: 任何 `(bool, optional_continuous)` 信号

4. **Conclusion Expiry** (Phase 4,1 周)
   - LESSONS.md 强结论加 frontmatter: `expires: 3-months`
   - 每月自动跑 adversarial 实验试图证伪
   - 防止"PT 通用最优"封顶持续阻断探索

5. **Variable Coupling Detector** (Phase 5,3 周)
   - Dataflow analysis BacktestEngine
   - 找"独立但耦合"的变量对 (如 timing × leverage 出现在同一处乘积)
   - 建议合并实验
   - 发现下一个"timing 和 leverage 可合并"机会

### 工厂 vs 人的本质分工

| | 工厂(机器) | 人 | MetaSearch (新) |
|---|---|---|---|
| 擅长 | **广度搜索** — 预设空间内枚举 | **深度复用** — 重理解已有变量 | **质疑预设** — 找搜索空间外缺口 |
| Band 案例 | 6 周 55 hyp 0 实用 | 30 分钟想出 | 1 秒 PoC 定位根因 + 提示候选 |

**Phase 2 应有 1 周/月预算用于 MetaSearch,不只是扩展 Line 1 generators**。

### 信息熵框架 — small_nav 失败暴露的更深定理 (2026-06-07)

small_nav 5 实验全失败,本质是数学定理:**dist 是 small_nav 对 timing 决策的充分统计量,条件互信息 ≈ 0**。这把整个 plan 从"经验工程"提升到"信息论框架":

**框架核心 (4 LIVE 实测 MI 矩阵确认):**
- 4 策略两两 MI 1.5-1.8 bits (上限 3 bits, 共享 50%+) — 信息论独立给出与 corr 0.83 相同诊断
- 顺序 cond_mi: small-cap 1.57 → size-low-vol 0.15 → size-earnings 0.27 — 与 marginal_sharpe +0.10/-0.12/-0.28 **完美同向衰减**
- **A 股 alpha 的"独立信息预算"有限**: 受市场 beta + 行业 beta 上限约束。工厂努力多 ≠ 挤更多独立信息;要找尚未被利用的数据源 (基本面/资金流/行业/港股)

**MI auditor 的关键边界 (Band 案例暴露):**
- Band vs Binary: MI 完全相同 (2.77 bit), cond_mi=0 → REDUNDANT
- 但实测 Band Calmar +13% 真实价值
- 原因: **MI 测"两变量依赖", 不测"如何用同一份信息"**。Binary 和 Band 派生自同一 dist, 信息内容相同但与 PnL 的**函数关系不同**

**框架定位修正 — MI 是必要不充分:**
- 低 MI → 必然 REDUNDANT (放心关闭)
- 高 MI → 不保证 VALUABLE (还需测方向 + 用法)
- MetaSearch 是双层:
  - Lower (MI): 信息含量,毫秒级,过滤冗余
  - Upper (Sharpe): 信息使用,回测级,测方向

**这就是 plan 的 L−1 关 (在 L0 IC scan 之前)**: 工厂前端最便宜的过滤器。`factor_research/metasearch/mi_auditor.py` 已实现,等待集成到 L0 之前。

### Information Map 框架的关键盲点 — IC MI ≠ Returns MI (2026-06-07)

加 4 个 fundamental factor (NPY/revenue_yoy/ROE/gross_margin) 跑端到端,验证 Information Map 的预测:

**Information Map 预测 (IC 时序 MI):**
  · 4 fundamental 与 LIVE 距离 2.86-2.97 (近上限 ~3.0)
  · PNG 显示 fundamental 在完全独立的信息维度
  · 预测: 真正多元化候选

**实测 marginal eval (Returns):**
  · 4 fundamental returns vs LIVE corr **0.76-0.80** (远超 0.42 物理下限)
  · 全部 SHELVE,bear_imp 全部负值 (-4.8 ~ -13.8%)
  · marginal_sharpe -0.09 ~ -0.17

**根本原因 — 两个 MI 层次不同:**
  · IC MI 测"信号生成时机依赖" → fundamental 真独立 (不同时段不同预测方向)
  · Returns MI / corr 测"执行结果共动" → fundamental 与 LIVE 都是 long-only,**都吃市场 beta + 选股 overlap (NPY 好的也偏小盘) → returns 必然高度共动**

**plan 修正:**
  · 现 MetaSearch MI auditor 用 IC 时序作 proxy,与最终决策 (marginal_sharpe on returns) 不同口径
  · 必须建 **Returns MI auditor** (用 daily returns 而非 IC 时序),与 marginal_sharpe 同口径
  · 两层独立: IC MI 高 → 信号同源(关闭重复); Returns MI 高 → 组合冗余(真实拖累)
  · IC MI 低 **不保证** Returns MI 低 (fundamental 案例就是反例)

**A 股 long-only 框架的物理上限再次确认:**
  · LIVE 2 ACTIVE (illiquidity + small-cap) 已基本耗尽 long-only alpha
  · 任何 long-only fundamental 加入 → returns 大部分重叠
  · 真突破必须: (a) long-short 引擎去 beta,或 (b) 跨资产 (港股/债/商品),或 (c) 接受 2 ACTIVE 已是当前框架最优
  · 印证 STATUS 结论 #3 "真正多元化需跨资产"

**MetaSearch 框架价值:**
  · 1 天验证 fundamental 在 long-only 框架下无独立组合价值 (节省未来周/月反复尝试)
  · 暴露 MI 框架盲点 (IC vs Returns 分层) 并即时修正
  · 关闭分支 ≠ 失败,是 plan 设计本身的迭代

### A 股 long-only 多因子的真实 corr 上限 = 0.75-0.80 (2026-06-07)

之前 LESSONS 写"A 股长仓多因子 corr 物理下限 ~0.42",但 0.42 是个例 (微观结构 vol_breakout/mom_n 类)。完整数据资产盘点 + 大量实测后,**真实分布是 0.75-0.80**:

**实测 corr to A 股 ACTIVE (illiquidity + small-cap):**
- bp_proxy (经典价值): 0.77 (期望 contrarian 但实际持仓仍偏小盘)
- ep_proxy: ~0.77
- roe (质量): 0.77
- gross_margin: 0.76
- net_profit_yoy (成长): 0.80
- vol_breakout/mom_n (微观结构): 0.42-0.58 (个例,corr 真低)
- **HK 港股 (跨市场): 0.25-0.27** (唯一突破 0.5)

**根本原因 — A 股流动性结构强制 long-only 持仓收敛:**
- top-N 持仓必然偏小盘 (大盘股 1/top_n 权重太大,等权 long-only 在 A 股 universe 自然偏小)
- 价值股 (高 BP) 在 A 股不是大盘蓝筹,主要是次新/中小盘
- 成长股 (高 NPY/ROE) 也多小盘
- OHLC 派生信号 (close_position/high_low_breakout 等) 选趋势股,也多小盘
- → 所有 long-only 多因子的实际持仓都收敛到"小盘 + 流动性"维度

**对 plan 的影响:**
- 现 LIVE 2 ACTIVE (illiq + small-cap) Calmar 2.14 已是 A 股 long-only 框架几乎最优
- 任何 long-only fundamental / value / quality / OHLC 候选 corr 都 0.75+,组合贡献负
- 真正突破必须: (a) Long-short 引擎去 beta (corr 物理可到 0.2-0.4), 或 (b) 跨资产 (HK 已验证 corr 0.26 但单 Sharpe 弱需更好因子), 或 (c) 接受现状
- 现 MI Auditor 用 IC 时序 → 与最终 Returns 共动差异巨大,**信号空间独立 ≠ 持仓空间独立**,必须建 Returns MI 第二层

**完整数据资产清单 (已盘点 2026-06-07):**
- price/daily (close, volume 已用) + daily_raw OHLC (raw_open/high/low 之前没用,新增 close_position/high_low_breakout/amplitude_mean factor)
- fundamental_batch 16 字段 (今天已用 NPY/ROE/revenue_yoy/gross_margin/BP/EP/cfo,9/16 字段)
- capital/margin_all (2010-2026 全) — LESSONS 标弱,Returns 视角可重测
- capital/northbound_all (2017-2024-08 截止) — 浅尝
- price/hk_daily (111 只 × 8 年) — **HK 港股完全没用,corr 0.25 真低**,需更好 HK 因子工程
- price/monthly, weekly — 不知用没用

### 验证纪律 — 任何"建议使用"前必须 OOS 三关 (2026-06-08 永久记忆)

**触发条件:** 任何策略/配置/参数被推荐入 LIVE/SHADOW/生产前 (含"切换默认", "推荐配置", "新组合").

**必须三关 (in-sample 漂亮 ≠ 可投资):**
1. **Walk-Forward 参数稳健性** — 在搜索网格上做 WF, 看选出的参数 OOS 是否仍是最优, 或邻近参数 OOS 表现是否一致 (plateau ≠ spike).
2. **分段稳定性** — 按年/regime 切分独立测, 看哪些时段亏哪些时段赚, 是否依赖单一极端年.
3. **极端事件检查** — 在已知 stress 期 (2008/2015/2018/2022 等 A 股大跌) 看策略真实表现, 不能只看全样本平滑曲线.

**反例 (今天踩的坑):**
- 2026-06-07 推荐 ETF 配置 35/35/15/15, grid search 在全样本上选的最优
- 国债 MA60 是先验选的, 没在 ETF universe 做 WF
- 未分段验证 → 不知道是否依赖某些特殊年份
- 用户即时拦住要求验证 → 才发现可能 in-sample 调优

**反例 (历史):**
- v1.0 夏普 2.06 (含幸存者偏差水分)
- v2.2 PureTrend tw=2 IS Sharpe 4.25-4.96, shift(1) 修复后 2.2%
- MA16 grid 测试 plateau 不是 spike (这是正面例子 — 做了所以稳健)

**强制流程 (任何 SHADOW/LIVE 推荐前):**
```
1. 报告 in-sample 结果
2. 主动声明: "未经 OOS 三关验证, 直接切 LIVE 是冒险"
3. 给出三关验证 plan
4. 三关全过才能 SHADOW; SHADOW 30 日不出问题才 LIVE
```

**例外:** 仅当用户明确说"先 SHADOW 跟踪, 不切 LIVE", 且 SHADOW 期内会持续累计真实数据 — 才可跳过 walk-forward (因为 SHADOW 期本身就是 OOS 验证).

### 执行优化 — fill_mode 切换 close 实证 Sharpe +0.18 / ann +5.3pp (2026-06-07 Task 1.2)

LESSONS 早已写过 "T+1 开盘执行让 2024-2025 年化 45.1%→23.7%, 差 21.4pp"。Task 1.2 audit 实证:

**5 fill mode 对照 (2024-2025 重放, simplified no-cost baseline):**
- open (旧默认):     ann 40.3%, sh 2.29  (baseline)
- ohlc_mid (10:30):   ann 42.9%, sh 2.42  Δsh +0.13
- vwap_4:             ann 42.8%, sh 2.41  Δsh +0.12
- **close (14:55):**  **ann 45.6%, sh 2.47  Δsh +0.18** ⭐ 最佳
- lo_close_mid:       ann 41.6%, sh 2.25  Δsh -0.04

**根本原因:**
- 隔夜跳空诊断: 9% 显著高开 (>+1%), 95 pctile +1.6%
- open 模式在高开股上吃满隔夜冲击 → 持仓成本虚高
- close 模式等冲击消化, 实际成交价低 1-2pp

**决定: paper_trade.py 默认 FILL_PRICE_MODE = 'close'** (line 38-44)
- 环境变量覆盖: `PAPER_FILL_MODE=open` 回滚
- get_fill_price() 支持 4 mode (open/close/ohlc_mid/vwap_4)
- 涨跌停约束仍按开盘价判 (即使 close mode, 开盘涨停依然买不进)

**生产预期 (含真实成本 + 涨跌停):**
- 相对 Δ 改善 +5.3pp ann 可信; 绝对值依赖 paper_trade 真实环境
- audit baseline 40.3% vs paper_replay 真实 23.7%, 差 ~16pp = 成本 + 约束
- 切 close 真实生产期望: 23.7% → 28-30% ann (回收摩擦的 25-35%)

**与 6 大盲区路线的关系:**
- #2 [执行优化] PoC 完成 → 推荐切换已落地
- 后续若要更精确, 拉 5min K 线做 09:30/10:00/10:30 etc 精细对照
- 但 OHLC 推断已经给出明确方向, **节省 5min K 线工程约 1 周** (Task 1.2 plan 预期效果)

`scripts/research/execution_optimization_audit.py` 作可复用资产 (修改 fill_fn 即可加更多 mode).

### 多元化的数学下限 — 候选 Sharpe / 组合 Sharpe 比例 (2026-06-07)

HK 因子工程 (6 因子 × 5 config × 多 timing) 实测后发现:

**HK 最佳候选**:
  · mom252+illiq + notiming: sh 0.53, corr 0.18 to A 股 LIVE
  · all4_equal (mom+illiq+lowvol+size): sh 0.51, mdd -41% (最低), corr 0.24

**加入组合实测全部拖累**:
  · A only risk_parity: sh 1.89, cal 2.14
  · + HK_all4 (sh 0.51, corr 0.24): sh 1.54 (-0.35) ❌
  · + HK_mom252_illiq (sh 0.53, corr **0.18**): sh 1.55 (-0.33) ❌
  · **即使 corr 0.18 极低也救不了!**

**根本原因 — 数学约束:**
  · Sharpe = mean / vol
  · 加入 HK → portfolio mean 必降 (HK ann 12-19% vs A 股 30%+)
  · HK vol 高,即使 corr 低,也不显著降 portfolio vol
  · 分子降幅 > 分母降幅 → Sharpe 净降

**经验法则 (写进 plan):**
  · **candidate Sharpe / portfolio Sharpe < 50% → 必拖累 (即使 corr=0)**
  · 当前 portfolio sh 1.89,要不拖累 HK 必须 sh ≥ 0.95
  · HK long-only 单 sh 上限 ~0.5 (universe 91 只 + 港股流动性 + 机构主导长趋势)
  · 数学不可能在 long-only 框架下用 HK 改善 A 股组合

**真正可行的 cross-market 路径:**
  · (a) Long-short HK → 去 beta, vol 降一半,Sharpe 可能翻倍
  · (b) HK ETF rotation (行业/风格,不选股) → 降 vol
  · (c) 港股通跨市场统计套利 → 真 market-neutral
  · 这些都需要新引擎/数据,plan 之前没有

**结论修正 (A 股 long-only 物理上限的精确表述):**
  · 不只是"corr 0.75-0.80",还有数学约束
  · 任何 candidate Sharpe < 当前组合 Sharpe × 0.5 → 必拖累
  · 当前 A 股组合 sh 1.89 → 任何新候选必须 sh ≥ 0.95 才有意义
  · A 股 long-only 多因子的单 sh 也很难持续 ≥ 0.95 (已知最强 illiq v1.0 sh 1.78)

`scripts/research/hk_factor_grid.py` + `scripts/research/hk_v2_independent_timing.py` 作可复用资产。

### small_nav 已审计 — 无独立价值 (2026-06-07)

MetaSearch PoC 提示 `small_cap_timing` output[1] `small_nav` 100% 被丢。1-2 小时跑 5 实验:
  - V1 rolling 252d drawdown gate
  - V2 slope-driven boost (代替 dist boost)
  - V3 small_nav / mkt_nav 相对强度 gate
  - V4 adaptive exposure_cap (NAV 滚动 vol 控制)
  - V5 Binary × NAV vol-target 30%

**全部失败** (全段 Sharpe 不改善或下降)。V2 slope boost 全段 -0.4 sharpe 是最强证据: A 股小盘的 timing 信号在"相对均线位置 (dist)"层,不在"短期变化率 (slope)"层。

**结论: dist 已充分提取 small_nav 的全部时序信息,nav 自身/派生信号都被 dist 包含或对偶**。`scripts/research/small_nav_experiments.py` 作可复用资产。

**这是 MetaSearch 路径的价值证明 —— 不仅找到 Band 类升级,也 1-2 小时快速证伪 small_nav 类幻觉,关闭分支**。未来再有人想挖 small_nav,LESSONS 直接告诉他"已审计无价值"。

### 实证: PoC 输出 (2026-06-07)

```
HIGH PRIORITY — 默认被忽略的输出
  callee                       #calls  output[i]   discard%
  small_cap_timing                 40    1/2         100%   ← small_nav 全丢
  small_cap_timing                 40    2/2          88%   ← dist (Band 来源!)
  spearmanr                        21    1/1         100%   ← p-value 全丢
  load_price_panels                 9    1/2          89%   ← volume? 全丢
  backtest_weights                 72    1/1         100%   ← detail 全丢
```

下一步: 逐个审 small_nav / spearmanr p-value / backtest detail 能不能成下个 Band。

## 科学性 / 参数 robustness
- **MA16 是 plateau 不是 spike**(2026-06-07 grid 测试 2010-2026):
  - MA10-20 sharpe 1.26-1.45 都 work(plateau)
  - MA16 sharpe 1.45 是 grid winner,但 MA18 1.42 几乎等效且 calmar +0.92>0.89、mdd -29.1%<-30.5%
  - 极端 MA5 sh 0.81 / MA60 sh 0.96 → 趋势跟踪概念真实(中间区段都 work)
  - 但"16"无理论意义,是事后合理化(3 周 ≈ MA15-18 都行)
  - 教训:**概念有理论根据(time-series momentum) + 参数 plateau ≠ magic number**。MA16 不是 v2.2 tw=2 那样的偷看 bug,只是轻度 in-sample tuning。严肃科学应 walk-forward 选 MA window。

## 因子评价框架: 截面 vs 时序 + 多周期 IC (2026-06-07)

专家审视触发: 量化交易的关键不在具体因子，而在科学的因子评价体系——将定性理解转化为定量约束函数。

### 多周期 IC 闸门实验

**假设**: 工厂 L0 只用 1d forward return ICIR 筛因子。但 A 股价格发现慢，所有因子 IC 从 1d→20d 单调递增 (增幅 76%-156%)。L0 在信号最弱的周期上设门槛，可能误杀中周期因子。

**实验**: 从 `FACTOR_MUTATION_SPECS` 生成 74 个候选因子，双闸门评分:
- 旧闸门: |ICIR_1d| > 0.03
- 新闸门: 0.1×ICIR_1d + 0.2×ICIR_5d + 0.3×ICIR_10d + 0.4×ICIR_20d > 中位数

**结果**: **0 个误杀**。旧闸门通过率 99% (73/74)，几乎是个 no-op——阈值 0.03 太宽松。

**深层发现**:
- 旧闸门 L1 精度 22%，新闸门 19% — 两者都不高
- IC Score 和真实 L1 收益 **不相关甚至反向**: vol_breakout Score 最高 (0.56) 但 L1 -6.3%；illiquidity Score 中等 (0.40-0.48) 但 L1 +21-23%
- **IC 是必要条件，不是充分条件。** IC 能去掉明显噪音，但区分不了"真 alpha"和"会死的假 alpha"

**结论**: 多周期 IC 无增量——不是闸门周期的问题，是 IC 本身信息量有限。当前 L0→L1→L2→L3 串联设计合理: IC 粗筛，后续层精筛。真正改进方向: 提高旧闸门阈值 (从 0.03)，而非加周期维度。

`scripts/research/experiment_multi_period_ic.py` + `scripts/research/factor_eval_framework.py` 作可复用资产。

### 时序预测 vs 截面预测

**假设**: 截面 IC 测"这只股票比别的股票好吗"，时序 IC 测"这只股票比它自己过去好吗"。两者是不同信息维度，时序信号可用于仓位管理。

**实验**: 对 illiquidity 因子，在截面 top-25 基础上加入时序仓位缩放——每只股票的 illiquidity 相对自身 252 天历史的 zscore。测试正向 (选时序上升) 和反向 (选时序下降 = 流动性恢复)。

**时序 IC 基线** (20 只抽样):
- 1d forward: 均值 +0.024, 仅 10% 股票显著
- 20d forward: 均值 **+0.101**, **75%** 股票显著 — 时序信号在中周期确实有效

**回测结果**:
| 场景 | 年化 | 回撤 | 夏普 | 换手 |
|------|------|------|------|------|
| 等权 (基线) | +20.8% | -21.8% | 1.23 | 36.5x |
| 时序缩放 (正向) | +19.4% | -22.1% | 1.13 | 38.2x |
| 时序缩放 (反向) | +20.5% | -21.8% | 1.21 | 37.4x |
| 时序筛选 (正向) | +13.6% | -21.1% | 0.70 | 42.0x |
| 时序筛选 (反向) | +21.3% | **-18.5%** | 1.21 | 43.4x |

**核心发现**:
- 方向是对的: 反向 (选流动性恢复) > 等权 > 正向 (选流动性恶化)
- 但效果太小: 反向筛选仅 +0.5pp 年化、换手 +19%，不显著
- B2 缩放版本几乎和等权一样 — 时序信号只在激进筛选时有效，不是稳定的线性信号
- **截面 illiquidity 完成了 95% 的工作，时序微调只贡献边缘噪音**

**方法论教训**:
- 时序和截面是两个不同的预测视角，逻辑必须对齐
- 对 illiquidity，"截面高 = 选它"是对的；但"时序升高 = 它在恶化"有害、"时序下降 = 它在恢复"有益
- 时序信号的方向不能假设，必须和截面信号的逻辑一致
- 当前不值得将时序仓位加入系统——复杂度提升 > 收益改善

`scripts/research/experiment_ts_weighting.py` 作可复用资产。

### top_n 参数是 plateau 不是 spike (2026-06-07)

**实验**: Band timing 下跑 top_n = 10/15/20/25/30/40/50/60/80/100/120, 2018-2026 全区间 + 三段分区间验证。

**全区间结果**: 20-25 区间几乎等效:
| top_n | 年化 | 回撤 | 夏普 | 卡玛 |
|------:|------|------|------|------|
| 20 | +25.3% | -18.0% | 1.49 | 1.41 |
| 25 | +25.0% | -17.7% | 1.50 | 1.41 |

**分段验证**: 20 的微弱优势 (+0.3pp) 几乎全部来自 2024-2026 段，前两个子段 25 反而更好。20 和 25 在子段间互有胜负，差异不显著。

**结论**: **top_n=25 不变。** 20-25 是 plateau，不是 spike。和 MA 参数一样，区间内几乎等效，不值得为 0.3pp 噪声改参数。更集中 (10-15) 回撤大、更分散 (50+) 稀释 alpha。25 容量优于 20 (多 25%)。

`scripts/research/top_n_sensitivity.py` 作可复用资产。

### ST 股暴露 — 反直觉：ST 不拖累反而略好 (2026-06-07)

**发现**: illiquidity 因子选的 top-25 中，ST 股占比高达 **28.7%**。因子天然选中成交额极低的股票，和 ST 高度重叠。

**实证对比** (2018-2026, 调仓日次日收益):
| | ST 持仓 | 非 ST 持仓 |
|--|:--:|:--:|
| 占比 | 28.7% | 71.3% |
| 平均日收益 | **+0.13%** | +0.12% |
| 中位数日收益 | 0.00% | 0.00% |
| 波动率 | 2.15% | 1.85% |
| 跌停率 (≤-5%) | 0.9% | 0.8% |
| 大涨率 (≥+5%) | 1.6% | 1.3% |

**为什么 ST 没有拖累**:
- ST 已被市场定价，信息是公开的
- A 股 ST 存在投机溢价: 壳资源炒作 + 散户博重组反转 → 彩票式正向尾部
- ST 退市股票在回测中被自然剔除 (次日不交易 → 调仓排除)

**决策: 不主动排除 ST。** 排除 ST = 对抗因子自身的信号，会损失 ST 彩票溢价带来的 alpha。ST 暴露是因子逻辑的结果，不是 bug。但在真实盘需注意停牌期间无法卖出的执行风险 (回测无法完全捕捉)。

### *ST 过滤实为有害 (2026-06-07)

**问题**: ST 暴露 28.7%，如果某只持仓被 *ST (退市风险警示) 后连续跌停卖不掉怎么办?

**实验**: 三场景对比 — 无过滤 vs 仅排除 *ST vs 排除全部 ST。*ST 识别通过 `codes.name` 前缀判断 (`*ST` 开头 = 退市风险，`ST` 开头非 `*ST` = 其他风险)。

**结果**:
| 场景 | 年化 | 回撤 | 夏普 | 终值 |
|------|------|------|------|------|
| 无过滤 | **+20.6%** | -20.0% | **1.23** | **484万** |
| 排除 *ST | +18.3% | -19.1% | 1.06 | 403万 |
| 排除全部 ST | +19.3% | -19.9% | 1.11 | 435万 |

排除 *ST: 年化 -2.2pp，回撤仅改善 0.9pp — **用 2.2% 年化换 0.9% 回撤改善，血亏。**

**为什么**: *ST 股是 illiquidity 最极端的股票，天然占据因子排序顶端。排除 *ST = 砍掉最强 alpha 信号源。因子通过更高的收益补偿了退市风险 (ST 彩票溢价包含了退市风险定价)，排除就丢掉了这部分补偿。

**结论: 不加 *ST 过滤。** 因子自身已定价退市风险。单只 4% 仓位 + A 股退市整理期 (15 交易日可交易) = 真正的尾部风险可管理。砍 *ST 的代价远大于收益。如果未来注册制下退市潮，再重新评估。

## 关键决策
- **文档治理**(2026-06):CLAUDE.md 精简(操作宪法)/ SPEC.md(架构)/ STATUS.md(进度)/ LESSONS.md(本文件)。别再把设计/进度往 CLAUDE.md 堆。
- **母策略两层台账**(2026-06):口径降为版本属性;组合 vs 轮换待定(先只立分类)。
- **阶段 0 收束**(2026-06):统一 `core/` 内核 + data_lake + 真实成本;旧 `data_full/data` 约 513M 清理,旧 `evolve` 不再是主线。
- **项目级目标校准**(2026-06):原"年化 35%/回撤 15%"锚定在 v1.0 的 `data_full` 水分 40%,去水分+真实成本后真实基线仅 21%,该目标退役。校准为**双轨**:满意线 年化≥20% & 夏普≥1.0(baseline 已达),卓越线 年化≥28% 或 卡玛≥1.6。单母策略入册线 15%/20% 不变。组合路线(`scripts/research/portfolio_combo.py` 验证)能降回撤/提卡玛(压力 -33.9%→-27.8%),但难把绝对收益提到 35%——目标连同口径一起"去水分"。

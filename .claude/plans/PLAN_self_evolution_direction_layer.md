# PLAN — 自进化「方向半环」补全:教训机械回流 + 组合定时化 + 枯竭外探

> 日期:2026-07-02。来源:owner 诉求「定时因子研究/多因子多策略组合/吸取教训找正交因子/自进化/枯竭时自己搜业界方向、自己找新数据」。
> 诊断结论:**验真半环已工业级完备**(L1 四地基全落地,LOOP_ENGINEERING §5 全 ✅);缺的是**方向半环**——
> 教训与元研究产出没有机械回流到候选生成器,组合层无定时 job,「枯竭 → 外部探索」无触发器。
> 本计划全部在现有架构内落地,不新增框架,不触碰任何 P0 红线(验真/选择/晋级仍归确定性代码与人)。

---

## 0. 已验证的现状缺口(证据)

1. **教训不回流**:`knowledge/graph.py` 的 SearchGate 只从单候选验证结果自长(`record_from_validation`),
   研究级证伪(LESSONS/DECISIONS/research_ledger 的方向级结论)只存在于自然语言。活证据:
   `factory/autoresearch/generator.py::_SEEDS` 仍把北向/股东户数「置顶」标注为"最强正交源",
   而 research_ledger run `e6e655401623899d` 已证该族 top25 long-only 下太弱(残差 ICIR~0.2)。
2. **方向门对 DSL 候选失配**:`ast_to_hypothesis` 把所有 autoresearch 候选的 `factor_fn_name`
   统一写成 `factors.autoresearch_dsl.compute_dsl_factor` → 现有 SearchGate 因子级匹配对
   autoresearch 候选**永远失配**(真实盲区,需 term 级匹配修复)。
3. **metasearch 是孤儿**:MI 冗余簇(38% 算力白算)与 information_map 空白区(06-23 人工跑出)
   只打印/出图,无机器可读产物,无调度,生成器不消费。
4. **组合是一次性实验**:06-30 复合组合(17.68%/1.16)为人工实验;`portfolio/` 优化器、
   `marginal_alpha` 均在但无定时 job;R-PROD-001 的 top-N paper 排名持久化未落地。
5. **枯竭无信号**:`scheduled_factor_search` 零晋级时只打印即退出,不留摘要 → 「连续 N 周无产出」
   这一枯竭事实系统自己看不见,更不会触发外探。

---

## 1. 工作流划分

### WS-A 方向级教训登记簿(本次落地)⭐ 杠杆最大
- `knowledge/direction_registry.json`(git 跟踪,人/强模型策展,**证据门控**:无 evidence 指针的条目一律忽略)。
  条目 schema:`id / direction / status(falsified|weak|frontier) / action(SKIP|DEPRIORITIZE|BOOST|NOTE)
  / scope_factors[](白名单因子名) / evidence[](ADR/LESSONS/report/run_id 指针) / revival_condition
  / created / expires(到期自动失效=复活重测) / prompt_note`。
- `knowledge/directions.py`:加载/校验/查询 API(`seed_action`/`boost_factors`/`prompt_block`/`direction_findings`)。
- `graph.py`:`_atom_attrs` + `SearchGate.matches` 支持 `term_factor` 匹配(修缺口 2);
  `load_graph()` 内存合并方向 findings → promote/pipeline/factory_cli 自动消费,不落盘不污染机器自长文件。
- 接线生成端:`generate_seed_candidates`(SKIP 不生成/DEPRIORITIZE 排尾/BOOST 排头,自饿保护:
  滤空则退回未过滤+诚实警告);`generate_llm_candidates` prompt 注入 `prompt_block()`。
- 初始策展条目(全带证据指针):北向/holder/资金流族 weak→DEPRIORITIZE(带复活条件:宽持仓/多空结构);
  等权全市场动量单因子 NOTE;size×illiquidity 同信息 NOTE;基本面族 frontier→BOOST(metasearch 06-23)。

### WS-B metasearch 机械回流(本次落地)
- `factor_mi_audit` / `information_map` 加 `--json`:落 `metasearch/redundancy_clusters.json`
  (簇成员→白名单因子名映射)/ `metasearch/frontier.json`(最独立远邻因子)。
- 生成端消费(fail-open,文件缺→不过滤):种子两腿同簇 → DEPRIORITIZE(同信息组合);
  frontier 因子并入 BOOST 集。
- `scheduled_weekly_maintenance` 挂**月度** metasearch 刷新步(研究旁路,失败不标 failed)。

### WS-C 枯竭触发器 + 数据 scouting 清单(本次落地)
- `scheduled_factor_search` 每次运行落摘要 `reports/research/factor_search_runs.jsonl`
  (date/evaluated/n_promoted/holdout_ok/marginal verdicts)。
- `services/read/research_exhaustion.py`(纯读层,确定性 advisory):连续 K=4 次 run 零晋级或全冗余
  → `exhausted`;样本不足/文件缺 → `insufficient_evidence`(不假绿不假红)。
- `decision_inbox` 加第七源(info 级):exhausted → 建议启动 probe-signal-source 剧本 + 指向数据源清单;
  源不可读 → 显式入箱(沿用现有 `_source_error_item` 纪律)。
- `knowledge/data_source_backlog.json`:候选新数据源清单(带正交性论据 + 优先级)。
  **置顶 = 退市股数据回补**(幸存者偏差是已确认 P0 级数据债,也是多条死路的复活条件);
  其余:筹码分布 cyq_chips / 龙虎榜 top_list / 大宗 block_trade / 集合竞价 stk_auction /
  解禁 share_float / 业绩预告 forecast·express / 质押 pledge / 互动易 irm_qa / 游资 hm_detail。

### WS-D 组合再构成定时 job + top-N paper 排名持久化(规划→TASKS)
- `scheduled_portfolio_recompose`(周度):在册+影子池日收益(`data_lake/version_returns/`)
  → 逐腿 `marginal_alpha` 边际贡献 → `PortfolioOptimizer` 重算权重 → 建议进决策收件箱(人裁决,不自动生效)。
- 排名由后端确定性代码产出并持久化(R-PROD-001);top-N 自动开 paper 账户并行实测;组合本身进衰减复测。

### WS-E 文献扫描剧本(规划→TASKS,价值最不确定放最后)
- 枯竭信号触发的 agent 剧本:WebSearch 扫 SSRN/arXiv q-fin/业界研究 → 带出处 Hypothesis 草案
  进 factory 候选队列(R-LLM-001 合规:只提假设,不判有效)。落成 agent skill 文档。

---

## 2. 不可违反边界(全程)

- 方向登记簿只影响**生成端**搜索空间分配(跳过/降权/倾斜);候选无论来源仍走完整 L0-L3/9-Gate/holdout
  (R-LLM-001 / R-WF-001 不动)。
- 枯竭信号 = advisory,不自动启动任何外部抓取;外探剧本由人从收件箱批准(LOOP §6)。
- 生成端 steering 一律 fail-open(读不到登记簿/簇文件 → 不过滤,诚实警告),绝不因方向层故障阻断搜索;
  验真端无任何改动。
- 证据门控:登记簿条目无 evidence 指针 → 忽略 + 警告(防「顺手编方向」污染搜索空间)。

## 3. 对抗性测试要求(护栏 C,happy-path = 未完成)

1. SKIP 方向真拒:登记 SKIP 后含该因子的种子必须消失;登记簿为空时同因子必须出现(证明过滤真的在干活)。
2. 证据门控真拒:无 evidence 条目不产生任何 gate/过滤。
3. 保质期真传播:条目过期 → 因子种子复活(复活重测语义)。
4. 排序真变:DEPRIORITIZE 因子种子排尾、BOOST 排头(与无登记簿基线对比断言)。
5. 自饿保护真兜底:登记簿 SKIP 全部因子 → 退回未过滤 + 警告标志。
6. term_factor 门真修盲区:同一 SearchGate 对 DSL 候选(via ast terms)命中,旧 factor_fn_name 匹配必失配。
7. LLM prompt 真注入:假 adapter 捕获 prompt,断言方向块存在。
8. MI 簇真降权:fixture 簇文件下同簇两腿种子被降权;文件缺失 → 顺序不变。
9. 枯竭信号:4 次零晋级 → exhausted;混合 → healthy;样本<4/文件缺 → insufficient_evidence(不假红)。
10. 收件箱:exhausted 产 info 项(不计入待裁决数);源读取异常显式入箱不静默。

## 4. 验收

- `bash scripts/test_all.sh` 静态守卫全绿 + 新增对抗测试全过(worktree 无数据湖,数据依赖用例环境性失败照 STATUS 惯例注明)。
- 文档同步:TASKS.md(WS-D/E 立项)、STATUS.md、DECISIONS.md(方向登记簿机制 ADR)。
- 提交按 §11:一个 commit 一个意图(A/B/C/文档分拆)。

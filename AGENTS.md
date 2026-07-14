# AGENTS.md — 通用 agent 项目指令(A股全市场因子量化研究)

> **定位**:跨工具 agent 的**协作底线**(共享工作树下的提交纪律等),所有 agent 共读。
> **何时读**:任何 agent 接手本仓、尤其动 git 之前。
> **不归这管**:数据/策略/架构**铁律** → [CLAUDE.md](CLAUDE.md);哪个**平台**干哪类负载 → [MULTI_AGENT.md](MULTI_AGENT.md);每步流程谁干 → [WORKFLOW.md](WORKFLOW.md)。

`AGENTS.md` 是**跨工具共读**的项目级 agent 指令:Codex、**Antigravity**、Cursor、Claude Code 等都会读它。
本仓库由**多个 agent 并发共享同一个工作树**,本文件给所有 agent 立共同的协作底线;
完整开发宪法见 [CLAUDE.md](CLAUDE.md)(数据/策略/架构铁律、成本模型、分层依赖、台账唯一写入口),
分工与交接见 [MULTI_AGENT.md](MULTI_AGENT.md)。**冲突时以 CLAUDE.md 为准**(Antigravity 另需让位其 GEMINI.md)。
接手先读 CLAUDE.md + STATUS.md。

## 提交纪律(最高优先级,违反 = 卷走别人改动/无法 revert)

多 agent 共享工作树时,烂提交会把别人的半成品一起焊死进历史。必须:

1. **一个 commit = 一个完整、可独立 revert 的意图**。宁可拆成几个小而自洽的 commit,不要一个"什么都做了"的大杂烩。
2. **绝不 `git add -A` / `git add .` / `git commit -a`**。一锅端会卷进别的 agent 正在改的文件。
   **只用显式路径** `git add <file>...`,只 stage 你 trace 得清、属于本次意图的文件。
3. **提交前必核对范围**:`git diff --cached --stat` + `git diff --cached`,确认每个文件、每一行都 trace 到本次目的;
   别人的改动**留在工作树,不碰**。
4. **不擅自切分支 / reset / rebase / amend 共享分支或别人的 commit**。动 git 历史前先 `git status`
   看有无他人正在改的文件;有疑问先停下问,别先斩后奏。
5. **message 讲"为什么"**:`type(scope): 标题`(conventional commits) + 正文写根因(diff 看不出的部分)
   和验证证据;提交前先跑守卫+测试,绿了再提。
6. **数据湖/大体量运行产物不入库**(`data_lake/`、`scratch/*.csv`、运行结果);这也是不能 `add -A` 的硬理由。

## 与 CLAUDE.md 共通的铁律(摘要,详见 CLAUDE.md)

- **分层依赖单向**:`data(lake) → factors → core.engine → {strategies, factory/workflow} → registry → production`;
  提交前跑 `python3 factor_research/scripts/ci/check_layer_deps.py` 确认无倒灌。
- **回测唯一权威 = `core.engine.BacktestEngine`**;台账唯一写入口 = `strategy_registry.register()`;
  数据湖写入口 = `lake/` 或 `scripts/data/`。
- **真实口径不可动**:样本、公式、成本、`shift(1)`、T+1 一律不许为"达标"而改。
- **接入新数据源必须先读固定剧本** [`data_source_onboarding.md`](factor_research/docs/agent_skills/data_source_onboarding.md)
  再动手:S0 立项五判 → 小样本探针 → 契约声明(时间轴口径三选一,防未来函数) → 回填 → 质量门 →
  统一加载层 → 登记,逐步 fail-closed。**不得临场自创接入流程**;历史工程事故(东财封禁/单位错
  100 倍/幸存者偏差/未来泄露)全部源于跳过这些步骤。数据落湖 ≠ 因子有效,价值判断另走 probe。
- **一键检查**:`bash factor_research/scripts/test_all.sh`(分层+数据湖守卫 + 全部测试)。

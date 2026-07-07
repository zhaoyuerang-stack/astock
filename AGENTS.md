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

## 提交 / 归档 / 忽略判定规则

脏工作树先分桶,再处理。默认问题不是"能不能提交",而是:

1. **它是不是源文件?** 能决定系统行为、研究口径、接口契约、测试结果或活文档的,才可能提交。
2. **它能不能复现?** 由脚本/测试/渲染/回测重新生成的产物,默认不提交;只提交生成它的源脚本、配置和必要说明。
3. **它有没有长期审计价值?** 研究结论、ADR、可复现实验报告、人工决策记录可提交;一次性中间文件、临时 CSV、截图缓存、局部 profiler 输出不提交。
4. **它是否含本地/私密信息?** token、本机 IDE 配置、个人 workspace、私有小程序配置、connector/agent 本地状态一律不提交。
5. **它能否独立 revert?** 不能和本次意图一起解释清楚的文件,留在工作树,另起 commit 或归档。

目录级默认动作:

| 类别 | 默认动作 | 例子 |
| --- | --- | --- |
| 代码源文件 | 提交 | `factor_research/{api,core,factors,workflow,portfolio,strategies}/**/*.py`, `web/**/*.tsx` |
| 测试与守卫 | 提交 | `factor_research/tests/**/*.py`, `factor_research/scripts/ci/*.py` |
| canonical 配置/台账 | 谨慎提交 | `app_config/*.yaml`, `strategy_versions.json`, `strategy_families.json`;必须说明生成/修改入口 |
| 活文档/ADR/运行手册 | 提交 | `CLAUDE.md`, `STATUS.md`, `DECISIONS.md`, `RUNBOOK.md`, `docs/**/*.md` |
| 可复现实验报告 | 归档后提交 | `reports/research/*.md`;必须包含数据口径、命令、日期、结论边界 |
| 探索脚本 | 先归档/转正再提交 | `scratch/*.py` 若复用,迁到 `scripts/research/` 或 `scripts/ops/`;否则留本地 |
| 运行产物/缓存 | 忽略或删除 | `*.profraw`, `.thumbnails/`, `.waveform-cache/`, `renders/`, 临时 CSV/JSON |
| 本地 agent/IDE 状态 | 忽略 | `.agents/`, `.superpowers/`, `.workbuddy/`, `*.code-workspace` |
| 私有/本机配置 | 忽略 | `project.private.config.json`, token/密钥/本机路径配置 |
| 大体量数据湖/行情缓存 | 忽略 | `data_lake/`, `data_full/`, `data/`;除非是明确跟踪的 schema/manifest 且有审计理由 |

归档规则:

- **仍有参考价值但不是生产入口**:放到 `docs/archive/` 或对应模块 `archive/`,文件头写明"历史参考,不作实现依据"。
- **研究报告可复现**:放 `reports/research/`,正文必须写数据版本、命令、样本区间、成本口径、`shift(1)`/T+1 口径和主要失败风险。
- **探索脚本转正**:只有当脚本被复用、被文档引用、或进入流程入口时,才从 `scratch/` 迁入 `scripts/research/` / `scripts/ops/` 并补最小测试或 dry-run 验证。
- **纯运行中间物**:不归档,不提交;必要时加 `.gitignore`。

提交前检查口径:

```bash
git status --short --branch
git diff --name-only
git diff --cached --stat
git diff --cached
```

只允许显式路径 stage。看到 `scratch/`、本地配置、缓存、渲染产物、私密配置时,默认先停下分桶,不要顺手提交。

## 与 CLAUDE.md 共通的铁律(摘要,详见 CLAUDE.md)

- **分层依赖单向**:`data(lake) → factors → core.engine → {strategies, factory/workflow} → registry → production`;
  提交前跑 `python3 factor_research/scripts/ci/check_layer_deps.py` 确认无倒灌。
- **回测唯一权威 = `core.engine.BacktestEngine`**;台账唯一写入口 = `strategy_registry.register()`;
  数据湖写入口 = `lake/` 或 `scripts/data/`。
- **真实口径不可动**:样本、公式、成本、`shift(1)`、T+1 一律不许为"达标"而改。
- **一键检查**:`bash factor_research/scripts/test_all.sh`(分层+数据湖守卫 + 全部测试)。

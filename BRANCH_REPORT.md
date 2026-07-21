# 分支状态日报

生成时间: 2026-07-21 12:33 PDT

> 本报告由每日定时任务机械生成,只做只读分析(rev-list / merge-tree / 隔离 worktree 跑 test_all.sh)。
> **不执行任何分支合并、不修改除本文件外的任何内容。是否合并、何时合并由人工决定。**
> 深检(test_all.sh)每次最多跑 5 个候选分支,本次实际跑了 0 个,以控制机器负载。

| 分支 | 最后提交 | 落后/领先 main | 状态 | 说明 |
|---|---|---|---|---|
| `claude/daily-round-9` | 2026-07-19 06:48 | -41/+2 | **CONFLICT** | git merge-tree 对 main 检测到冲突,需要人工 rebase/解冲突 |
| `claude/gracious-joliot-801c36` | 2026-07-10 08:41 | -220/+27 | **CONFLICT** | git merge-tree 对 main 检测到冲突,需要人工 rebase/解冲突 |
| `claude/sleepy-euclid-e50e34` | 2026-07-10 04:56 | -220/+17 | **CONFLICT** | git merge-tree 对 main 检测到冲突,需要人工 rebase/解冲突 |
| `codex/converge-governance` | 2026-07-14 21:56 | -158/+3 | **CONFLICT** | git merge-tree 对 main 检测到冲突,需要人工 rebase/解冲突 |
| `codex/xiaochengxu` | 2026-07-14 20:28 | -272/+145 | **CONFLICT** | git merge-tree 对 main 检测到冲突,需要人工 rebase/解冲突 |
| `claude/daily-round-10` | 2026-07-20 22:54 | -37/+3 | **ACTIVE_WORKTREE** | 当前被其他 worktree 检出(/Users/kiki/astcok/.claude/worktrees/daily-research-round),疑似进行中,跳过深检以免打扰 |
| `codex/ml-multifactor-bias-correction` | 2026-07-19 09:10 | -37/+4 | **ACTIVE_WORKTREE** | 当前被其他 worktree 检出(/private/tmp/astcok-ml-multifactor-bias-correction),疑似进行中,跳过深检以免打扰 |
| `grok/l01-timing` | 2026-07-20 22:54 | -34/+1 | **ACTIVE_WORKTREE** | 当前被其他 worktree 检出(/private/tmp/grok-l01-timing),疑似进行中,跳过深检以免打扰 |
| `claude/epic-dubinsky-3a3f52` | 2026-07-04 20:00 | -232/+7 | **STALE_PARALLEL** | 已知活跃分支的旧并行影子版本,历史结论=别硬合,等主线收工 |
| `ws0-ws4-topn` | 2026-07-01 20:26 | -272/+4 | **STALE_PARALLEL** | 已知活跃分支的旧并行影子版本,历史结论=别硬合,等主线收工 |
| `ws2-composite` | 2026-07-05 06:07 | -237/+1 | **STALE_PARALLEL** | 已知活跃分支的旧并行影子版本,历史结论=别硬合,等主线收工 |
| `claude/brave-golick-426851` | 2026-06-30 13:27 | -274/+1 | **FROZEN** | 命中冻结名单(owner 已明确暂缓),不评估 |
| `claude/naughty-raman-133948` | 2026-07-05 06:08 | -334/+35 | **FROZEN** | 命中冻结名单(owner 已明确暂缓),不评估 |
| `claude/thirsty-rhodes-40ed0c` | 2026-06-30 12:53 | -277/+2 | **FROZEN** | 命中冻结名单(owner 已明确暂缓),不评估 |
| `claude/daily-round-8` | 2026-07-19 01:13 | -103/+0 | **NO_NEW_COMMITS** | 相对 main 无新增 commit(落后 103),无内容可合,建议核实后归档/删除 |
| `claude/system-lessons-knowledge-base-0ef77a` | 2026-07-18 12:42 | -92/+0 | **NO_NEW_COMMITS** | 相对 main 无新增 commit(落后 92),无内容可合,建议核实后归档/删除 |
| `grok/adr037-session-audit` | 2026-07-18 07:13 | -76/+0 | **NO_NEW_COMMITS** | 相对 main 无新增 commit(落后 76),无内容可合,建议核实后归档/删除 |
| `subagent-GA-Parallel-Search-Benchmarker-self-1155d691` | 2026-06-28 04:56 | -319/+0 | **NO_NEW_COMMITS** | 相对 main 无新增 commit(落后 319),无内容可合,建议核实后归档/删除 |
| `subagent-Optimization-Benchmarker-self-a5233b55` | 2026-06-27 18:11 | -327/+0 | **NO_NEW_COMMITS** | 相对 main 无新增 commit(落后 327),无内容可合,建议核实后归档/删除 |
| `subagent-Quantitative-Performance-Engineer-self-2e4c9739` | 2026-06-27 18:11 | -327/+0 | **NO_NEW_COMMITS** | 相对 main 无新增 commit(落后 327),无内容可合,建议核实后归档/删除 |
| `subagent-Surrogate-Search-Optimizer-self-14cb5973` | 2026-06-27 18:11 | -327/+0 | **NO_NEW_COMMITS** | 相对 main 无新增 commit(落后 327),无内容可合,建议核实后归档/删除 |
| `worktree-docs-cleanup` | 2026-06-20 23:17 | -430/+0 | **NO_NEW_COMMITS** | 相对 main 无新增 commit(落后 430),无内容可合,建议核实后归档/删除 |

## 状态说明
- `MERGEABLE`: 机械信号+test_all.sh 全绿,可交给人工评审后合并。
- `GUARD_FAIL`: 无冲突但守卫/测试未过,需要人工看失败原因。
- `CANDIDATE`: 未被深检(通常因为已达单次深检上限),下次运行会继续排队。
- `CONFLICT`: 与 main 有冲突,需先 rebase/手动解决。
- `ACTIVE_WORKTREE`: 分支当前被某个 worktree 检出,可能有人/某 agent 正在写,跳过。
- `STALE_PARALLEL`: 已知活跃分支的旧并行版本,历史结论是别硬合,等主线收工。
- `FROZEN`: 命中 owner 冻结名单,不评估。
- `NO_NEW_COMMITS`: 相对 main 没有新提交,无可合并内容。

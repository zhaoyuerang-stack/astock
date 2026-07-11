# LOOP_QUICK_CALLS.md — Loop OS Agent 速调用清单

> 目的:给 Codex / Claude Code / Antigravity 等 agent 快速判断哪些 Loop OS 命令可以直接跑,哪些必须等人工确认。

工作目录:

```bash
cd /Users/kiki/astcok/factor_research
```

## Safe Quick Checks

这些命令是只读、dry-run 或测试/守卫类,agent 可以快速调用:

```bash
python3 apps/loop_cli.py status --root .
python3 apps/loop_cli.py dry-run --root . --no-staleness
python3 scripts/ci/check_loop_contracts.py
python3 scripts/ci/check_layer_deps.py
bash scripts/test_all.sh
```

Loop OS 专项测试:

```bash
python3 -m pytest -q \
  tests/test_loop_contracts.py \
  tests/test_loop_store.py \
  tests/test_loop_policy.py \
  tests/test_loop_adapters.py \
  tests/test_loop_orchestrator.py \
  tests/test_loop_cli.py \
  tests/test_loop_api.py \
  tests/test_loop_weekly_source.py \
  tests/test_loop_ci_guard.py
```

## Human-Confirmed Only

以下是真研究动作,不得自动调用:

```bash
python3 apps/loop_cli.py weekly --root . --confirm-record-trials
```

原因:

- `weekly` 会调用真实候选源。
- `island_search` 会永久记录 trials。
- trials 会影响后续 DSR 多重测试惩罚。
- 这不是 smoke test,只能由人按周度研究节奏明确批准。

## Never As Quick Calls

agent 不得把以下动作当作速调用:

- 直接写 `strategy_versions.json` / registry JSON。
- 绕过 `workflow/promote.py` 注册策略。
- 自动 promote / 自动上线 / 自动改 production manifest。
- 为了通过门槛改成本、样本、`shift(1)`、holdout boundary 或 DSR trial 数。

## Rule

安全检查可以快跑;真实研究、registry 写入、production 写入必须有人工确认和完整证据链。

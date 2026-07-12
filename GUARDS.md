# GUARDS.md — 规则守卫索引

> 本文件是 `scripts/ci/` 实际守卫脚本的索引表。**唯一真相 = 脚本本身**，均由 `scripts/test_all.sh` 调用。
> 本表原为 `CLAUDE.md` §16，2026-07-11 下沉到本文件以控制宪法长度；规则语义未变，只是搬了位置。
> 规则编号定义（P0/P1 具体内容）见 [`CLAUDE.md`](CLAUDE.md) §4/§5。

| 规则 / 关注点 | 等级 | 守卫脚本(`scripts/ci/`) | 说明 |
| --- | --- | --- | --- |
| R-ARCH-001 单向依赖 | P1 | `check_layer_deps.py` | AST 静态分析 FORBIDDEN_EDGES，禁下层/生产层反向 import |
| API 薄层 / artifact 边界 | P1 | `check_layer_deps.py` | API 禁直接读取 `data_lake/reports/signals/paper`；直接写运行审计产物必须显式经 `services.actions.action_guard` |
| services 权限分层 | P1 | `check_layer_deps.py` | `services.read` 禁 import `services.actions`；`services.actions` 高风险 promote/registry 动作必须经 `jobs` 或 `action_guard` |
| workflow / script 边界 | P1 | `check_layer_deps.py` | `workflow.*` 禁 import `scripts.research.*`；research script 只能包 CLI |
| R-ARCH-004 数据湖写入可审计 | P1 | `check_lake_writers.py` | 写 data_lake 核心区必须走 canonical writer + 更新 manifest |
| R-WF-001 候选入册通道 | P0 | `check_no_force_promote.py` | 禁 bulk/scheduled/factory_cli/autoresearch 字面 `force=True`/`run_marginal=False`；holdout 硬闸在 `phase4_register`(force 亦不可绕) |
| R-REG-001 / R-EVIDENCE-001 证据自证 | P0 | `check_registry_evidence.py` | 禁跨家族 IC 照抄；standalone DSR(G3)+nine_gate 收据(G4)；diversifier 须 marginal_receipt 绑定 corr/residual(G5) |
| R-OBJECTIVE-001 DSR 强制门 | P0 | `strategy_registry.register()` + `check_registry_evidence.py`(G3) | standalone 准入须 dsr_p<0.05(多重测试惩罚显著)，hit 达标≠通过 |
| G8 防自欺 / holdout | P0 | `check_holdout_compliance.py` | 自动环+promote 验证栈(phase2/3)load 全样本必须截到 <boundary；锁 holdout.start hash(ADR-021)；强制 boundary 只进不退+账本一致(ADR-023)，禁偷看金库 |
| 防自欺 / 控制路径可观测 | P0 | `check_control_exceptions.py` | 准入/裁决/信号/执行路径禁 `except: pass` 静默吞异常 |
| 测试发现完整 | P1 | `check_test_discovery.py` | 全量收集 `test_*.py`，杜绝漏跑的手工清单 |
| R-DATA-001 禁用旧口径 | P0 | `check_no_legacy_data.py` | AST 禁代码 import data_full / 从 data_full 目录读盘(放过注释/口径标签/迁移目录) |
| amount 单位口径 | P0 | `check_amount_units.py` | 正式路径重建 amount 禁 `volume×100×price`；canonical = `lake.units.implied_amount`(share×raw) |
| R-COST-001 正式成本 | P0 | `check_cost_model_usage.py` | 正式策略/workflow 禁非正 stock 腿成本 |
| R-ARCH-002 生产层隔离 | P1 | `check_layer_deps.py`(覆盖) | production 禁 import research 在依赖图内强制 |
| Git 禁止一锅端 | P1 | 人工 diff | 多 agent 共享工作树必守，无脚本可代替 |

> 注：本表里的 "G3"/"G8" 是 `check_registry_evidence.py`/`check_holdout_compliance.py` 脚本内部自定义的检查编号，**不等同于** `CLAUDE.md` §6 的 Gate 0–8（那是 `core/analysis/nine_gates.py` 的因子评估流水线编号）。两套编号历史上共用过 "G" 前缀造成过混淆，这里明确标注避免误读。

凡"缺/待建"的守卫，应在 `TASKS.md` 立项。

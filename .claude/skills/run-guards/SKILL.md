---
name: run-guards
description: 跑一次本仓全量守卫 + 测试(factor_research/scripts/test_all.sh:7 个 check_*.py 静态守卫 + ~50 个 test_*.py),只跑一次、不重复轮询,捕获首个失败块并定位到对应 P0/P1 规则,给出可读摘要。当完成 数据/因子/引擎/策略/workflow/registry 改动、提交前要确认守卫全绿时用。test_all 用 set -e 首个失败即停,本 skill 负责把"哪一块挂了、对应哪条红线"讲清楚。
---

# run-guards —— 全量守卫 + 测试的一次性可读执行

> 本仓 = A股全市场日频因子量化研究系统。守卫现状唯一真相 = `factor_research/scripts/ci/` 实际脚本;一键入口 = `factor_research/scripts/test_all.sh`(`CLAUDE.md` §13/§16)。
> 本 skill 把"跑守卫"固化成:**跑一次、读对失败、定位红线**,杜绝报告里出现过的"重复轮询 + 重复跑 test_all"的浪费。

## 这个 skill 解决什么

`test_all.sh` 用 `set -e`,**首个失败即整体中止**,后面的块根本不跑。
痛点:① 容易重复跑 / 反复轮询同一个后台任务(浪费轮次);② 只看尾巴 `🎉 All tests passed!` 有没有出现,不知道**具体哪一块、对应哪条 P0/P1 红线**。
本 skill:一次性跑、把输出落盘、**精确报出首个失败块 + 它守的是哪条规则**,绿了就一句话收尾。

## 铁律

1. **跑一次,不重复**:一个 session 内对**同一份未改动的工作树**,守卫只跑一次。后台跑就**等它一次性结束再读结果**,禁反复 `tail`/轮询/重跑(报告里的明确摩擦点)。
2. **不为变绿改红线**(§12.3):守卫挂了 → 读错误、找根因、改**代码**;**禁**删测试 / 弱化断言 / 改样本/成本/shift/T+1/股票池让它变绿。那样作废(§4 P0)。
3. **静态守卫优先级 > 单测**:前 7 个 `check_*.py` 守的是分层依赖 / 证据自证 / holdout / 防 force-promote 等架构与防自欺红线(P0/P1);它们挂比某个 `test_*.py` 挂更严重,先读这类错误。
4. **不替你裁决**:本 skill 只跑既有守卫并报结果,不新增/放宽门禁,不判断策略有效性。

## 怎么跑

### 标准用法(前台,几分钟内)
全量约 60 个步骤(7 守卫 + ~50 测试),跑几分钟。落盘后判读,避免边跑边猜:
```bash
LOG="$CLAUDE_JOB_DIR/tmp/guards.log"   # 无 $CLAUDE_JOB_DIR 时用 /tmp/guards.log
bash factor_research/scripts/test_all.sh > "$LOG" 2>&1; echo "EXIT=$?"
tail -3 "$LOG"
```
- `EXIT=0` 且末尾有 `🎉 All tests passed!` → **全绿**,一句话收尾(见下)。
- `EXIT≠0` → 进"定位失败"。

### 定位失败(set -e:最后一个 `=== ... ===` 块就是失败点)
```bash
grep -n '^=== ' "$LOG" | tail -1      # 最后启动的块 = 失败块(后面的没跑)
tail -40 "$LOG"                       # 该块的真实报错(traceback/AssertionError)
```
把失败块名映射到规则(`CLAUDE.md` §16 守卫表):

| 失败块(`check_*.py`)             | 规则 / 含义                                   | 等级 |
| ----------------------------- | ----------------------------------------- | -- |
| `check_layer_deps.py`         | R-ARCH-001/002 单向依赖 + 生产层禁 import 研究层 + 台账唯一写入口 | P1 |
| `check_test_discovery.py`     | 测试发现完整:有 `test_*.py` 没被收录                  | P1 |
| `check_control_exceptions.py` | 控制路径禁 `except: pass` 静默吞异常                 | P0 |
| `check_registry_evidence.py`  | R-EVIDENCE-001 台账证据自证:禁跨家族照抄 / DSR 缺算不显著  | P0 |
| `check_holdout_compliance.py` | G8 防自欺:自动选择路径必须 holdout 截断(偷看金库)          | P0 |
| `check_no_force_promote.py`   | R-WF-001 禁 `force=True` 跳过 phase1/2 防未来门  | P0 |
| `check_no_legacy_data.py`     | R-DATA-001 禁 import/加载 `data_full` 旧口径    | P0 |
| `check_lake_writers.py`       | R-ARCH-004 数据湖唯一写入口 + 更 manifest          | P1 |
| `test_*.py`(任意单测)             | 对应模块行为/不变量回归(块名注释已说明守什么)                  | 视测试 |

报告时讲清:**哪个块挂、对应哪条规则、错误根因一句话、建议下一步**。P0 守卫挂 = 触及作废级红线,优先修。

### 后台用法(想边改边等时)
```bash
# run_in_background=true 跑,等它结束的通知,不要反复轮询
bash factor_research/scripts/test_all.sh > "$CLAUDE_JOB_DIR/tmp/guards.log" 2>&1
```
后台任务结束会自动回调;**在那之前不 tail、不重跑**。结束后按上面"定位失败"读 log。

### 只想快速过静态守卫(改了架构/依赖/台账时)
单测慢,若本次只动了依赖结构 / 台账 / 数据湖写入,可先单独跑相关 `check_*.py` 快速验:
```bash
cd factor_research && python3 scripts/ci/check_layer_deps.py && python3 scripts/ci/check_registry_evidence.py
```
但**提交前仍需一次完整 `test_all.sh` 全绿**(§13:开发期不得用局部检查代替全量)。

## 收尾报告模板
- **全绿**:`守卫全绿:7 静态守卫 + N 测试通过(test_all.sh EXIT=0)`。
- **挂了**:`失败:<块名>(<规则>,<P0/P1>)。根因:<一句话>。下一步:<改哪里>。其余块因 set -e 未跑。`

## 反模式(禁止)
- 反复 `tail` / 轮询后台守卫 / 重复跑 `test_all.sh`(报告里的真实浪费)。
- 只看有没有 `🎉` 就报"通过",不核对 `EXIT` 码。
- 守卫挂了去删测试 / 弱化断言 / 改口径让它变绿(§12.3,作废)。
- 用单独跑某个 `check_*.py` 代替提交前的完整 `test_all.sh`。

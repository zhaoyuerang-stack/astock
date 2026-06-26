---
name: commit
description: 把本仓 CLAUDE.md §11 的原子提交纪律固化成一条命令——多 agent 共享工作树下安全提交。禁一锅端(显式 stage)、一 commit 一意图、提交前强制核对 diff、修正共享工作树 mode 位坑、按本仓 canonical 格式写 message(为什么/做了什么/验证 + Co-Authored-By + Claude-Session 尾注)。当要把已完成的本次改动提交入库时用。只编排提交流程,不替你判断改动对不对。
---

# commit —— CLAUDE.md §11 原子提交纪律的可执行封装

> 本仓 = A股全市场日频因子量化研究系统,**多 agent 共享工作树**,提交纪律是 P1。
> 上游唯一真相:`CLAUDE.md` §11(提交纪律)、`AGENTS.md`(跨工具协作底线)。本 skill 只把 §11 变成"每次照做的一条命令",**不放宽任何一条**。

## 这个 skill 解决什么

你每个 session 都在做同一件高风险的事:在共享工作树里**只提交属于本次意图的文件**、核对 diff、按固定格式写 message。
手动每次都要记全 §11.1–11.5,容易漏(误 stage 他人半成品、忘核对 diff、mode 位污染、尾注格式飘)。
本 skill 把这套流程固化,确定性步骤照做,**"改动本身对不对"仍由你判断**。

## 铁律(违反则本次提交需 revert 重做)

1. **禁一锅端**(§11.1):**禁** `git add -A` / `git add .` / `git commit -a`。必须显式 `git add <file>...`,只 stage trace 得清、属于本次意图的文件。
2. **一 commit 一意图**(§11.2):一个完整、可独立 revert 的意图。**禁**把数据修复 / 策略变更 / Web UI / 文档 / 测试 / 重构 / 格式化混进一个 commit。宁可多个小 commit。
3. **提交前必核对 diff**(§11.3):`git diff --cached --stat` + `git diff --cached` 必须亲眼看完。每个文件属本任务、每行可解释、没卷入他人半成品、没误删测试、没弱化断言、没改无关配置、没把大数据产物入库。
4. **禁擅改 Git 历史**(§11.4):共享分支上**禁** `reset --hard` / `rebase` / `push --force` / `clean -fd`,除非任务明确要求且确认无他人工作树风险。
5. **不替你裁决改动**:本 skill 只编排"安全地提交你已决定提交的东西";**不**判断策略是否有效、回测是否达标、因子是否该入册(那些走确定性门禁 + workflow,见 `R-LLM-001`/`R-WF-001`)。
6. **没看到 diff 不提交**:跳过步骤 3 直接 commit = 违反 §11.3,作废重做。

## 提交流程

### 步骤 0 — 看全局(必做)
```bash
git status --short        # 共享工作树:确认哪些是本次改动、哪些是他人/历史遗留
git stash list            # 确认没有半路 stash 会被误带
```
逐一认领:**只有你能 trace 到本次意图的文件**才进本次 commit;其余(他人半成品、未追踪的报告/数据产物)**不碰**。

### 步骤 1 — 显式 stage(禁通配)
```bash
git add path/to/file_a.py path/to/test_file_a.py   # 一个一个列;禁 -A / . / *
```
若本次改动横跨多个**不同意图**(如:一个因子 + 一处 Web 修复),**分两次 commit**——先 stage 第一意图的文件、提交、再 stage 第二意图。

### 步骤 2 — 修正共享工作树 mode 位坑(本仓已知坑)
共享工作树偶尔给文件加上 `+x` 执行位,diff 里出现 `old mode 100644 / new mode 100755`。提交前复位:
```bash
git diff --cached --summary | grep -i 'mode change' || echo "无 mode 变化"
# 若有非预期的 +x:对该文件 chmod -x <file> 后重新 git add <file>
```
(脚本类文件本就该可执行的除外;判断标准:这个 +x 是不是本次有意为之。)

### 步骤 3 — 强制核对 diff(P1,不可跳)
```bash
git diff --cached --stat      # 文件清单:每个都该在、没有多余
git diff --cached             # 逐行:每行可解释、无他人改动、无弱化断言、无大数据产物
```
核对清单(§11.3,逐条过):
- [ ] 每个文件都属本次意图,没有顺手带进无关文件
- [ ] 没有卷入他人半成品(对照步骤 0 的 `git status`)
- [ ] 没有误删测试 / 弱化断言让结果变绿(违反 §12.3)
- [ ] 没有改无关配置(费率/路径/数据源/股票池——动这些要走 §10/ADR)
- [ ] 没有把大 parquet / 数据产物 / `.next` build / 报告 csv 入库
- [ ] manifest / 台账类文件若变了,是本次有意更新(非被动副作用)

**任一条不过 → 回步骤 1 调整 stage,不准 commit。**

### 步骤 4 — 按本仓 canonical 格式写 message
格式(取自本仓真实 commit,**不要换成泛化英文模板**):
```text
type(scope): 中文标题(一句话说清这次干了什么)

为什么:
<diff 看不出的根因——为什么需要这次改动。这是 message 最有价值的部分。>

做了什么:
- <要点 1：动了哪个文件/函数,关键决策>
- <要点 2>

验证:<跑了什么命令、什么结果。如 "pytest=N passed;check_layer_deps/check_test_discovery 过">。
<若涉及策略/因子:补一句口径声明,如 "L0 证据非已验证 alpha,入册走 workflow(R-WF-001)">

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: <本次任务 kebab-slug>
```
`type` ∈ `feat / fix / refactor / docs / test / perf / governance / chore`;`scope` = 模块(factors / engine / web / registry / lake / agent / skill …)。

提交(用 heredoc 保多行 + 中文):
```bash
git commit -F - <<'EOF'
feat(scope): 标题

为什么:
...

做了什么:
- ...

验证:...

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
Claude-Session: my-task-slug
EOF
```

### 步骤 5 — 提交后自检
```bash
git show --stat HEAD          # 确认入库文件 = 步骤 3 核对过的那批,无多无少
git status --short            # 确认没把本该提交的漏在工作区,也没误清他人改动
```
报告:提交了哪些文件、commit hash、message 标题。若本次是**多意图拆成多个 commit**,逐个列。

## 反模式(禁止)
- `git add -A` / `git add .` / `git commit -am`(违反 §11.1)。
- 把数据修复 + 策略 + Web + 文档塞进一个 commit(违反 §11.2)。
- 不看 `git diff --cached` 就提交(违反 §11.3)。
- 为"让 CI 绿"删测试 / 弱化断言再提交(违反 §12.3)。
- 共享分支上 `reset --hard` / `rebase` / `push --force` 改历史(违反 §11.4)。
- 用英文泛化模板替掉"为什么/做了什么/验证"+ `Claude-Session` 尾注。
- 把"策略是否有效/是否入册"的判断写进 commit 当成结论(那是门禁 + workflow 的事)。

## 何时**不**用这个 skill
- 还没核对过改动对不对、测试没跑过 → 先做完 §12 任务循环(跑检查 §13)再来提交。
- 要改 Git 历史 / 处理 push 冲突 / 解决 rebase → 那是历史操作,§11.4 要单独谨慎处理,不在本 skill 范围。

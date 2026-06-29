#!/usr/bin/env python3
"""PreToolUse 守卫:把 CLAUDE.md 里"违反=作废"级的反模式从 skill 软提醒升级成硬阻断。

契约(Claude Code PreToolUse hook):
- stdin 收 JSON: {tool_name, tool_input, cwd, ...}
- exit 2  -> 阻断该工具调用, stderr 自动回灌给 Claude(看得到原因)
- exit 0  -> 放行
- 任何内部异常一律 fail-open(exit 0): 守卫绝不卡住合法操作

注:本脚本的"脚本缺失/python 缺失/语法错"等"启动级"失败 fail-open,由
.claude/settings.json 里的 wrapper 命令兜底(只有干净 exit 2 才阻断);本脚本
内部再用 try/except 把"运行级"异常也压到 exit 0。两层共同保证 exit 2 只在
"确实命中反模式"时出现 —— 否则会像首次部署那样把所有 Bash/Edit/Write 锁死。

拦的只有"确定性可正则匹配、且几乎从不该用"的几条。模式经对抗性审查扩展过
(裸 -A/--force 之外的等价绕过也要盖):
  §11.1 禁一锅端  : git add 全仓(-A/--all/./:/:(top)/* 等), git commit -a/-am
  §11.4 禁改历史  : git reset --hard, git push --force/-f/+refspec 强推,
                    git commit --amend, git clean -f*/--force,
                    git checkout -f, git switch -f/-C/--discard-changes
  R-DATA-001 旧口径: 编辑/写入 data_full 目录
其余纪律(一commit一意图、核对diff、内容里 import data_full)仍交给
/commit skill + scripts/ci/check_*.py,本 hook 只做最后一道硬闸。

边界声明(重要,别 whack-a-mole):这是"防手滑黑名单",不是安全边界 ——
命中时 stderr 会直接告诉用户怎么改写。只盖"常见危险写法 + 其直接等价绕过"
(如 add :/ ≡ add -A、push +ref ≡ push --force);**不**追求穷尽对抗
(alias / xargs git / git stage -A / update-ref / branch -D 等一律不拦)。
真要绕的人随时能绕;目的只是把"无意识手滑触发作废级操作"挡在门外。
新增模式前先问:它是不是某条已拦红线的常见直接等价写法?不是就不加。
"""
import sys
import json
import re
import shlex

# git add 的"全仓 pathspec"集合:单独出现即等价 -A 一锅端。
# 注意只列"单独=全仓"的 token;`./foo.py` `:/foo` `:(top)foo` 是具体路径,放行。
ADD_ALL_TOKENS = {"-A", "--all", ".", "./", ":/", ":(top)", "*"}


def _segments(command):
    """shlex 整条切 token 后,按 shell 控制符分段。引号内的分隔符已被 shlex
    正确归入 token,不会被误切(如 git commit -m 'fix; bug')。"""
    try:
        toks = shlex.split(command, posix=True)
    except ValueError:
        toks = command.split()
    segs, cur = [], []
    for t in toks:
        if t in (";", "&&", "||", "|", "&"):
            if cur:
                segs.append(cur)
                cur = []
        else:
            cur.append(t)
    if cur:
        segs.append(cur)
    return segs


def _git_calls(command):
    """从命令里抽出 (子命令, 参数列表),跳过 git 全局选项(-C path / -c k=v)。"""
    out = []
    for seg in _segments(command):
        if "git" not in seg:
            continue
        rest = seg[seg.index("git") + 1:]
        i = 0
        while i < len(rest):
            t = rest[i]
            if t in ("-C", "-c"):
                i += 2  # 带值的全局选项
                continue
            if t.startswith("-"):
                i += 1
                continue
            break
        if i >= len(rest):
            continue
        out.append((rest[i], rest[i + 1:]))
    return out


def _is_short_flag_with(args, ch):
    """args 里有没有"短选项簇含某字符",如 clean -fd / -fx 里的 f。"""
    return any(re.fullmatch(r"-[a-z]+", a) and ch in a for a in args)


def check_bash(command):
    hits = []
    R11_1 = "§11.1 禁一锅端"
    R11_4 = "§11.4 禁擅改历史"
    for sub, args in _git_calls(command):
        if sub == "add" and any(a in ADD_ALL_TOKENS for a in args):
            hits.append((
                R11_1,
                "`git add` 全仓(-A/--all/./:/:(top)/* 等)会把他人半成品 + 数据产物一并 "
                "stage。改用显式 `git add <file> ...`(只 stage 本次意图的文件),或走 "
                "/commit skill。",
            ))
        elif sub == "commit":
            if "--all" in args or any(re.fullmatch(r"-[a-z]*a[a-z]*", a) for a in args):
                hits.append((
                    R11_1,
                    "`git commit -a/-am` 跳过显式 stage。先 `git add <file>` 再 "
                    "`git commit -m`(或 /commit skill 的 heredoc 流程)。",
                ))
            if "--amend" in args:
                hits.append((
                    R11_4,
                    "`git commit --amend` 改写已存在的 commit = 共享分支上改历史。"
                    "另起新 commit;确需修补请人工确认无他人基于该 commit 后再手动执行。",
                ))
        elif sub == "reset" and "--hard" in args:
            hits.append((
                R11_4,
                "共享工作树禁 `git reset --hard`(真实数据丢失风险)。"
                "确需时人工确认无他人 worktree 风险后再手动执行。",
            ))
        elif sub == "push" and (
            any(a in ("-f", "--force") or a.startswith("--force-with-lease") for a in args)
            or any(a.startswith("+") for a in args)
        ):
            hits.append((
                R11_4,
                "禁 `git push --force` / `+refspec` 强推(覆盖远端他人提交)。",
            ))
        elif sub == "clean" and ("--force" in args or _is_short_flag_with(args, "f")):
            hits.append((
                R11_4,
                "禁 `git clean -f*/--force`(删除未追踪文件,曾致 .next 丢失事故)。"
                "先 `git clean -n` 干跑确认,确需再手动执行。",
            ))
        elif sub == "checkout" and (
            any(a in ("-f", "--force", "-B") for a in args)
            or any(a in ADD_ALL_TOKENS for a in args)
        ):
            hits.append((
                R11_4,
                "禁 `git checkout -f/-B` 或 `git checkout .`(强制丢弃工作区 / 强建分支,"
                "数据丢失风险)。具体文件 `git checkout -- <file>` 放行;先 stash/确认。",
            ))
        elif sub == "switch" and any(
            a in ("-f", "--force", "-C", "--force-create", "--discard-changes") for a in args
        ):
            hits.append((
                R11_4,
                "禁 `git switch -f/-C/--discard-changes`(丢弃工作区或强移分支)。"
                "用 `-c` 建新分支;确需强制请人工确认。",
            ))
    return hits


def check_path(file_path):
    if file_path and re.search(r"(^|/)data_full(/|$)", file_path):
        return [(
            "R-DATA-001 禁旧数据口径",
            f"禁编辑/写入 data_full(只含沪市主板的幸存者偏差旧缓存):{file_path}。"
            "用 data_lake 全市场口径。",
        )]
    return []


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)  # 读不到输入: fail-open

    try:
        tool = payload.get("tool_name", "")
        ti = payload.get("tool_input", {}) or {}
        if tool == "Bash":
            hits = check_bash(ti.get("command", "") or "")
        elif tool in ("Edit", "Write", "MultiEdit"):
            hits = check_path(ti.get("file_path", "") or "")
        else:
            hits = []
    except Exception:
        sys.exit(0)  # 守卫自身出错绝不阻断合法操作

    if hits:
        lines = ["⛔ 提交纪律守卫拦截(CLAUDE.md 作废级铁律):"]
        for rule, why in hits:
            lines.append(f"  [{rule}] {why}")
        lines.append("如本次确属任务明确要求的例外,请改用不触发该模式的等价命令,或与用户确认后再行。")
        sys.stderr.write("\n".join(lines) + "\n")
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()

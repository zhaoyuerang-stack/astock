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

拦的只有"确定性可正则匹配、且几乎从不该用"的几条:
  §11.1 禁一锅端     : git add -A/./--all/* , git commit -a/-am
  §11.4 禁擅改历史   : git reset --hard , git push --force/-f , git clean -f*
  R-DATA-001 旧口径  : 编辑/写入 data_full 目录
其余纪律(一commit一意图、核对diff、内容里 import data_full)仍交给
/commit skill + scripts/ci/check_*.py,本 hook 只做最后一道硬闸。
"""
import sys
import json
import re
import shlex


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


def check_bash(command):
    hits = []
    for sub, args in _git_calls(command):
        if sub == "add" and any(a in ("-A", "--all", ".", "*") for a in args):
            hits.append((
                "§11.1 禁一锅端",
                "`git add -A/./--all/*` 会把他人半成品 + 数据产物一并 stage。"
                "改用显式 `git add <file> ...`(只 stage 本次意图的文件),或走 /commit skill。",
            ))
        elif sub == "commit" and (
            "--all" in args
            or any(re.fullmatch(r"-[a-z]*a[a-z]*", a) for a in args)
        ):
            hits.append((
                "§11.1 禁一锅端",
                "`git commit -a/-am` 跳过显式 stage。先 `git add <file>` 再 "
                "`git commit -m`(或 /commit skill 的 heredoc 流程)。",
            ))
        elif sub == "reset" and "--hard" in args:
            hits.append((
                "§11.4 禁擅改历史",
                "共享工作树禁 `git reset --hard`(真实数据丢失风险)。"
                "确需时人工确认无他人 worktree 风险后再手动执行。",
            ))
        elif sub == "push" and any(
            a in ("-f", "--force") or a.startswith("--force-with-lease") for a in args
        ):
            hits.append((
                "§11.4 禁擅改历史",
                "禁 `git push --force`(覆盖远端他人提交)。",
            ))
        elif sub == "clean" and any(
            re.fullmatch(r"-[a-z]+", a) and "f" in a for a in args
        ):
            hits.append((
                "§11.4 禁擅改历史",
                "禁 `git clean -f*`(删除未追踪文件,曾致 .next 丢失事故)。"
                "先 `git clean -n` 干跑确认,确需再手动执行。",
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

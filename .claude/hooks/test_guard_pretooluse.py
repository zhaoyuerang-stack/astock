#!/usr/bin/env python3
"""guard_pretooluse 回归测试:把"该拦/该放"+"脚本缺失必须 fail-open"钉成契约。

跑法: python3 .claude/hooks/test_guard_pretooluse.py

两层:
  A. 逻辑层 —— 直接跑 guard 脚本,验证反模式拦/正常放。含对抗性审查补的
     等价绕过(add 全仓 pathspec、push +refspec 强推、clean 长选项、
     commit --amend、checkout -f、switch -C),每条都配一个"具体/安全形式"
     的对照确保不误伤。
  B. wrapper 层 —— 跑 settings.json 里的真命令(防配置漂移),验证:
       脚本缺失 -> exit 0(首次部署把整个仓锁死的那个 bug,最重要的一条),
       真命中经 wrapper -> exit 2,正常经 wrapper -> exit 0。
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(HOOK_DIR))  # .../.claude/hooks -> repo root
HOOK = os.path.join(HOOK_DIR, "guard_pretooluse.py")
SETTINGS = os.path.join(REPO_ROOT, ".claude", "settings.json")

BLOCK, PASS = 2, 0


def _run(argv, payload, env=None, shell=False):
    p = subprocess.run(
        argv,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        shell=shell,
    )
    return p.returncode


# ---- A. 逻辑层:直接跑脚本 ----
def _direct(payload):
    return _run([sys.executable, HOOK], payload)


def bash(cmd):
    return _direct({"tool_name": "Bash", "tool_input": {"command": cmd}})


def edit(fp):
    return _direct({"tool_name": "Edit", "tool_input": {"file_path": fp}})


LOGIC_CASES = [
    # --- 一锅端 add(裸 + 对抗审查补的等价 pathspec) ---
    (BLOCK, lambda: bash("git add -A"), "git add -A"),
    (BLOCK, lambda: bash("git add ."), "git add ."),
    (BLOCK, lambda: bash("git add --all"), "git add --all"),
    (BLOCK, lambda: bash("git add *"), "git add *"),
    (BLOCK, lambda: bash("git add ./"), "git add ./ (等价一锅端)"),
    (BLOCK, lambda: bash("git add :/"), "git add :/ (全仓 pathspec)"),
    (BLOCK, lambda: bash("git add :(top)"), "git add :(top) (magic pathspec)"),
    (BLOCK, lambda: bash("git add -- ."), "git add -- ."),
    # --- commit 一锅端 + amend 改历史 ---
    (BLOCK, lambda: bash('git commit -am "x"'), "git commit -am"),
    (BLOCK, lambda: bash("git commit -a"), "git commit -a"),
    (BLOCK, lambda: bash('git commit --all -m "x"'), "git commit --all"),
    (BLOCK, lambda: bash("git commit --amend --no-edit"), "git commit --amend (改历史)"),
    # --- reset / push 强推 ---
    (BLOCK, lambda: bash("git reset --hard HEAD~1"), "git reset --hard"),
    (BLOCK, lambda: bash("git push --force origin x"), "git push --force"),
    (BLOCK, lambda: bash("git push -f"), "git push -f"),
    (BLOCK, lambda: bash("git push origin +main"), "git push +main (+refspec 强推)"),
    (BLOCK, lambda: bash("git push origin +HEAD:main"), "git push +HEAD:main"),
    # --- clean 短簇 + 长选项 ---
    (BLOCK, lambda: bash("git clean -fd"), "git clean -fd"),
    (BLOCK, lambda: bash("git clean --force -d"), "git clean --force (长选项)"),
    # --- checkout/switch 丢弃工作区/强移分支 ---
    (BLOCK, lambda: bash("git checkout -f"), "git checkout -f (丢弃工作区)"),
    (BLOCK, lambda: bash("git checkout -B main"), "git checkout -B (强建分支)"),
    (BLOCK, lambda: bash("git checkout ."), "git checkout . (bulk 丢弃)"),
    (BLOCK, lambda: bash("git checkout -- ."), "git checkout -- . (bulk 丢弃)"),
    (BLOCK, lambda: bash("git switch -C main"), "git switch -C (强移分支)"),
    (BLOCK, lambda: bash("git switch --discard-changes main"), "git switch --discard-changes"),
    # --- 复合命令 ---
    (BLOCK, lambda: bash("cd x && git add -A"), "compound && git add -A"),
    (BLOCK, lambda: bash('git add foo.py && git commit -am "x"'), "compound commit -am"),
    (BLOCK, lambda: edit("/repo/data_full/cache.parquet"), "edit data_full/"),
    # --- 必须放行:具体/安全形式,防误伤 ---
    (PASS, lambda: bash("git add factor_research/x.py"), "git add <file>"),
    (PASS, lambda: bash("git add ./factor_research/x.py"), "git add ./path (具体)"),
    (PASS, lambda: bash("git add :/factor_research/x.py"), "git add :/path (具体)"),
    (PASS, lambda: bash("git add -p"), "git add -p"),
    (PASS, lambda: bash('git commit -m "fix"'), "git commit -m"),
    (PASS, lambda: bash('git commit -m "fix; bug -A ."'), "commit msg 含 ; -A ."),
    (PASS, lambda: bash("git status"), "git status"),
    (PASS, lambda: bash("git push origin main"), "git push (no force)"),
    (PASS, lambda: bash("git clean -n"), "git clean -n dry-run"),
    (PASS, lambda: bash("git checkout main"), "git checkout <branch> (切换)"),
    (PASS, lambda: bash("git checkout -b newbr"), "git checkout -b (建新分支,安全)"),
    (PASS, lambda: bash("git checkout -- foo.py"), "git checkout -- file (恢复单文件)"),
    (PASS, lambda: bash("git checkout HEAD -- foo.py"), "git checkout HEAD -- file"),
    (PASS, lambda: bash("git switch feature"), "git switch <branch>"),
    (PASS, lambda: bash("git switch -c newbranch"), "git switch -c (建新分支,安全)"),
    (PASS, lambda: bash('echo "git add -A is banned"'), "echo 含字面串"),
    (PASS, lambda: bash("git reset HEAD foo.py"), "git reset (soft)"),
    (PASS, lambda: edit("/repo/data_lake/cache.parquet"), "edit data_lake/"),
    (PASS, lambda: edit("/repo/data_full_report.md"), "edit data_full_report.md"),
]


# ---- B. wrapper 层:跑 settings.json 里的真命令 ----
def _wrapper_cmd():
    cfg = json.load(open(SETTINGS, encoding="utf-8"))
    return cfg["hooks"]["PreToolUse"][0]["hooks"][0]["command"]


def _wrapper(project_dir, payload):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=project_dir)
    return _run(_wrapper_cmd(), payload, env=env, shell=True)


def wrapper_cases():
    cmd_add_all = {"tool_name": "Bash", "tool_input": {"command": "git add -A"}}
    cmd_add_file = {"tool_name": "Bash", "tool_input": {"command": "git add foo.py"}}
    out = []
    # 最重要:脚本缺失 -> fail-open exit 0(首次部署锁死整个仓的那个 bug)
    empty = tempfile.mkdtemp(prefix="guard-empty-")
    try:
        out.append((PASS, _wrapper(empty, cmd_add_all),
                    "wrapper: 脚本缺失 -> fail-open 放行(关键回归)"))
    finally:
        shutil.rmtree(empty, ignore_errors=True)
    # 脚本在 -> 真命中经 wrapper 仍阻断
    out.append((BLOCK, _wrapper(REPO_ROOT, cmd_add_all),
                "wrapper: 脚本在 + git add -A -> 阻断"))
    # 脚本在 -> 正常命令经 wrapper 放行
    out.append((PASS, _wrapper(REPO_ROOT, cmd_add_file),
                "wrapper: 脚本在 + git add <file> -> 放行"))
    return out


def main():
    failed = 0
    for expect, call, desc in LOGIC_CASES:
        got = call()
        if got != expect:
            failed += 1
            print(f"FAIL  [logic]   expect={expect} got={got} | {desc}")
    for expect, got, desc in wrapper_cases():
        if got != expect:
            failed += 1
            print(f"FAIL  [wrapper] expect={expect} got={got} | {desc}")
    total = len(LOGIC_CASES) + 3
    if failed:
        print(f"\n{failed}/{total} FAILED")
        sys.exit(1)
    print(f"OK  {total}/{total} passed (logic {len(LOGIC_CASES)} + wrapper 3)")


if __name__ == "__main__":
    main()

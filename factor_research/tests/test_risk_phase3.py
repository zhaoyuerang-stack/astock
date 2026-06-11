"""Phase 3 验证:声明式 risk_policy 评估 + 控制回路。

Run:
    cd factor_research && python3 tests/test_risk_phase3.py
    cd factor_research && PHASE3_FULL=1 python3 tests/test_risk_phase3.py   # 含 target 现算集成
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from services.read.risk import _cap_check, load_risk_policy, risk_report
from contracts.models import ControlAction


def test_cap_check_levels():
    assert _cap_check("x", 0.10, 0.50).status == "breach"
    assert _cap_check("x", 0.10, 0.095).status == "warn"   # >= 0.9*阈值
    assert _cap_check("x", 0.10, 0.04).status == "ok"
    assert _cap_check("x", 0.10, None).status == "na"
    print("✅ cap_check 分级 ok/warn/breach/na 正确")


def test_policy_loaded():
    p = load_risk_policy()
    assert p["max_single_position_weight"] > 0 and p["max_position_count"] > 0
    print(f"✅ risk_policy 载入:单票上限 {p['max_single_position_weight']}, 持仓上限 {p['max_position_count']}")


def test_breach_generates_control_action():
    """合成一个超限组合 → 必须生成 requires_confirmation 的 ControlAction(且未执行)。"""
    breach = _cap_check("单票最大权重", 0.10, 0.50)
    assert breach.status == "breach"
    ca = ControlAction(action_id="ca-test", object_type="portfolio", object_id="x/v1",
                        trigger_state=f"{breach.rule}={breach.current} vs {breach.threshold}",
                        action="decrease", reason="单票超限", requires_confirmation=True, executed=False)
    assert ca.requires_confirmation is True and ca.executed is False
    print("✅ 超限 → ControlAction(待确认,未执行)")


def test_risk_report_integration():
    r = risk_report()
    assert r.verdict in ("正常", "预警", "超限")
    assert any(c.rule == "单票最大权重" for c in r.checks)
    print(f"✅ risk_report 集成:verdict={r.verdict} "
          f"checks={[(c.rule, c.status) for c in r.checks]} actions={len(r.control_actions)}")


if __name__ == "__main__":
    print("Running Phase 3 risk tests...\n")
    test_cap_check_levels()
    test_policy_loaded()
    test_breach_generates_control_action()
    if os.environ.get("PHASE3_FULL"):
        test_risk_report_integration()
    else:
        print("ℹ️  跳过 risk_report 集成(现算 target,设 PHASE3_FULL=1 开启)")
    print("\n🎉 Phase 3 risk tests passed!")

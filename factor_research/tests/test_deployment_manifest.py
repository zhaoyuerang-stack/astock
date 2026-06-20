"""Task 7: 部署清单 fail-closed —— registry 退役 / spec_hash 漂移机械阻断生产。"""
import json

import pytest

from runtime.deployment import (
    Deployment,
    DeploymentNotReady,
    load_active_deployment,
)

GOOD_HASH = "a" * 64
OTHER_HASH = "b" * 64


def _manifest(tmp_path, legs=None, status="active"):
    legs = legs if legs is not None else [
        {"family": "illiquidity", "version": "v3.1", "spec_hash": GOOD_HASH, "role": "equity_alpha"},
    ]
    p = tmp_path / "deploy.json"
    p.write_text(json.dumps({
        "deployment_id": "test-prod", "environment": "production", "status": status,
        "portfolio_policy": {"type": "regime_rotation", "defensive_cap": 1.0},
        "legs": legs,
    }), encoding="utf-8")
    return p


def _registry(status="在册", spec_hash=GOOD_HASH):
    def lookup(family, version):
        if (family, version) != ("illiquidity", "v3.1"):
            return None
        rec = {"version": version, "status": status}
        if spec_hash is not None:
            rec["executable_spec"] = {"spec_hash": spec_hash}
        return rec
    return lookup


def test_active_deployment_loads_when_registered_and_hash_matches(tmp_path):
    dep = load_active_deployment(_manifest(tmp_path), registry_lookup=_registry())
    assert isinstance(dep, Deployment)
    assert dep.legs[0].family == "illiquidity"
    assert dep.portfolio_policy["defensive_cap"] == 1.0


def test_leg_missing_spec_hash_field_is_not_ready(tmp_path):
    bad = [{"family": "illiquidity", "version": "v3.1", "role": "equity_alpha"}]
    with pytest.raises(DeploymentNotReady):
        load_active_deployment(_manifest(tmp_path, legs=bad), registry_lookup=_registry())


def test_retired_version_cannot_activate(tmp_path):
    with pytest.raises(DeploymentNotReady):
        load_active_deployment(_manifest(tmp_path), registry_lookup=_registry(status="退役"))


def test_candidate_version_cannot_activate(tmp_path):
    with pytest.raises(DeploymentNotReady):
        load_active_deployment(_manifest(tmp_path), registry_lookup=_registry(status="候选"))


def test_spec_hash_mismatch_blocks(tmp_path):
    with pytest.raises(DeploymentNotReady):
        load_active_deployment(_manifest(tmp_path), registry_lookup=_registry(spec_hash=OTHER_HASH))


def test_missing_registry_spec_hash_blocks(tmp_path):
    with pytest.raises(DeploymentNotReady):
        load_active_deployment(_manifest(tmp_path), registry_lookup=_registry(spec_hash=None))


def test_registry_status_change_blocks_next_load(tmp_path):
    path = _manifest(tmp_path)
    load_active_deployment(path, registry_lookup=_registry())          # 起初可加载
    with pytest.raises(DeploymentNotReady):                            # 退役后立即阻断
        load_active_deployment(path, registry_lookup=_registry(status="退役"))


def test_inactive_manifest_blocks(tmp_path):
    with pytest.raises(DeploymentNotReady):
        load_active_deployment(_manifest(tmp_path, status="paused"), registry_lookup=_registry())


def test_unregistered_leg_blocks(tmp_path):
    bad = [{"family": "ghost", "version": "v9", "spec_hash": GOOD_HASH, "role": "equity_alpha"}]
    with pytest.raises(DeploymentNotReady):
        load_active_deployment(_manifest(tmp_path, legs=bad), registry_lookup=_registry())


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-q"]))

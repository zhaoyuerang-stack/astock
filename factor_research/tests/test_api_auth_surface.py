"""API auth surface: heavy tasks require token; non-loopback reads require token.

Run: cd factor_research && python3 tests/test_api_auth_surface.py
     or: python3 -m pytest tests/test_api_auth_surface.py -q
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

TOKEN = "api-auth-unit-token"

from api.main import app  # noqa: E402
from services.actions import action_guard  # noqa: E402


@pytest.fixture(autouse=True)
def _force_action_token(monkeypatch):
    """Isolate from other test modules that also set ASTCOK_ACTION_TOKEN at import."""
    monkeypatch.setenv("ASTCOK_ACTION_TOKEN", TOKEN)


def _run(coro):
    return asyncio.run(coro)


def _async_client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


def test_public_health_and_openapi_unauthenticated():
    async def scenario():
        async with _async_client() as client:
            health = await client.get("/health")
            assert health.status_code == 200
            assert health.json()["status"] == "ok"

            openapi = await client.get("/openapi.json")
            assert openapi.status_code == 200

    _run(scenario())
    print("✅ public health/openapi remain unauthenticated")


def test_heavy_agent_and_backtest_require_action_token():
    async def scenario():
        async with _async_client() as client:
            # Agent POSTs
            for path, body in [
                ("/agent/ask", {"request": "hello", "context": {}, "messages": []}),
                ("/agent/sessions", {"page_context": "overview", "title": "t", "user_id": "local"}),
            ]:
                missing = await client.post(path, json=body)
                assert missing.status_code == 403, f"{path} missing token must 403"
                bad = await client.post(path, json=body, headers={"X-Action-Token": "wrong"})
                assert bad.status_code == 403, f"{path} bad token must 403"

            # Agent GETs
            missing_get = await client.get("/agent/sources")
            assert missing_get.status_code == 403

            # Backtest heavy GET
            missing_bt = await client.get("/backtest/run?start=2018-01-01&top_n=5")
            assert missing_bt.status_code == 403
            bad_bt = await client.get(
                "/backtest/run?start=2018-01-01&top_n=5",
                headers={"X-Action-Token": "wrong"},
            )
            assert bad_bt.status_code == 403

            # Correct token reaches business layer (must NOT be auth 403).
            with patch("api.routers.backtest.run_backtest") as mock_bt:
                from contracts.views import BacktestResult

                mock_bt.return_value = BacktestResult(
                    annual=0, vol=0, sharpe=0, maxdd=0, calmar=0, hit=False, n=0,
                    turnover_annual=0, cost_annual=0, yearly_returns={},
                    n_stocks=0, n_days=0, start="2018-01-01", end="2018-01-01",
                    family="illiquidity", version="v3.1",
                )
                ok_bt = await client.get(
                    "/backtest/run?start=2018-01-01&top_n=5",
                    headers={"X-Action-Token": TOKEN},
                )
                assert ok_bt.status_code == 200, ok_bt.text

            with patch("api.routers.agent.ask") as mock_ask:
                mock_ask.return_value = {
                    "output": {
                        "summary": "ok",
                        "evidence": [],
                        "risk": [],
                        "recommendation": [],
                        "next_actions": [],
                        "citations": [],
                        "source_types": [],
                        "suggested_navigation": [],
                        "confidence": 0.5,
                        "requires_human_confirmation": False,
                    },
                    "task_id": "t1",
                    "tool": None,
                    "risk": None,
                    "llm_ready": False,
                }
                ok_ask = await client.post(
                    "/agent/ask",
                    json={"request": "hello", "context": {}, "messages": []},
                    headers={"X-Action-Token": TOKEN},
                )
                assert ok_ask.status_code == 200, ok_ask.text

    _run(scenario())
    print("✅ agent/* and GET /backtest/run require X-Action-Token")


def test_non_loopback_read_requires_token():
    """If client is not loopback, research GETs must present action token."""
    import api.routers.settings as settings_router

    async def scenario():
        async with _async_client() as client:
            with (
                patch.object(action_guard, "is_loopback_request", return_value=False),
                patch.object(settings_router, "is_loopback_request", return_value=False),
            ):
                denied = await client.get("/governance")
                assert denied.status_code == 403, "non-loopback read without token must 403"

                denied_portfolio = await client.get("/portfolio")
                assert denied_portfolio.status_code == 403

                denied_paper = await client.get("/paper/plan")
                assert denied_paper.status_code == 403

                # Action-token bootstrap is loopback-only (route-level); cannot mint remotely.
                denied_token = await client.get("/settings/action-token")
                assert denied_token.status_code == 403

                allowed = await client.get("/health")  # public stays open
                assert allowed.status_code == 200

                # strategies is a read surface — valid token should pass middleware
                ok = await client.get(
                    "/strategies",
                    headers={"X-Action-Token": TOKEN},
                )
                # May be 200 with real data or service error; must not be auth 403
                assert ok.status_code != 403, ok.text

    _run(scenario())
    print("✅ non-loopback research reads require X-Action-Token")


def test_loopback_read_without_token_still_allowed():
    """Local research desk: ordinary GETs work without token on loopback."""

    async def scenario():
        async with _async_client() as client:
            # testclient is treated as loopback
            res = await client.get("/strategies")
            # auth layer must not 403; data may be empty list
            assert res.status_code != 403, res.text

    _run(scenario())
    print("✅ loopback research reads remain usable without token")


def test_is_public_path_helpers():
    assert action_guard.is_public_path("/health")
    assert action_guard.is_public_path("/miniapp/v1/home")
    assert action_guard.is_public_path("/openapi.json")
    assert not action_guard.is_public_path("/strategies")
    assert not action_guard.is_public_path("/agent/ask")
    print("✅ public path classifier")


if __name__ == "__main__":
    # Script mode: set env before app imports already happened — re-assert token.
    os.environ["ASTCOK_ACTION_TOKEN"] = TOKEN
    print("Running API auth surface tests...\n")
    test_is_public_path_helpers()
    test_public_health_and_openapi_unauthenticated()
    test_heavy_agent_and_backtest_require_action_token()
    test_non_loopback_read_requires_token()
    test_loopback_read_without_token_still_allowed()
    print("\n🎉 API auth surface tests passed!")

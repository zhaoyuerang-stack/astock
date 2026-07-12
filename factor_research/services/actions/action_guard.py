"""Local confirmation-token guard for write/costly UI actions + research-API access.

Security model (local research desk, not multi-tenant SaaS):

1. **Heavy / write actions** always require ``X-Action-Token`` (even on loopback).
2. **Research read APIs** allow loopback without a token; non-loopback clients must
   present a valid action token (fail-closed if API is bound beyond 127.0.0.1).
3. **Miniapp** keeps its own openid session auth and is excluded from (2).
4. **``GET /settings/action-token``** remains loopback-only so remote clients cannot
   bootstrap a token unless they already know ``ASTCOK_ACTION_TOKEN``.
"""
from __future__ import annotations

import os
import secrets
from datetime import date
from pathlib import Path

from fastapi import Header, HTTPException, Request

from lake.artifact_writer import append_jsonl, atomic_write_text

ROOT = Path(__file__).resolve().parents[2]
ACTION_TOKEN_ENV = "ASTCOK_ACTION_TOKEN"
ACTION_TOKEN_FILE = ROOT / "data_lake" / "agent" / "action_token"
ACTION_AUDIT_FILE = ROOT / "data_lake" / "agent" / "action_audit.jsonl"
ACTION_HEADER = "X-Action-Token"

# Paths that never require research-desk auth (health + product miniapp + OpenAPI).
PUBLIC_PATH_PREFIXES: tuple[str, ...] = (
    "/health",
    "/miniapp",
    "/docs",
    "/redoc",
    "/openapi.json",
)


def current_action_token() -> tuple[str, str]:
    """Return the local action token, creating a gitignored file token if needed."""
    env_token = os.environ.get(ACTION_TOKEN_ENV, "").strip()
    if env_token:
        return env_token, "env"

    if ACTION_TOKEN_FILE.exists():
        token = ACTION_TOKEN_FILE.read_text(encoding="utf-8").strip()
        if token:
            return token, "file"

    token = secrets.token_urlsafe(32)
    atomic_write_text(ACTION_TOKEN_FILE, token + "\n", mode=0o600)
    return token, "file"


def verify_action_token(token: str | None) -> None:
    expected, _source = current_action_token()
    supplied = (token or "").strip()
    if not supplied or not secrets.compare_digest(supplied, expected):
        raise HTTPException(status_code=403, detail=f"missing or invalid {ACTION_HEADER}")


def require_action_token(x_action_token: str | None = Header(default=None, alias=ACTION_HEADER)) -> None:
    """FastAPI dependency: always require a valid action token (heavy/write)."""
    verify_action_token(x_action_token)


def is_loopback_request(request: Request) -> bool:
    host = request.client.host if request.client else ""
    return host in {"127.0.0.1", "::1", "localhost", "testclient"}


def is_public_path(path: str) -> bool:
    """True for unauthenticated health/docs/miniapp routes."""
    if path in {"/", "/health", "/openapi.json"}:
        return True
    return any(path == prefix or path.startswith(prefix + "/") for prefix in PUBLIC_PATH_PREFIXES)


def require_local_or_action_token(request: Request) -> None:
    """Allow loopback freely; non-loopback must present a valid action token.

    Used by research-API middleware so bind-to-0.0.0.0 without a token is fail-closed
    for reads of registry / paper / governance surfaces.
    """
    if is_loopback_request(request):
        return
    token = request.headers.get(ACTION_HEADER)
    verify_action_token(token)


def audit_action(summary: str, detail: str = "", *, status: str = "accepted", actor: str = "human") -> None:
    """Append action audit without recording secrets or payload contents."""
    try:
        row = {
            "date": str(date.today()),
            "summary": summary,
            "detail": detail,
            "status": status,
            "actor": actor,
        }
        append_jsonl(ACTION_AUDIT_FILE, row)
    except OSError as exc:
        raise RuntimeError("failed to persist the action audit record") from exc

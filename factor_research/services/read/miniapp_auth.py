"""小程序微信登录认证 + 会话管理 + 用户额度。

职责(MINIPROGRAM_ARCHITECTURE §认证):
1. code → openid(调微信 API;无凭据时退开发模式)
2. openid → 用户档案(plan/token 余额,文件持久化)
3. access_token 会话存储(内存 + 过期清理;生产环境换 Redis)
4. FastAPI 依赖注入:get_current_user 从 Authorization 头解析 openid

不依赖业务策略层,只读 app_config/miniapp_settings.yaml。

⚠️ 镜像文件:实际运行于 factor_research/services/read/miniapp_auth.py,修改请同步两边。
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Optional

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

try:
    import yaml
except ImportError:
    yaml = None

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "app_config" / "miniapp_settings.yaml"

# 会话存储(进程内;多实例部署需换 Redis)
_SESSIONS: dict[str, dict] = {}

# HTTPBearer:auto_error=False → 未带 token 时不自动 403,由 get_current_user 显式拒绝
_SECURITY = HTTPBearer(auto_error=False)


def _load_config() -> dict:
    if yaml is None or not CONFIG_PATH.exists():
        return {}
    try:
        return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001
        return {}


_CONFIG = _load_config()
_WX = _CONFIG.get("wechat", {}) or {}
_SESSION_CFG = _CONFIG.get("session", {}) or {}
_QUOTA = _CONFIG.get("quota", {}) or {}
_STORAGE = _CONFIG.get("storage", {}) or {}

_DATA_DIR = ROOT / (_STORAGE.get("data_dir") or "data_lake/miniapp")
_USERS_DIR = _DATA_DIR / "users"


def _data_dir() -> Path:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    _USERS_DIR.mkdir(parents=True, exist_ok=True)
    return _DATA_DIR


# ─────────────────────────────────────────
# 微信登录
# ─────────────────────────────────────────

def wx_login(code: str) -> dict:
    """code → openid → session + 用户档案。

    无 appid/secret 时退开发模式:用 code 哈希造稳定 openid,便于本地联调。
    """
    appid = _WX.get("appid", "").strip()
    secret = _WX.get("secret", "").strip()

    if appid and secret:
        openid, session_key = _wx_code2session(appid, secret, code)
    else:
        # 开发模式:稳定伪 openid(同一 code → 同一 openid)
        openid = "dev_" + hashlib.sha256(code.encode("utf-8")).hexdigest()[:16]
        session_key = ""

    # 生成 token
    ts = int(time.time())
    access_token = _make_token(openid, "access", ts)
    refresh_token = _make_token(openid, "refresh", ts)

    ttl = int(_SESSION_CFG.get("ttl_seconds", 7200))
    _SESSIONS[access_token] = {
        "openid": openid,
        "session_key": session_key,
        "expire_at": ts + ttl,
    }

    user = _get_or_create_user(openid)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": user,
    }


def _wx_code2session(appid: str, secret: str, code: str) -> tuple[str, str]:
    """调微信 jscode2session 接口。"""
    import urllib.request
    import urllib.parse

    url = (
        "https://api.weixin.qq.com/sns/jscode2session?"
        + urllib.parse.urlencode({
            "appid": appid,
            "secret": secret,
            "js_code": code,
            "grant_type": "authorization_code",
        })
    )
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:  # noqa: S310
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"微信接口调用失败: {e}")

    if "errcode" in data and data["errcode"] != 0:
        raise HTTPException(
            status_code=400,
            detail=f"微信登录失败({data.get('errcode')}): {data.get('errmsg', '')}",
        )
    openid = data.get("openid")
    if not openid:
        raise HTTPException(status_code=400, detail="微信未返回 openid")
    return openid, data.get("session_key", "")


def _make_token(openid: str, kind: str, ts: int) -> str:
    raw = f"{kind}:{openid}:{ts}:{hashlib.sha256((openid+str(ts)).encode()).hexdigest()[:8]}"
    return raw


# ─────────────────────────────────────────
# 会话校验(FastAPI 依赖)
# ─────────────────────────────────────────

def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_SECURITY),
) -> dict:
    """从 Authorization: Bearer <token> 解析当前用户 openid。

    返回 {"openid": ...} 供下游服务用。token 过期/无效 → 401。
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail="未授权:缺少 access_token")

    token = credentials.credentials
    session = _SESSIONS.get(token)
    if not session:
        raise HTTPException(status_code=401, detail="access_token 无效或已过期")

    if session["expire_at"] < time.time():
        _SESSIONS.pop(token, None)
        raise HTTPException(status_code=401, detail="access_token 已过期,请重新登录")

    return {"openid": session["openid"]}


# ─────────────────────────────────────────
# 用户档案(文件持久化)
# ─────────────────────────────────────────

def _get_or_create_user(openid: str) -> dict:
    """读取或创建用户档案(含 plan / token 余额)。"""
    _data_dir()
    path = _USERS_DIR / f"{_safe_filename(openid)}.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass

    plan = (_QUOTA.get("default_plan") or "free")
    quota = _quota_for_plan(plan)
    user = {
        "id": "U" + openid[-8:],
        "openid": openid,
        "tenantId": "T-" + hashlib.sha256(openid.encode()).hexdigest()[:6].upper(),
        "nickname": "微信用户",
        "avatar": "K",
        "plan": plan,
        "tokenBalance": quota,
        "tokenQuota": quota,
        "createdAt": _today(),
    }
    path.write_text(json.dumps(user, ensure_ascii=False, indent=2), encoding="utf-8")
    return user


def get_user(openid: str) -> dict:
    """读用户档案(不存在则创建)。"""
    return _get_or_create_user(openid)


def save_user(user: dict) -> None:
    """写回用户档案(扣 token / 升级后调用)。"""
    _data_dir()
    openid = user.get("openid", "")
    if not openid:
        return
    path = _USERS_DIR / f"{_safe_filename(openid)}.json"
    path.write_text(json.dumps(user, ensure_ascii=False, indent=2), encoding="utf-8")


def deduct_token(openid: str, cost: int) -> int:
    """扣减 token,返回扣减后余额。余额不足 → raise HTTPException(402)。"""
    user = get_user(openid)
    balance = int(user.get("tokenBalance", 0))
    if balance < cost:
        raise HTTPException(
            status_code=402,
            detail=f"token 余额不足(需 {cost},剩余 {balance})",
        )
    user["tokenBalance"] = balance - cost
    save_user(user)
    return user["tokenBalance"]


# ─────────────────────────────────────────
# 辅助
# ─────────────────────────────────────────

def _quota_for_plan(plan: str) -> int:
    mapping = {
        "free": int(_QUOTA.get("free_quota", 3)),
        "pro": int(_QUOTA.get("pro_quota", 30)),
        "max": int(_QUOTA.get("max_quota", 120)),
    }
    return mapping.get(plan, mapping["free"])


def _safe_filename(name: str) -> str:
    return hashlib.sha256(name.encode("utf-8")).hexdigest()[:24]


def _today() -> str:
    return time.strftime("%Y-%m-%d", time.localtime())

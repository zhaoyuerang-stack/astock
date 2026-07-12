"""FastAPI app —— Phase 0 装配。

运行(cwd 必须是 factor_research/,以便 import services/contracts/引擎):
    cd factor_research && uvicorn api.main:app --reload
或直接:
    cd factor_research && python3 -m api.main

⚠️ 镜像文件:实际运行于 factor_research/api/main.py,修改请同步两边。
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routers import (agent, backtest, data, experiments, factors, miniapp, paper, portfolio,
                         risk, settings, state, strategies, system, trade_readiness, governance)
from services.actions.action_guard import (
    ACTION_HEADER,
    is_public_path,
    require_local_or_action_token,
)

app = FastAPI(title="Quant Research Platform API", version="0.0-phase0")

# Phase 1:允许本地 Next.js 开发服务器跨域调用。3001 是 3000 被占用时的 fallback。
# 小程序请求不校验 CORS(微信客户端发起),此处仍保留 Web 端跨域支持。
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def research_api_local_or_token(request: Request, call_next):
    """Research desk reads: loopback OK; non-loopback needs X-Action-Token.

    Heavy/write endpoints still enforce token via Depends(require_action_token)
    even on loopback. Miniapp / health / OpenAPI stay public (own auth or none).
    """
    path = request.url.path
    if is_public_path(path):
        return await call_next(request)
    # Action-token bootstrap itself is loopback-gated inside the route.
    if path == "/settings/action-token":
        return await call_next(request)
    try:
        require_local_or_action_token(request)
    except Exception as exc:
        # HTTPException from verify_action_token
        status = getattr(exc, "status_code", 403)
        detail = getattr(exc, "detail", f"missing or invalid {ACTION_HEADER}")
        return JSONResponse(status_code=status, content={"detail": detail})
    return await call_next(request)


app.include_router(strategies.router)
app.include_router(factors.router)
app.include_router(backtest.router)
app.include_router(data.router)
app.include_router(state.router)
app.include_router(portfolio.router)
app.include_router(paper.router)
app.include_router(risk.router)
app.include_router(experiments.router)
app.include_router(agent.router)
app.include_router(settings.router)
app.include_router(trade_readiness.router)
app.include_router(governance.router)
app.include_router(system.router)
app.include_router(miniapp.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "phase": 0}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8011)

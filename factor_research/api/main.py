"""FastAPI app —— Phase 0 装配。

运行(cwd 必须是 factor_research/,以便 import services/contracts/引擎):
    cd factor_research && uvicorn api.main:app --reload
或直接:
    cd factor_research && python3 -m api.main
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import backtest, data, factors, portfolio, risk, state, strategies

app = FastAPI(title="Quant Research Platform API", version="0.0-phase0")

# Phase 1:允许本地 Next.js 开发服务器(3000)跨域调用。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(strategies.router)
app.include_router(factors.router)
app.include_router(backtest.router)
app.include_router(data.router)
app.include_router(state.router)
app.include_router(portfolio.router)
app.include_router(risk.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "phase": 0}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)

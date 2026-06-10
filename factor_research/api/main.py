"""FastAPI app —— Phase 0 装配。

运行(cwd 必须是 factor_research/,以便 import services/contracts/引擎):
    cd factor_research && uvicorn api.main:app --reload
或直接:
    cd factor_research && python3 -m api.main
"""
from __future__ import annotations

from fastapi import FastAPI

from api.routers import backtest, factors, strategies

app = FastAPI(title="Quant Research Platform API", version="0.0-phase0")
app.include_router(strategies.router)
app.include_router(factors.router)
app.include_router(backtest.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "phase": 0}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)

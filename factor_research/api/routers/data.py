"""GET /data/quality —— 数据质量状态(含可选 DuckDB 即席复核)。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from contracts.views import DataQualityView, GlobalDataCoverageView, GlobalDataSourcesView, StockProfileView
from services.read.global_data import global_data_coverage, global_data_sources
from services.read.state import data_quality
from services.read.stocks import stock_profile

router = APIRouter(prefix="/data", tags=["data"])


@router.get("/quality", response_model=DataQualityView)
def quality(duckdb: bool = True) -> DataQualityView:
    return data_quality(with_duckdb=duckdb)


@router.get("/global/sources", response_model=GlobalDataSourcesView)
def global_sources() -> GlobalDataSourcesView:
    return global_data_sources()


@router.get("/global/coverage", response_model=GlobalDataCoverageView)
def global_coverage() -> GlobalDataCoverageView:
    return global_data_coverage()


@router.get("/stocks/{code}", response_model=StockProfileView)
def stock(code: str) -> StockProfileView:
    try:
        return StockProfileView(**stock_profile(code))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

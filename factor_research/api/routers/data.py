"""GET /data/quality —— 数据质量状态(含可选 DuckDB 即席复核)。"""
from __future__ import annotations

from fastapi import APIRouter

from contracts.views import DataQualityView
from services.read.state import data_quality

router = APIRouter(prefix="/data", tags=["data"])


@router.get("/quality", response_model=DataQualityView)
def quality(duckdb: bool = True) -> DataQualityView:
    return data_quality(with_duckdb=duckdb)

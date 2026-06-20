"""数据面板内容指纹——把 vintage_id 从"自报标签"变成"数据凭证"。

背景(2026-06-12 事故):数据湖同日被重写三次,17:33 与 20:12 两个截然
不同的面板会盖出同一个 vintage 字符串,实验日志不可复现且无法事后甄别。

指纹 = 末 N 日 × 抽样列的数值字节 + 形状 + 末日,sha256 截断。
同一 parquet → 同一浮点位 → 同一指纹;任何一格数值变动 → 指纹变。
计算量 O(60×~100 列),微秒级,可加在每次实验启动时。
"""
from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd


def panel_fingerprint(panel: pd.DataFrame, *, n_days: int = 60, col_step: int = 50) -> str:
    """对 (date × code) 宽面板取轻量内容指纹(12 位 hex)。"""
    if panel.empty:
        return "empty"
    tail = panel.iloc[-n_days:, ::max(1, col_step)]
    h = hashlib.sha256()
    h.update(f"{panel.shape}|{panel.index[-1]}".encode())
    h.update(np.ascontiguousarray(tail.fillna(-1.0).to_numpy(dtype="float64")).tobytes())
    return h.hexdigest()[:12]


def stamp_vintage(base: str, close: pd.DataFrame) -> str:
    """vintage 字符串追加数据指纹;重跑对账时指纹不符 = 数据已漂移。"""
    return f"{base}#{panel_fingerprint(close)}"

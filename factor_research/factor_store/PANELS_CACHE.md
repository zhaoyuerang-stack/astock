# factor_store 分区：panels cache vs 资产

`data_lake/factor_store/` 分两层语义（湖目录本身不入库，本说明在源码侧）：

| 子目录 | 语义 | 可否 GC | 可否作证据 |
| --- | --- | --- | --- |
| `panels/` | **cache 区**：AutoResearch DSL 因子面板磁盘缓存 | ✅ 可删 | ❌ |
| `manifests/` | **资产区**：正式登记的因子 manifest | ❌ 需审计 | ✅ |
| `scores/` | **资产区**：IC/ICIR 等评分 | ❌ 需审计 | ✅ |

## panels/ 缓存契约

- 写入方：`factors/autoresearch_dsl.py`（`cache_mode != "memory"`）
- 缓存 key：`name + params + data_signature + 源码 hash(_src…) + 数据 mtime(_mt…)`
- 改因子实现 → 源码 hash 变 → 自动 miss，不静默复用旧值
- GC：`python3 scripts/ops/gc_factor_panel_cache.py`（默认 dry-run；`--apply` 删非当前 mtime 代）

2026-07-12 dry-run 本机示例：keep ≈ 350 文件 / 18GB，delete ≈ 630 文件 / 21GB（旧 mtime 代）。

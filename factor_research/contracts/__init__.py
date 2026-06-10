"""产品数据契约层(纯 DTO,只依赖 pydantic + stdlib)。

- ``models``:SPEC §7 的 8 个核心数据模型(产品 write-schema,现在定义为统一契约)。
- ``views`` :Phase 0 API 的读/响应 DTO(端点实际返回的形状)。

分层铁律:``contracts`` 是叶子,不得 import 任何业务层(core/lake/factors/...
services/api)。守卫见 scripts/ci/check_layer_deps.py。
"""
from contracts import models, views  # noqa: F401

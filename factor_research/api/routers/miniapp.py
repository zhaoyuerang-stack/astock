"""小程序专用路由 —— /miniapp/v1/*

职责(MINIPROGRAM_ARCHITECTURE):
1. 内容脱敏(信号→研究候选,指令→观察池调整)—— 在 services.read.miniapp 内完成
2. 数据聚合(首页一次请求拿全)
3. openid 鉴权(access_token)
4. 免责声明注入

路由薄层:只做请求/响应模型 + 调 service + 错误码归一,不含业务逻辑。

⚠️ 镜像文件:实际运行于 factor_research/api/routers/miniapp.py,修改请同步两边。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from services.read.miniapp import (
    DISCLAIMER,
    get_audit_history,
    get_audit_result,
    get_home_data,
    get_portfolio_data,
    get_strategies_list,
)
from services.read.miniapp_auth import get_current_user, get_user, wx_login
from services.read.miniapp_audit import (
    parse_strategy_with_llm,
    submit_audit_job,
)

router = APIRouter(prefix="/miniapp/v1", tags=["miniapp"])


# ─────────────────────────────────────────
# 请求 / 响应模型
# ─────────────────────────────────────────

class LoginRequest(BaseModel):
    code: str = Field(..., description="wx.login() 返回的 code")


class ParseStrategyRequest(BaseModel):
    description: str


class SubmitAuditRequest(BaseModel):
    spec: dict


class SubscribeRequest(BaseModel):
    templates: list[str] = Field(default_factory=list)


# ─────────────────────────────────────────
# 认证
# ─────────────────────────────────────────

@router.post("/auth/login")
def login(req: LoginRequest):
    """微信登录:code → openid → access_token + 用户档案。"""
    try:
        return wx_login(req.code)
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"登录失败: {e}")


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    """当前用户档案(plan / token 余额)。"""
    return get_user(user["openid"])


# ─────────────────────────────────────────
# 首页聚合
# ─────────────────────────────────────────

@router.get("/home")
def home(user: dict = Depends(get_current_user)):
    """首页聚合:市场状态 + KPI + 候选池 + 预警 + 结论 + 用户额度。"""
    try:
        return get_home_data(user["openid"])
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"获取首页数据失败: {e}")


# ─────────────────────────────────────────
# 审计
# ─────────────────────────────────────────

@router.post("/audit/parse")
def parse_strategy(req: ParseStrategyRequest, user: dict = Depends(get_current_user)):
    """自然语言策略描述 → 结构化 strategy spec JSON。"""
    try:
        return parse_strategy_with_llm(req.description)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"解析失败: {e}")


@router.post("/audit/submit")
def submit_audit(req: SubmitAuditRequest, user: dict = Depends(get_current_user)):
    """提交审计任务(扣 token → 创建 job → 跑 9-Gate → 落盘)。"""
    try:
        return submit_audit_job(user["openid"], req.spec)
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"提交审计失败: {e}")


@router.get("/audit/result/{job_id}")
def audit_result(job_id: str, user: dict = Depends(get_current_user)):
    """查询审计结果(校验 openid 归属)。"""
    result = get_audit_result(job_id, user["openid"])
    if not result:
        raise HTTPException(status_code=404, detail="审计结果不存在或无权访问")
    return result


@router.get("/audit/history")
def audit_history(
    user: dict = Depends(get_current_user),
    limit: int = Query(20, ge=1, le=100),
):
    """审计历史列表(倒序)。"""
    return get_audit_history(user["openid"], limit=limit)


# ─────────────────────────────────────────
# 组合(脱敏)
# ─────────────────────────────────────────

@router.get("/portfolio")
def portfolio(user: dict = Depends(get_current_user)):
    """组合页:净值 + 当前持仓(脱敏) + 目标持仓 + 状态。"""
    try:
        return get_portfolio_data(user["openid"])
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"获取组合数据失败: {e}")


# ─────────────────────────────────────────
# 策略列表(脱敏)
# ─────────────────────────────────────────

@router.get("/strategies")
def strategies(user: dict = Depends(get_current_user)):
    """策略列表(脱敏后):只展示概要,不展示具体参数。"""
    try:
        return get_strategies_list(user["openid"])
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"获取策略列表失败: {e}")


# ─────────────────────────────────────────
# 订阅消息
# ─────────────────────────────────────────

@router.post("/subscribe")
def subscribe(req: SubscribeRequest, user: dict = Depends(get_current_user)):
    """记录用户订阅消息授权(MVP:仅记录,实际推送由 worker 触发)。"""
    # TODO: 落盘订阅记录,供日更 worker 推送订阅消息用
    return {
        "success": True,
        "templates": req.templates,
        "openid": user["openid"],
        "disclaimer": DISCLAIMER,
    }


# ─────────────────────────────────────────
# 研究使用声明
# ─────────────────────────────────────────

@router.get("/disclaimer")
def disclaimer():
    """研究使用声明(前端首次进入强制阅读用)。"""
    return {
        "title": "研究使用声明",
        "content": (
            "本工具为研究方法学分析工具,不构成任何投资建议。\n\n"
            "· 审计结果基于公开市场历史数据,可能存在延迟或错误\n"
            "· 过去表现不代表未来收益\n"
            "· DSR/9-Gate 等指标为统计结论,不构成投资建议\n"
            "· 用户应自行承担依据本工具结果做出的任何决策风险\n\n"
            "继续使用即表示您已阅读并同意以上声明。"
        ),
        "requireReadSeconds": 20,
        "version": "1.0",
    }

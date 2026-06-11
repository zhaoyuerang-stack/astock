"""LLM 适配器 —— Agent 的"大脑",多 provider、可插拔、零新依赖(stdlib HTTP)。

接各种模型:绝大多数(DeepSeek/通义/Kimi/GLM/Ollama/vLLM/OpenAI)都是 **OpenAI 兼容**
`/v1/chat/completions` → 一个 OpenAICompatAdapter 覆盖;Anthropic 走原生 /v1/messages。
切模型只改 app_config/settings.yaml 的 ai_model 段(provider/model/base_url/api_key_env)。

安全铁律:LLM **只做** route(选白名单工具)+ synthesize(把工具结果写成解读)——
**永不执行工具、永不下单**。不越权门在 planner 里,LLM 影响不到(见 planner.py)。
无 key/无配置 → NullAdapter,planner 退回确定性关键词路由。
"""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _ai_cfg() -> dict:
    try:
        import yaml
    except ImportError:
        return {}
    p = ROOT / "app_config" / "settings.yaml"
    if not p.exists():
        return {}
    return (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("ai_model") or {}


def _http_post(url: str, headers: dict, payload: dict, timeout: int = 30) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                 headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _norm_openai_base(url: str) -> str:
    """容错 base_url:去空白/尾斜杠;若误粘了完整端点则剥掉,得到可拼 /chat/completions 的 base。

    都正规化到末尾不带 /chat/completions:
      https://api.deepseek.com/v1/chat/completions → https://api.deepseek.com/v1
      https://api.deepseek.com/v1/                  → https://api.deepseek.com/v1
      https://api.deepseek.com/v1/chat/completions/ → https://api.deepseek.com/v1
    """
    u = (url or "").strip().rstrip("/")
    # http→https(公网 API 必须 https;本地 ollama/127.0.0.1 保留 http)
    if u.startswith("http://") and "localhost" not in u and "127.0.0.1" not in u:
        u = "https://" + u[len("http://"):]
    for suf in ("/chat/completions", "/v1/chat/completions"):
        if u.endswith(suf):
            u = u[: -len(suf)]
            break
    return u.rstrip("/")


# ── 适配器接口 ─────────────────────────────────────────────────────────────────
class LLMAdapter:
    name = "null"
    model = ""

    def available(self) -> bool:
        return False

    def route(self, request: str, context: dict, tool_names: list[str]) -> str | None:
        """选一个白名单工具名,或 None(planner 走确定性 fallback)。"""
        return None

    def synthesize(self, request: str, context: dict, tool_name: str, data) -> str | None:
        """把工具结果写成中文解读,或 None(planner 用确定性 _summarize)。"""
        return None

    def complete(self, system: str, user: str, max_tokens: int = 2000) -> str | None:
        """通用补全(如 AutoResearch 候选生成)。不可用 / 失败 → None。"""
        return None

    def ping(self) -> bool:
        """最小连通测试。子类做一次 1-token 调用,失败抛异常。"""
        return False


class NullAdapter(LLMAdapter):
    pass


class OpenAICompatAdapter(LLMAdapter):
    """OpenAI 兼容(OpenAI / DeepSeek / 通义 Qwen / Kimi / GLM / Ollama / vLLM …)。"""
    name = "openai_compatible"

    def __init__(self, model: str, base_url: str, api_key: str):
        self.model = model
        self.base_url = _norm_openai_base(base_url)
        self.api_key = api_key

    def available(self) -> bool:
        return bool(self.api_key and self.model and self.base_url)

    def _chat(self, system: str, user: str, max_tokens: int = 1200) -> str:
        # 推理(thinking)模型会先花 token 思考,max_tokens 需留足,否则 content 为空
        url = f"{self.base_url}/chat/completions"
        try:
            data = _http_post(
                url,
                {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                {"model": self.model, "temperature": 0.2, "max_tokens": max_tokens,
                 "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]},
            )
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"HTTP {e.code} @ {url}(检查 base_url/model)") from e
        return data["choices"][0]["message"]["content"].strip()

    def route(self, request, context, tool_names):
        try:
            ans = self._chat(
                f"你是路由器。只能从以下工具里选一个:{tool_names}。只回工具名,或回 none。",
                f"页面={context.get('current_page','')} 请求={request}", max_tokens=256).strip().strip('"').lower()
            # 推理模型可能带思考前缀,取末尾出现的工具名
            for t in tool_names:
                if t in ans:
                    return t
            return None
        except Exception:  # noqa: BLE001
            return None

    def synthesize(self, request, context, tool_name, data):
        try:
            return self._chat(
                "你是量化研究副驾驶。根据工具返回的 JSON 写简洁中文解读,不得编造任何数字。",
                f"问题:{request}\n工具:{tool_name}\n数据:{json.dumps(data, ensure_ascii=False)[:3000]}")
        except Exception:  # noqa: BLE001
            return None

    def complete(self, system, user, max_tokens=2000):
        try:
            return self._chat(system, user, max_tokens=max_tokens)
        except Exception:  # noqa: BLE001
            return None

    def ping(self) -> bool:
        self._chat("你是助手", "回复:通", max_tokens=64)
        return True


class AnthropicAdapter(LLMAdapter):
    """Anthropic 原生 /v1/messages(Claude)。"""
    name = "anthropic"

    def __init__(self, model: str, api_key: str, base_url: str = "https://api.anthropic.com"):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def available(self) -> bool:
        return bool(self.api_key and self.model)

    def _msg(self, system: str, user: str, max_tokens: int = 1200) -> str:
        url = f"{self.base_url}/v1/messages"
        try:
            data = _http_post(
                url,
                {"x-api-key": self.api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
                {"model": self.model, "system": system, "max_tokens": max_tokens,
                 "messages": [{"role": "user", "content": user}]},
            )
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"HTTP {e.code} @ {url}(检查 base_url/model)") from e
        return data["content"][0]["text"].strip()

    def route(self, request, context, tool_names):
        try:
            ans = self._msg(f"只能从工具 {tool_names} 选一个,只回工具名或 none。",
                            f"页面={context.get('current_page','')} 请求={request}", max_tokens=256).strip().strip('"').lower()
            for t in tool_names:
                if t in ans:
                    return t
            return None
        except Exception:  # noqa: BLE001
            return None

    def synthesize(self, request, context, tool_name, data):
        try:
            return self._msg("你是量化研究副驾驶,根据 JSON 写简洁中文解读,不得编造数字。",
                             f"问题:{request}\n工具:{tool_name}\n数据:{json.dumps(data, ensure_ascii=False)[:3000]}")
        except Exception:  # noqa: BLE001
            return None

    def complete(self, system, user, max_tokens=2000):
        try:
            return self._msg(system, user, max_tokens=max_tokens)
        except Exception:  # noqa: BLE001
            return None

    def ping(self) -> bool:
        self._msg("你是助手", "回复:通", max_tokens=64)
        return True


# ── 运行时配置(UI 可写;key 存 gitignored 文件,绝不进 git/不回传明文)─────────────
_RUNTIME = ROOT / "data_lake" / "agent" / "llm_config.json"


def load_runtime_config() -> dict:
    if _RUNTIME.exists():
        try:
            return json.loads(_RUNTIME.read_text(encoding="utf-8"))
        except ValueError:
            return {}
    return {}


def save_runtime_config(provider: str, model: str, base_url: str, api_key: str | None) -> dict:
    """保存到 gitignored 文件(权限 600)。api_key 传 None 表示保留原 key。"""
    _RUNTIME.parent.mkdir(parents=True, exist_ok=True)
    cur = load_runtime_config()
    cfg = {
        "provider": (provider or "none"),
        "model": (model or ""),
        "base_url": (base_url or ""),
        "api_key": (api_key if api_key is not None else cur.get("api_key", "")),
    }
    _RUNTIME.write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    try:
        os.chmod(_RUNTIME, 0o600)
    except OSError:
        pass
    return cfg


def effective_config() -> dict:
    """settings.yaml(默认)+ 运行时文件(UI 写,优先)合并。"""
    merged = dict(_ai_cfg())
    for k, v in load_runtime_config().items():
        if v not in (None, ""):
            merged[k] = v
    return merged


def _resolve_key(cfg: dict) -> str:
    # 运行时文件的 api_key 优先;否则按 api_key_env 取环境变量
    return load_runtime_config().get("api_key") or os.environ.get(cfg.get("api_key_env") or "") or ""


def get_adapter() -> LLMAdapter:
    cfg = effective_config()
    provider = (cfg.get("provider") or "none").lower()
    key = _resolve_key(cfg)
    model = cfg.get("model") or ""
    if provider == "anthropic" and key and model:
        return AnthropicAdapter(model, key, cfg.get("base_url") or "https://api.anthropic.com")
    if provider in ("openai", "openai_compatible") and key and model and cfg.get("base_url"):
        return OpenAICompatAdapter(model, cfg["base_url"], key)
    return NullAdapter()


def llm_ready() -> bool:
    return get_adapter().available()


def ai_model_info() -> dict:
    cfg = effective_config()
    a = get_adapter()
    return {
        "provider": cfg.get("provider", "none"),
        "model": cfg.get("model", ""),
        "base_url": cfg.get("base_url", ""),
        "has_key": bool(_resolve_key(cfg)),
        "llm_ready": a.available(),
        "mode": "规则式" if not a.available() else f"LLM:{a.name}",
    }


def llm_config_masked() -> dict:
    """给前端的当前配置 —— key 永不回传明文,只给提示。"""
    cfg = effective_config()
    key = _resolve_key(cfg)
    hint = (key[:3] + "…" + key[-2:]) if len(key) > 6 else ("已设置" if key else "")
    return {
        "provider": cfg.get("provider", "none"),
        "model": cfg.get("model", ""),
        "base_url": cfg.get("base_url", ""),
        "has_key": bool(key),
        "key_hint": hint,
        "llm_ready": get_adapter().available(),
    }


def test_llm() -> dict:
    a = get_adapter()
    if not a.available():
        return {"ok": False, "message": "未配置 provider/model/base_url/key,或缺一"}
    try:
        a.ping()
        return {"ok": True, "message": f"连通 {a.name}:{a.model}"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "message": f"失败:{type(e).__name__}: {e}"}

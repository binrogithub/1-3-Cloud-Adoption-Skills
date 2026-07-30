"""LiteLLM pre-call router for GLM execution, OpenRouter vision, and Opus reasoning."""

import json
import os
import re

from litellm.integrations.custom_logger import CustomLogger

GLM_MODEL = os.getenv("SMART_ROUTER_GLM_MODEL", "claude-*")
VISION_MODEL = os.getenv("SMART_ROUTER_VISION_MODEL", "vision-openrouter")
PREMIUM_MODEL = os.getenv("SMART_ROUTER_PREMIUM_MODEL", "premium-openrouter")
PREMIUM_CONTEXT_THRESHOLD = int(os.getenv("SMART_ROUTER_PREMIUM_CONTEXT_THRESHOLD", "198000"))

_VISION_RE = re.compile(
    r"\b(?:ui|ux|visual\s+design|design\s+system|landing\s+page)\b|"
    r"视觉设计|界面设计|网页设计|设计(?:网页|页面|界面|UI|UX)|设计系统|"
    r"\bdesign\s+(?:visual|de\s+interface|de\s+ui|de\s+ux)\b|"
    r"\bdiseño\s+(?:visual|de\s+interfaz|de\s+ui|de\s+ux)\b",
    re.IGNORECASE,
)

_PREMIUM_RE = re.compile(
    r"\b(?:system|software|solution|technical|application|cloud|security)\s+architecture\b|"
    r"\barchitecture\s+(?:design|planning|review)\b|"
    r"\b(?:database|schema|data\s+model|api|microservice|infrastructure)\s+design\b|"
    r"\b(?:complex\s+debug|security\s+review|production\s+incident|infrastructure\s+change)\b|"
    r"系统架构|软件架构|架构(?:设计|规划|评审)|数据库(?:架构|结构|表结构)?设计|"
    r"设计(?:数据库|表结构|数据模型|系统架构|软件架构)|"
    r"复杂(?:调试|排错|故障诊断)|安全(?:审查|评审|分析)|生产(?:事故|故障|事件)|"
    r"\b(?:arquitetura|desenho)\s+(?:de\s+)?(?:sistema|software|solução|solucao|"
    r"aplicação|aplicacao|nuvem|segurança|seguranca|banco\s+de\s+dados|dados|api|"
    r"microsserviços|microsservicos|infraestrutura)\b|"
    r"\b(?:desenhe|projete|planeje|revise)\b.{0,60}\b(?:arquitetura|banco\s+de\s+dados|"
    r"modelo\s+de\s+dados|microsserviços|microsservicos)\b|"
    r"\b(?:depuração|depuracao|diagnóstico|diagnostico)\s+complex[oa]\b|"
    r"\b(?:revisão|revisao|análise|analise)\s+de\s+segurança\b|"
    r"\bincidente\s+(?:de|em)\s+produção\b|"
    r"\b(?:arquitectura|diseño)\s+(?:de\s+)?(?:sistema|software|solución|solucion|"
    r"aplicación|aplicacion|nube|seguridad|base\s+de\s+datos|datos|api|"
    r"microservicios|infraestructura)\b|"
    r"\b(?:diseña|diseñe|planifica|planifique|revisa|revise)\b.{0,60}"
    r"\b(?:arquitectura|base\s+de\s+datos|modelo\s+de\s+datos|microservicios)\b|"
    r"\b(?:depuración|depuracion|diagnóstico|diagnostico)\s+complej[oa]\b|"
    r"\b(?:revisión|revision|análisis|analisis)\s+de\s+seguridad\b|"
    r"\bincidente\s+(?:de|en)\s+producción\b",
    re.IGNORECASE,
)


def _has_image(data):
    for message in data.get("messages") or data.get("input") or []:
        if not isinstance(message, dict):
            continue
        for block in message.get("content") if isinstance(message.get("content"), list) else []:
            if isinstance(block, dict) and block.get("type") in {"image", "image_url", "input_image"}:
                return True
    return False


def _latest_user_text(data):
    for key in ("messages", "input"):
        for message in reversed(data.get(key) or []):
            if not isinstance(message, dict) or message.get("role") != "user":
                continue
            content = message.get("content", "")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                return " ".join(
                    block.get("text", "")
                    for block in content
                    if isinstance(block, dict) and block.get("type") in {"text", "input_text"}
                )
    return ""


def _estimate_tokens(data):
    messages = data.get("messages") or data.get("input") or []
    try:
        from litellm import token_counter

        estimate = int(token_counter(model=data.get("model"), messages=messages))
    except Exception:
        estimate = len(json.dumps(messages, ensure_ascii=False, default=str)) // 4
    for key in ("system", "instructions", "tools"):
        if data.get(key):
            estimate += max(1, len(json.dumps(data[key], ensure_ascii=False, default=str)) // 4)
    return estimate


def route_request(data):
    """Mutate and return a request according to the documented hard rules."""
    original = data.get("model", GLM_MODEL)
    if _has_image(data):
        target, reason = VISION_MODEL, "image"
    else:
        tokens = _estimate_tokens(data)
        text = _latest_user_text(data)
        if tokens > PREMIUM_CONTEXT_THRESHOLD:
            target, reason = PREMIUM_MODEL, "context_over_198k"
        elif _VISION_RE.search(text):
            target, reason = VISION_MODEL, "visual_ui"
        elif _PREMIUM_RE.search(text):
            target, reason = PREMIUM_MODEL, "premium_reasoning"
        else:
            target, reason = original, "glm_execution"
    data["model"] = target
    metadata = data.setdefault("metadata", {})
    metadata["smart_router"] = {
        "original_model": original,
        "target_model": target,
        "route_reason": reason,
        "context_threshold": PREMIUM_CONTEXT_THRESHOLD,
        "languages": ["zh", "en", "pt-BR", "es"],
    }
    return data


class SmartRouter(CustomLogger):
    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        return route_request(data)


proxy_handler_instance = SmartRouter()

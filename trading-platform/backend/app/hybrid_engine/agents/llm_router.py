"""LLM Router — Multi-Model Intelligence Layer

Routes tasks between two NVIDIA Nemotron models:
  - SUPER (120B): news analysis, macro reasoning, complex events, commodities
  - NANO  (30B):  entity extraction, keyword detection, basic sentiment, JSON cleanup

Routing logic:
  1. Classify task type from input
  2. Assign model (NANO first for lightweight tasks)
  3. If NANO result confidence < 0.6 → escalate to SUPER
  4. Return structured output with model_used, task_type, result, confidence

⚠️ SAFETY: Never outputs BUY/SELL directly. All outputs are classification/scoring only.
"""
from __future__ import annotations

import json
import time
from enum import Enum
from typing import Any

import httpx
import redis.asyncio as aioredis

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

# ── Model identifiers ─────────────────────────────────────────────────────────

SUPER_MODEL = getattr(settings, "nvidia_super_model", "nvidia/nemotron-3-super-120b-a12b")
NANO_MODEL = getattr(settings, "nvidia_nano_model", "nvidia/nemotron-3-nano-30b-a3b")
BASE_URL = getattr(settings, "nvidia_base_url", "https://integrate.api.nvidia.com/v1")
API_KEY = getattr(settings, "nvidia_api_key", "")

_CHAT_URL = f"{BASE_URL}/chat/completions"
_TIMEOUT_NANO = 8    # seconds — nano must be fast
_TIMEOUT_SUPER = 20  # seconds — super gets more time
_CACHE_TTL = 3600    # 1 hour Redis cache per unique input hash
_ESCALATION_CONFIDENCE = 0.6  # escalate to SUPER if NANO confidence < this


# ── Task types ────────────────────────────────────────────────────────────────

class TaskType(str, Enum):
    # → SUPER model
    NEWS_ANALYSIS = "news_analysis"
    MACRO_ANALYSIS = "macro_analysis"
    COMPLEX_REASONING = "complex_reasoning"
    MULTI_SOURCE_ANALYSIS = "multi_source_analysis"
    HIGH_IMPACT_EVENT = "high_impact_event"
    COMMODITY_INTELLIGENCE = "commodity_intelligence"
    # → NANO model
    ENTITY_EXTRACTION = "entity_extraction"
    KEYWORD_DETECTION = "keyword_detection"
    BASIC_SENTIMENT = "basic_sentiment"
    TEXT_CLEANING = "text_cleaning"
    JSON_FORMATTING = "json_formatting"


_SUPER_TASKS = {
    TaskType.NEWS_ANALYSIS,
    TaskType.MACRO_ANALYSIS,
    TaskType.COMPLEX_REASONING,
    TaskType.MULTI_SOURCE_ANALYSIS,
    TaskType.HIGH_IMPACT_EVENT,
    TaskType.COMMODITY_INTELLIGENCE,
}

_NANO_TASKS = {
    TaskType.ENTITY_EXTRACTION,
    TaskType.KEYWORD_DETECTION,
    TaskType.BASIC_SENTIMENT,
    TaskType.TEXT_CLEANING,
    TaskType.JSON_FORMATTING,
}

# ── Prompts per task type ─────────────────────────────────────────────────────

_PROMPTS: dict[TaskType, str] = {
    TaskType.NEWS_ANALYSIS: (
        "You are a senior financial analyst for Indian and global markets. "
        "Analyze this news article deeply. Consider market context, sector impact, "
        "regulatory implications, and investor sentiment. "
        'Return ONLY valid JSON: {"asset": "TICKER", "sentiment": FLOAT[-1,1], '
        '"impact": INT[0,100], "confidence": FLOAT[0,1], '
        '"time_horizon": "short|medium|long", "reasoning": "MAX_80_WORDS", '
        '"affected_sectors": ["sector1"], "risk_factors": ["factor1"]}'
    ),
    TaskType.MACRO_ANALYSIS: (
        "You are a macro economist analyzing global market conditions. "
        "Assess the macro signal and its impact on Indian equities, gold, and crypto. "
        'Return ONLY valid JSON: {"risk_regime": "risk_on|risk_off|neutral", '
        '"equity_bias": FLOAT[-1,1], "gold_bias": FLOAT[-1,1], '
        '"confidence": FLOAT[0,1], "key_driver": "MAX_30_WORDS"}'
    ),
    TaskType.HIGH_IMPACT_EVENT: (
        "You are a financial event analyst. This is a HIGH IMPACT event (Fed decision, "
        "earnings surprise, geopolitical shock, regulatory action). "
        "Analyze immediate and medium-term market implications. "
        'Return ONLY valid JSON: {"asset": "TICKER_OR_INDEX", "sentiment": FLOAT[-1,1], '
        '"impact": INT[0,100], "confidence": FLOAT[0,1], '
        '"time_horizon": "short|medium|long", "event_type": "fed|earnings|geo|regulatory|other", '
        '"reasoning": "MAX_80_WORDS"}'
    ),
    TaskType.COMMODITY_INTELLIGENCE: (
        "You are a commodity analyst specializing in gold, silver, and crude oil. "
        "Analyze the input considering USD strength, inflation, geopolitical risk, "
        "and India-specific demand factors. "
        'Return ONLY valid JSON: {"asset": "GOLD|SILVER|CRUDEOIL", '
        '"bias": "bullish|bearish|neutral", "confidence": FLOAT[0,1], '
        '"sentiment": FLOAT[-1,1], "key_driver": "MAX_30_WORDS"}'
    ),
    TaskType.COMPLEX_REASONING: (
        "You are a quantitative analyst. Analyze the multi-factor input and provide "
        "a structured assessment. "
        'Return ONLY valid JSON: {"asset": "TICKER", "sentiment": FLOAT[-1,1], '
        '"impact": INT[0,100], "confidence": FLOAT[0,1], '
        '"time_horizon": "short|medium|long", "reasoning": "MAX_80_WORDS"}'
    ),
    TaskType.MULTI_SOURCE_ANALYSIS: (
        "You are a financial intelligence analyst. Multiple data sources are provided. "
        "Synthesize them into a coherent signal. "
        'Return ONLY valid JSON: {"asset": "TICKER", "sentiment": FLOAT[-1,1], '
        '"impact": INT[0,100], "confidence": FLOAT[0,1], '
        '"time_horizon": "short|medium|long", "consensus": "agree|disagree|mixed", '
        '"reasoning": "MAX_80_WORDS"}'
    ),
    TaskType.ENTITY_EXTRACTION: (
        "Extract all financial entities from the text. "
        'Return ONLY valid JSON: {"tickers": ["NSE:RELIANCE"], '
        '"commodities": ["GOLD"], "indices": ["NIFTY50"], '
        '"crypto": ["BTC"], "companies": ["Reliance Industries"]}'
    ),
    TaskType.KEYWORD_DETECTION: (
        "Detect financial sentiment keywords in the text. "
        'Return ONLY valid JSON: {"bullish_keywords": ["rally", "beat"], '
        '"bearish_keywords": ["crash", "miss"], '
        '"sentiment": FLOAT[-1,1], "confidence": FLOAT[0,1]}'
    ),
    TaskType.BASIC_SENTIMENT: (
        "Score the financial sentiment of this text. "
        'Return ONLY valid JSON: {"sentiment": FLOAT[-1,1], '
        '"confidence": FLOAT[0,1], "label": "bullish|bearish|neutral"}'
    ),
    TaskType.TEXT_CLEANING: (
        "Clean and normalize this financial text. Remove noise, fix formatting. "
        'Return ONLY valid JSON: {"cleaned_text": "...", "language": "en|hi|other"}'
    ),
    TaskType.JSON_FORMATTING: (
        "Parse and validate this JSON. Fix any formatting issues. "
        "Return ONLY the corrected valid JSON object."
    ),
}


# ── Task classifier ───────────────────────────────────────────────────────────

_HIGH_IMPACT_KEYWORDS = {
    "fed", "rbi", "rate", "gdp", "inflation", "war", "sanctions", "ban",
    "earnings", "quarterly", "results", "profit", "loss", "merger", "acquisition",
    "ipo", "sebi", "geopolit", "nuclear", "crisis", "default", "bankruptcy",
}

_COMMODITY_KEYWORDS = {"gold", "silver", "crude", "oil", "mcx", "comex", "bullion"}


def classify_task(text: str, hint: TaskType | None = None) -> TaskType:
    """Classify the task type from input text and optional hint."""
    if hint is not None:
        return hint

    lower = text.lower()
    word_set = set(lower.split())

    # Commodity check first (specific domain)
    if any(kw in lower for kw in _COMMODITY_KEYWORDS):
        return TaskType.COMMODITY_INTELLIGENCE

    # High-impact event check
    if any(kw in lower for kw in _HIGH_IMPACT_KEYWORDS):
        return TaskType.HIGH_IMPACT_EVENT

    # Long text → full news analysis
    if len(text) > 300:
        return TaskType.NEWS_ANALYSIS

    # Short text with entities → entity extraction
    if len(text) < 100:
        return TaskType.ENTITY_EXTRACTION

    # Default for medium-length financial text
    return TaskType.BASIC_SENTIMENT


# ── Core LLM caller ───────────────────────────────────────────────────────────

async def _call_model(
    model: str,
    system_prompt: str,
    user_content: str,
    timeout: float,
) -> tuple[dict[str, Any], float]:
    """Call NVIDIA API. Returns (parsed_result, latency_seconds)."""
    t0 = time.monotonic()
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(
            _CHAT_URL,
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                "max_tokens": 300,
                "temperature": 0.05,
            },
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json",
            },
        )
        resp.raise_for_status()

    latency = time.monotonic() - t0
    content = resp.json()["choices"][0]["message"]["content"].strip()

    # Strip markdown fences
    if content.startswith("```"):
        content = content.split("```")[1].lstrip("json").strip()

    return json.loads(content), latency


def _extract_confidence(result: dict[str, Any]) -> float:
    """Extract confidence from any result shape."""
    return float(result.get("confidence", 0.5))


def _validate_result(result: dict[str, Any], task_type: TaskType) -> bool:
    """Basic structural validation of LLM output."""
    if task_type in (TaskType.NEWS_ANALYSIS, TaskType.HIGH_IMPACT_EVENT, TaskType.COMPLEX_REASONING):
        return "sentiment" in result and "confidence" in result
    if task_type == TaskType.MACRO_ANALYSIS:
        return "risk_regime" in result and "confidence" in result
    if task_type == TaskType.COMMODITY_INTELLIGENCE:
        return "bias" in result and "confidence" in result
    if task_type == TaskType.ENTITY_EXTRACTION:
        return "tickers" in result or "companies" in result
    if task_type in (TaskType.BASIC_SENTIMENT, TaskType.KEYWORD_DETECTION):
        return "sentiment" in result
    return True  # permissive for text_cleaning, json_formatting


# ── Public router ─────────────────────────────────────────────────────────────

async def route(
    text: str,
    task_hint: TaskType | None = None,
    redis: aioredis.Redis | None = None,
    extra_context: str = "",
) -> dict[str, Any]:
    """
    Main entry point. Routes to NANO or SUPER based on task type.
    Escalates NANO → SUPER if confidence < threshold.

    Returns:
        {
            "model_used": "120b|30b",
            "task_type": str,
            "result": {...},
            "confidence": float,
            "latency_ms": int,
            "escalated": bool
        }
    """
    task_type = classify_task(text, task_hint)
    cache_key = f"llm:router:{task_type}:{hash(text + extra_context)}"

    # Check Redis cache
    if redis is not None:
        cached = await redis.get(cache_key)
        if cached:
            try:
                data = json.loads(cached)
                data["from_cache"] = True
                return data
            except json.JSONDecodeError:
                pass

    user_content = f"{extra_context}\n{text}".strip() if extra_context else text
    system_prompt = _PROMPTS[task_type]
    escalated = False
    model_label = "30b"
    result: dict[str, Any] = {}
    latency_ms = 0

    # ── Step 1: Try NANO for lightweight tasks, SUPER directly for heavy tasks ──
    if task_type in _NANO_TASKS:
        try:
            result, latency = await _call_model(NANO_MODEL, system_prompt, user_content, _TIMEOUT_NANO)
            latency_ms = int(latency * 1000)
            model_label = "30b"
            logger.info("llm_nano_called", task=task_type, latency_ms=latency_ms)

            # Escalate if low confidence or invalid output
            confidence = _extract_confidence(result)
            if confidence < _ESCALATION_CONFIDENCE or not _validate_result(result, task_type):
                logger.info("llm_escalating", task=task_type, nano_confidence=confidence)
                raise ValueError("escalate")

        except Exception as exc:
            if "escalate" not in str(exc):
                logger.warning("llm_nano_failed", task=task_type, error=str(exc))
            # Fall through to SUPER
            try:
                result, latency = await _call_model(SUPER_MODEL, system_prompt, user_content, _TIMEOUT_SUPER)
                latency_ms = int(latency * 1000)
                model_label = "120b"
                escalated = True
                logger.info("llm_super_called_escalated", task=task_type, latency_ms=latency_ms)
            except Exception as super_exc:
                logger.error("llm_super_failed", task=task_type, error=str(super_exc))
                return _fallback_response(task_type, text)

    else:
        # SUPER tasks go directly to 120B
        try:
            result, latency = await _call_model(SUPER_MODEL, system_prompt, user_content, _TIMEOUT_SUPER)
            latency_ms = int(latency * 1000)
            model_label = "120b"
            logger.info("llm_super_called", task=task_type, latency_ms=latency_ms)
        except Exception as exc:
            logger.error("llm_super_failed", task=task_type, error=str(exc))
            return _fallback_response(task_type, text)

    confidence = _extract_confidence(result)
    output = {
        "model_used": model_label,
        "task_type": task_type.value,
        "result": result,
        "confidence": confidence,
        "latency_ms": latency_ms,
        "escalated": escalated,
        "from_cache": False,
    }

    # Cache successful results
    if redis is not None and confidence >= 0.4:
        await redis.setex(cache_key, _CACHE_TTL, json.dumps(output))

    return output


def _fallback_response(task_type: TaskType, text: str) -> dict[str, Any]:
    """Keyword-based fallback when both models fail."""
    lower = text.lower()
    words = set(lower.split())
    _bull = {"surge", "rally", "gain", "rise", "beat", "profit", "growth", "record"}
    _bear = {"fall", "drop", "crash", "loss", "miss", "cut", "ban", "default"}
    bull = len(words & _bull)
    bear = len(words & _bear)
    total = bull + bear
    sentiment = (bull - bear) / max(total, 1) if total else 0.0

    result: dict[str, Any] = {
        "sentiment": round(sentiment, 3),
        "confidence": 0.3,
        "reasoning": "keyword_fallback_both_models_failed",
    }
    if task_type == TaskType.MACRO_ANALYSIS:
        result = {"risk_regime": "neutral", "equity_bias": 0.0, "gold_bias": 0.0, "confidence": 0.3, "key_driver": "fallback"}
    elif task_type == TaskType.COMMODITY_INTELLIGENCE:
        result = {"asset": "GOLD", "bias": "neutral", "confidence": 0.3, "sentiment": 0.0, "key_driver": "fallback"}
    elif task_type == TaskType.ENTITY_EXTRACTION:
        result = {"tickers": [], "commodities": [], "indices": [], "crypto": [], "companies": []}

    logger.warning("llm_fallback_used", task=task_type)
    return {
        "model_used": "fallback",
        "task_type": task_type.value,
        "result": result,
        "confidence": 0.3,
        "latency_ms": 0,
        "escalated": False,
        "from_cache": False,
    }


# ── Convenience wrappers ──────────────────────────────────────────────────────

async def analyze_news(title: str, body: str = "", entities: list[str] = [], redis: aioredis.Redis | None = None) -> dict[str, Any]:
    """Full news analysis — always uses SUPER model."""
    text = f"{title}\n{body[:1500]}" if body else title
    extra = f"Entities: {', '.join(entities[:5])}" if entities else ""
    return await route(text, TaskType.NEWS_ANALYSIS, redis, extra)


async def analyze_macro(macro_snapshot: dict[str, Any], redis: aioredis.Redis | None = None) -> dict[str, Any]:
    """Macro regime analysis — always uses SUPER model."""
    text = json.dumps(macro_snapshot)
    return await route(text, TaskType.MACRO_ANALYSIS, redis)


async def extract_entities(text: str, redis: aioredis.Redis | None = None) -> dict[str, Any]:
    """Entity extraction — uses NANO, escalates if needed."""
    return await route(text, TaskType.ENTITY_EXTRACTION, redis)


async def basic_sentiment(text: str, redis: aioredis.Redis | None = None) -> dict[str, Any]:
    """Quick sentiment — uses NANO, escalates if needed."""
    return await route(text, TaskType.BASIC_SENTIMENT, redis)


async def analyze_commodity(context: str, redis: aioredis.Redis | None = None) -> dict[str, Any]:
    """Commodity intelligence — always uses SUPER model."""
    return await route(context, TaskType.COMMODITY_INTELLIGENCE, redis)


async def analyze_high_impact_event(text: str, redis: aioredis.Redis | None = None) -> dict[str, Any]:
    """High-impact event (Fed, earnings, geo) — always uses SUPER model."""
    return await route(text, TaskType.HIGH_IMPACT_EVENT, redis)

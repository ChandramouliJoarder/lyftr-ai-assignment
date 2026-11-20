import hashlib
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import litellm
from litellm.caching.caching import Cache

from app.config import settings
from app.db import db

logger = logging.getLogger("app.llm")

# Initialize LiteLLM cache
cache_enabled = False
try:
    litellm.cache = Cache(type="local")
    cache_enabled = True
    logger.info("Initialized LiteLLM local in-memory cache")
except Exception as e:
    logger.warning("Failed to initialize LiteLLM cache: %s", e)
    cache_enabled = False


# Known failover exceptions in LiteLLM
FAILOVER_EXCEPTIONS = (
    litellm.RateLimitError,
    litellm.ServiceUnavailableError,
    litellm.InternalServerError,
    litellm.BadGatewayError,
    litellm.APIConnectionError,
    litellm.Timeout,
    litellm.AuthenticationError,
    litellm.PermissionDeniedError,
    litellm.APIError,
)


def compute_cache_key(model: str, messages: List[Dict[str, str]]) -> str:
    """
    Deterministic cache key based ONLY on model and the messages array.
    Does NOT depend on API keys or timestamps.
    """
    canonical_messages = [
        {"role": m["role"], "content": m["content"]}
        for m in messages
    ]
    raw = json.dumps({"model": model, "messages": canonical_messages}, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def parse_simulation_header(header_val: Optional[str]) -> Dict[str, int]:
    """
    Parse X-Simulate-Failure header into a mapping of key_id -> status_code.
    Allowed statuses: 429, 500, 502, 503.
    * means all keys.
    Lenient parsing: trim whitespace, ignore malformed pairs.
    """
    if not header_val or not settings.ENABLE_FAILURE_SIMULATION:
        return {}

    mapping: Dict[str, int] = {}
    parts = header_val.split(",")
    for part in parts:
        part = part.strip()
        if not part or "=" not in part:
            continue
        key, _, status_str = part.partition("=")
        key = key.strip()
        status_str = status_str.strip()
        try:
            status = int(status_str)
            if status in (429, 500, 502, 503):
                mapping[key] = status
        except ValueError:
            continue

    return mapping


def raise_simulated_exception(status: int, key_id: str, model: str):
    """Raise corresponding LiteLLM exception for simulated status code."""
    provider = model.split("/")[0] if "/" in model else "xai"
    msg = f"Simulated {status} failure for {key_id}"
    if status == 429:
        raise litellm.RateLimitError(message=msg, llm_provider=provider, model=model)
    elif status == 500:
        raise litellm.InternalServerError(message=msg, llm_provider=provider, model=model)
    elif status == 502:
        raise litellm.BadGatewayError(message=msg, llm_provider=provider, model=model)
    elif status == 503:
        raise litellm.ServiceUnavailableError(message=msg, llm_provider=provider, model=model)
    else:
        raise litellm.APIError(status_code=status, message=msg, llm_provider=provider, model=model)


class AllProvidersUnavailableError(Exception):
    """Raised when all keys in the pool fail."""
    pass


def get_cached_item(cache_key: str) -> Optional[Tuple[str, str, int, int]]:
    """Retrieve cached completion and tokens from LiteLLM in-memory cache or SQLite."""
    # 1. Try LiteLLM internal cache
    if cache_enabled and litellm.cache is not None:
        try:
            if hasattr(litellm.cache, "cache") and hasattr(litellm.cache.cache, "get_cache"):
                cached_resp = litellm.cache.cache.get_cache(cache_key)
                if cached_resp is not None:
                    reply = ""
                    if hasattr(cached_resp, "choices") and cached_resp.choices:
                        choice = cached_resp.choices[0]
                        reply = choice.message.content if hasattr(choice, "message") else ""
                    elif isinstance(cached_resp, dict):
                        reply = cached_resp.get("choices", [{}])[0].get("message", {}).get("content", "")

                    db_cached = db.get_cached_response(cache_key)
                    if db_cached:
                        return (
                            reply or db_cached["reply"],
                            db_cached["model"],
                            db_cached["input_tokens"],
                            db_cached["output_tokens"],
                        )
                    if reply:
                        return reply, settings.LLM_MODEL, 0, 0
        except Exception as e:
            logger.warning("Cache retrieval error from memory: %s", e)

    # 2. Try SQLite cached responses (survives container restarts)
    db_cached = db.get_cached_response(cache_key)
    if db_cached:
        return (
            db_cached["reply"],
            db_cached["model"],
            db_cached["input_tokens"],
            db_cached["output_tokens"],
        )

    return None


def store_cached_item(
    cache_key: str,
    response: Any,
    reply: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
):
    """Store completion in LiteLLM cache and persist to SQLite."""
    # Store in LiteLLM cache
    if cache_enabled and litellm.cache is not None:
        try:
            if hasattr(litellm.cache, "cache") and hasattr(litellm.cache.cache, "set_cache"):
                litellm.cache.cache.set_cache(cache_key, response)
        except Exception as ce:
            logger.warning("Failed to store in LiteLLM cache: %s", ce)

    # Store in SQLite table for restart persistence
    try:
        db.save_cached_response(cache_key, reply, model, input_tokens, output_tokens)
    except Exception as dbe:
        logger.warning("Failed to persist cached response in db: %s", dbe)


def execute_llm_request(
    messages: List[Dict[str, str]],
    simulate_header: Optional[str] = None,
) -> Tuple[str, Dict[str, Any]]:
    """
    Execute chat completion with LiteLLM caching and key failover loop.
    Returns: (reply_text, metadata_dict)
    """
    model = settings.LLM_MODEL
    key_pool = settings.key_pool
    timeout = settings.REQUEST_TIMEOUT_SECONDS
    cache_key = compute_cache_key(model, messages)

    simulation_map = parse_simulation_header(simulate_header)
    is_simulation_active = bool(simulation_map)

    # 1. Cache lookup if simulation is NOT active
    if not is_simulation_active and cache_enabled:
        cached_item = get_cached_item(cache_key)
        if cached_item is not None:
            reply, cached_model, input_tokens, output_tokens = cached_item
            meta = {
                "resolution_source": "LLM_CACHE",
                "model": cached_model or model,
                "input_tokens": int(input_tokens),
                "output_tokens": int(output_tokens),
                "key_id": None,
                "fallback_attempts": 0,
            }
            return reply, meta

    # If no keys are configured, fail immediately
    if not key_pool:
        logger.error("No API keys configured in LLM_API_KEYS")
        raise AllProvidersUnavailableError("all providers unavailable")

    fallback_attempts = 0

    for key_id, raw_api_key in key_pool:
        # Check simulated failure for this key or wildcard '*'
        sim_status = simulation_map.get(key_id) or simulation_map.get("*")

        try:
            if is_simulation_active and sim_status:
                logger.info("Simulating %s error for key %s", sim_status, key_id)
                raise_simulated_exception(sim_status, key_id, model)

            # Live LiteLLM completion
            response = litellm.completion(
                model=model,
                messages=messages,
                api_key=raw_api_key,
                timeout=timeout,
                num_retries=0,
                temperature=0.0,
                caching=not is_simulation_active,
                cache_key=cache_key,
            )

            # Check if LiteLLM itself detected a cache hit
            is_cache_hit = False
            hidden_params = getattr(response, "_hidden_params", {}) or {}
            if hidden_params.get("cache_hit") is True:
                is_cache_hit = True

            reply = response.choices[0].message.content or ""

            # Extract token counts
            usage = getattr(response, "usage", None)
            if usage:
                input_tokens = getattr(usage, "prompt_tokens", 0) or 0
                output_tokens = getattr(usage, "completion_tokens", 0) or 0
            else:
                input_tokens = 0
                output_tokens = 0

            # Fallback to token_counter if 0
            if input_tokens == 0:
                try:
                    input_tokens = litellm.token_counter(model=model, messages=messages)
                except Exception:
                    input_tokens = sum(len(m.get("content", "").split()) for m in messages)
            if output_tokens == 0:
                try:
                    output_tokens = litellm.token_counter(model=model, text=reply)
                except Exception:
                    output_tokens = len(reply.split())

            if is_cache_hit:
                resolution_source = "LLM_CACHE"
                successful_key = None
                effective_fallbacks = 0
            else:
                resolution_source = "LIVE_INFERENCE"
                successful_key = key_id
                effective_fallbacks = fallback_attempts
                # Record to cache and db if not simulating
                if not is_simulation_active and cache_enabled:
                    store_cached_item(
                        cache_key=cache_key,
                        response=response,
                        reply=reply,
                        model=model,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                    )

            meta = {
                "resolution_source": resolution_source,
                "model": model,
                "input_tokens": int(input_tokens),
                "output_tokens": int(output_tokens),
                "key_id": successful_key,
                "fallback_attempts": effective_fallbacks,
            }

            return reply, meta

        except FAILOVER_EXCEPTIONS as e:
            logger.warning("Provider call failed for key %s (attempt %d): %s", key_id, fallback_attempts + 1, e)
            fallback_attempts += 1
            continue
        except Exception as e:
            # Check for HTTP status codes on other exception types
            status_code = getattr(e, "status_code", None)
            if status_code in (429, 500, 502, 503, 401, 403):
                logger.warning("Provider error status %s for key %s: %s", status_code, key_id, e)
                fallback_attempts += 1
                continue
            logger.error("Unhandled error for key %s: %s", key_id, e)
            fallback_attempts += 1
            continue

    # All keys exhausted
    logger.error("All %d provider keys exhausted", len(key_pool))
    raise AllProvidersUnavailableError("all providers unavailable")

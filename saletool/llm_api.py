"""Shared OpenAI-compatible LLM API client for all LLM features.

Extracted because enrichment (company data extraction) and matching (service-fit
scoring) both need it and encounter the same pitfalls. Handle them once here
instead of duplicating the logic:

- **Structured output on OpenRouter depends on the endpoint, not the model.**
  The same model may be served by multiple providers, and only some support
  `json_schema`. The same code and model could therefore work intermittently.
  Send `provider.require_parameters=true` to route only to compatible providers,
  then fall back to standard JSON mode if it is still rejected.
- Some models wrap JSON in ```json … ``` despite being asked for plain JSON.
- Do not fully trust schema enforcement; **always validate again with Pydantic**
  on the caller side.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

import httpx

from saletool.llm_budget import prepare_payload
from saletool.models import LLMSettings

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 90.0


class LLMError(RuntimeError):
    pass


class LLMTimeoutError(LLMError):
    pass


def strip_code_fence(content: str) -> str:
    """Remove ```json … ``` fences if the model wraps the requested plain JSON."""
    fenced = re.search(r"```(?:json)?\s*(.+?)\s*```", content, re.DOTALL)
    return fenced.group(1) if fenced else content


def loads_json(content: str | None) -> Any:
    """Parse the JSON returned by the model. Raise LLMError with a user-friendly message."""
    try:
        return json.loads(strip_code_fence(content or ""))
    except (ValueError, TypeError) as exc:
        raise LLMError(f"Model did not return valid JSON: {exc}") from exc


async def post_chat(
    settings: LLMSettings,
    payload: dict,
    raise_on_error: bool = False,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> str | None:
    """Call /chat/completions and return the first message's content.

    Return `None` (instead of raising) on 400/404 when `raise_on_error=False`.
    This usually means "provider does not support this parameter", allowing the
    caller to downgrade the payload and retry.
    """
    try:
        payload = prepare_payload(
            payload, settings.context_window_tokens, settings.max_output_tokens
        )
    except ValueError as exc:
        raise LLMError(str(exc)) from exc
    url = f"{settings.base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await asyncio.wait_for(
                client.post(url, headers=headers, json=payload), timeout=timeout
            )
    except (asyncio.TimeoutError, httpx.TimeoutException) as exc:
        raise LLMTimeoutError(f"LLM request timed out after {timeout:g} seconds.") from exc
    except httpx.HTTPError as exc:
        raise LLMError(f"Could not reach the LLM API: {exc}") from exc

    if resp.status_code == 200:
        try:
            choice = resp.json()["choices"][0]
            if choice.get("finish_reason") == "length":
                raise LLMError("LLM output was truncated. Increase the output token budget.")
            return choice["message"]["content"]
        except (KeyError, IndexError, ValueError) as exc:
            raise LLMError(f"Unexpected LLM response shape: {exc}") from exc

    if resp.status_code in (400, 404) and not raise_on_error:
        logger.debug("LLM returned %s: %s", resp.status_code, resp.text[:300])
        return None

    raise LLMError(f"LLM API returned {resp.status_code}: {resp.text[:300]}")


async def request_json(
    settings: LLMSettings,
    payload: dict,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> Any:
    """Call the LLM with json_schema, falling back to json_object if rejected."""
    content = await post_chat(settings, payload, timeout=timeout)

    if content is None:
        logger.info("json_schema was rejected; retrying in standard JSON mode")
        fallback = dict(payload)
        fallback["response_format"] = {"type": "json_object"}
        fallback.pop("provider", None)
        content = await post_chat(settings, fallback, raise_on_error=True, timeout=timeout)

    return loads_json(content)

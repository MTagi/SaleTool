"""Lớp gọi API LLM tương thích OpenAI, dùng chung cho mọi tính năng cần LLM.

Tách ra vì hiện đã có 2 nơi cần: enrich (trích thông tin công ty) và matching
(chấm độ phù hợp dịch vụ). Cả hai gặp đúng những cái bẫy giống nhau nên xử lý
một lần ở đây thay vì chép đôi:

- **Structured output trên OpenRouter phụ thuộc endpoint, không phụ thuộc model.**
  Cùng một model có thể do nhiều provider phục vụ và chỉ một số hỗ trợ
  `json_schema` → cùng code, cùng model, lúc chạy được lúc không. Cách xử lý:
  gửi `provider.require_parameters=true` để chỉ route tới provider đủ tham số,
  và nếu vẫn bị từ chối thì hạ xuống JSON mode thường.
- Một số model bọc JSON trong ```json … ``` dù đã yêu cầu JSON thuần.
- Không tin tuyệt đối schema enforcement → **luôn validate lại bằng Pydantic**
  ở phía gọi.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from saletool.models import LLMSettings

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 90.0


class LLMError(RuntimeError):
    pass


def strip_code_fence(content: str) -> str:
    """Bóc ```json … ``` nếu model vẫn bọc dù đã yêu cầu JSON thuần."""
    fenced = re.search(r"```(?:json)?\s*(.+?)\s*```", content, re.DOTALL)
    return fenced.group(1) if fenced else content


def loads_json(content: str | None) -> Any:
    """Parse JSON model trả về. Raise LLMError với thông báo dùng được cho người dùng."""
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
    """Gọi /chat/completions, trả về nội dung message đầu tiên.

    Trả `None` (thay vì raise) khi server trả 400/404 và `raise_on_error=False`
    — đó thường là "provider không hỗ trợ tham số này", để phía gọi tự hạ cấp
    payload rồi thử lại.
    """
    url = f"{settings.base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, headers=headers, json=payload)
    except httpx.HTTPError as exc:
        raise LLMError(f"Could not reach the LLM API: {exc}") from exc

    if resp.status_code == 200:
        try:
            return resp.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError) as exc:
            raise LLMError(f"Unexpected LLM response shape: {exc}") from exc

    if resp.status_code in (400, 404) and not raise_on_error:
        logger.debug("LLM trả %s: %s", resp.status_code, resp.text[:300])
        return None

    raise LLMError(f"LLM API returned {resp.status_code}: {resp.text[:300]}")


async def request_json(
    settings: LLMSettings,
    payload: dict,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> Any:
    """Gọi LLM ở chế độ json_schema, tự hạ xuống json_object nếu bị từ chối."""
    content = await post_chat(settings, payload, timeout=timeout)

    if content is None:
        logger.info("json_schema bị từ chối, thử lại ở JSON mode thường")
        fallback = dict(payload)
        fallback["response_format"] = {"type": "json_object"}
        fallback.pop("provider", None)
        content = await post_chat(settings, fallback, raise_on_error=True, timeout=timeout)

    return loads_json(content)

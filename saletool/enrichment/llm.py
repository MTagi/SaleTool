"""Gọi LLM để trích xuất phần KHÔNG parse được bằng code thường.

Dùng API tương thích OpenAI (OpenRouter mặc định) qua httpx — không cần thêm SDK.

Về structured output trên OpenRouter, có một cái bẫy cần biết: hỗ trợ được xác
định theo **endpoint (provider phục vụ model)**, không phải theo tên model. Cùng
một model có thể được nhiều provider phục vụ và chỉ một số hỗ trợ json_schema →
cùng code, cùng model, lúc chạy được lúc không.

Cách xử lý ở đây:
1. gửi `provider.require_parameters=true` để OpenRouter chỉ route tới provider
   hỗ trợ đủ tham số;
2. vẫn **luôn validate lại bằng Pydantic**, vì mức đảm bảo khác nhau giữa các
   provider (có nơi coi schema chỉ là gợi ý mạnh);
3. nếu server từ chối json_schema thì tự động thử lại ở chế độ JSON thường.
"""

from __future__ import annotations

import json
import logging
import re

import httpx
from pydantic import BaseModel, ValidationError

from saletool.models import Executive, LLMSettings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You extract structured company information from website text. "
    "Only use facts present in the provided text. "
    "If a field is not stated, leave it null or an empty list. "
    "Never invent names, emails, phone numbers, or figures."
)


class LLMExtraction(BaseModel):
    """Các trường LLM phụ trách — phần mơ hồ mà regex/JSON-LD không lo được."""

    description: str | None = None
    industry: str | None = None
    founded_year: int | None = None
    headquarters: str | None = None
    employee_count_text: str | None = None
    technologies: list[str] = []
    executives: list[Executive] = []


_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "description": {"type": ["string", "null"]},
        "industry": {"type": ["string", "null"]},
        "founded_year": {"type": ["integer", "null"]},
        "headquarters": {"type": ["string", "null"]},
        "employee_count_text": {"type": ["string", "null"]},
        "technologies": {"type": "array", "items": {"type": "string"}},
        "executives": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "full_name": {"type": "string"},
                    "title": {"type": ["string", "null"]},
                },
                "required": ["full_name"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["description", "industry", "technologies", "executives"],
    "additionalProperties": False,
}


class LLMError(RuntimeError):
    pass


def _strip_code_fence(content: str) -> str:
    """Một số model vẫn bọc JSON trong ```json ... ``` dù đã yêu cầu JSON thuần."""
    fenced = re.search(r"```(?:json)?\s*(.+?)\s*```", content, re.DOTALL)
    return fenced.group(1) if fenced else content


class LLMClient:
    def __init__(self, settings: LLMSettings):
        if not settings.api_key:
            raise LLMError("LLM API key is not configured.")
        self.settings = settings

    async def extract_company_info(
        self, company_name: str, page_text: str, source_url: str | None = None
    ) -> LLMExtraction:
        user_prompt = (
            f"Company: {company_name}\n"
            f"Source URL: {source_url or 'unknown'}\n\n"
            "Extract company information from the text below.\n"
            "For 'executives', include only people explicitly described as leaders "
            "(CEO, founder, director, head of…), with their stated title.\n\n"
            "--- TEXT START ---\n"
            f"{page_text}\n"
            "--- TEXT END ---"
        )

        payload = {
            "model": self.settings.model,
            "temperature": self.settings.temperature,
            "max_tokens": self.settings.max_output_tokens,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "company_info", "strict": True, "schema": _JSON_SCHEMA},
            },
            # Chỉ route tới provider hỗ trợ đủ tham số đã gửi (gồm response_format).
            "provider": {"require_parameters": True},
        }

        content = await self._post(payload)

        if content is None:
            # Provider từ chối json_schema — hạ xuống JSON mode thường.
            logger.info("json_schema bị từ chối, thử lại ở JSON mode thường")
            payload["response_format"] = {"type": "json_object"}
            payload.pop("provider", None)
            content = await self._post(payload, raise_on_error=True)

        try:
            data = json.loads(_strip_code_fence(content or ""))
        except (ValueError, TypeError) as exc:
            raise LLMError(f"Model did not return valid JSON: {exc}") from exc

        try:
            return LLMExtraction.model_validate(data)
        except ValidationError as exc:
            # Không tin tuyệt đối schema enforcement của provider — nên tới đây
            # vẫn có thể lệch. Giữ lại phần dùng được thay vì bỏ cả kết quả.
            logger.warning("Kết quả LLM lệch schema, dùng phần hợp lệ: %s", exc)
            return LLMExtraction.model_validate(
                {k: v for k, v in data.items() if k in LLMExtraction.model_fields}
            )

    async def _post(self, payload: dict, raise_on_error: bool = False) -> str | None:
        url = f"{self.settings.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.settings.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                resp = await client.post(url, headers=headers, json=payload)
        except httpx.HTTPError as exc:
            raise LLMError(f"Could not reach the LLM API: {exc}") from exc

        if resp.status_code == 200:
            try:
                return resp.json()["choices"][0]["message"]["content"]
            except (KeyError, IndexError, ValueError) as exc:
                raise LLMError(f"Unexpected LLM response shape: {exc}") from exc

        # 400/404 thường là "provider không hỗ trợ tham số này" -> để caller hạ cấp.
        if resp.status_code in (400, 404) and not raise_on_error:
            logger.debug("LLM trả %s: %s", resp.status_code, resp.text[:300])
            return None

        raise LLMError(f"LLM API returned {resp.status_code}: {resp.text[:300]}")

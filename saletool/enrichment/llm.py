"""Gọi LLM để trích xuất phần KHÔNG parse được bằng code thường.

Phần plumbing (gọi HTTP, hạ cấp json_schema -> json_object, bóc code fence) nằm
ở `saletool.llm_api` vì matching cũng cần đúng những thứ đó. Ở đây chỉ còn
prompt, schema và cách gộp kết quả.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, ValidationError

from saletool.llm_api import LLMError, request_json
from saletool.models import Executive, LLMSettings

logger = logging.getLogger(__name__)

__all__ = ["LLMClient", "LLMError", "LLMExtraction"]

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

        data = await request_json(self.settings, payload)

        try:
            return LLMExtraction.model_validate(data)
        except ValidationError as exc:
            # Không tin tuyệt đối schema enforcement của provider — nên tới đây
            # vẫn có thể lệch. Giữ lại phần dùng được thay vì bỏ cả kết quả.
            logger.warning("Kết quả LLM lệch schema, dùng phần hợp lệ: %s", exc)
            return LLMExtraction.model_validate(
                {k: v for k, v in data.items() if k in LLMExtraction.model_fields}
            )

"""Use an LLM to extract fields that regular code could not parse.

The API plumbing (HTTP calls, json_schema -> json_object fallback, and code-fence
removal) lives in `saletool.llm_api` because matching needs it too. This module
contains only the prompt, schema, and result merging.
"""

from __future__ import annotations

import json
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
    """Fields handled by the LLM — ambiguous data that regex/JSON-LD cannot extract."""

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
        payload = {
            "model": self.settings.model,
            "temperature": self.settings.temperature,
            "max_tokens": self.settings.max_output_tokens,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "company": company_name,
                            "source_url": source_url,
                            "instructions": "Extract company information; include only explicitly stated leaders and titles.",
                            "evidence": page_text,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "company_info", "strict": True, "schema": _JSON_SCHEMA},
            },
            # Route only to providers that support all supplied parameters (including response_format).
            "provider": {"require_parameters": True},
        }

        data = await request_json(self.settings, payload)

        try:
            return LLMExtraction.model_validate(data)
        except ValidationError as exc:
            # Do not fully trust provider schema enforcement; results may still
            # differ here. Keep usable fields instead of discarding everything.
            logger.warning("LLM result did not match schema; using valid fields: %s", exc)
            return LLMExtraction.model_validate(
                {k: v for k, v in data.items() if k in LLMExtraction.model_fields}
            )

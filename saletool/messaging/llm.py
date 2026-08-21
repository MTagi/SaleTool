"""Sinh message gửi cho 1 contact cụ thể.

Prompt ở đây dựng theo hướng dẫn công khai của Apollo.io về cold email, vì đó là
bên có số liệu thật trên hàng triệu email:

- **Situational awareness, không phải demographic awareness.** "Tôi thấy anh là
  CFO ngành sản xuất" là mail-merge; "công ty anh đang chốt sổ thủ công qua ba
  nhà máy" mới là lý do người ta trả lời. Prompt bắt câu mở đầu phải nói về
  *tình huống* của họ, không phải chức danh.
- **6-8 câu.** Apollo đo email trong khoảng này có tỉ lệ trả lời cao nhất.
- **Một ý, một lời đề nghị.** Nhiều CTA làm giảm tỉ lệ trả lời.
- Câu đầu tiên nói về **họ**, không phải về mình.

Hai điều prompt KHÔNG lo được nên code phải kiểm lại (xem `pipeline.py`):
giới hạn ký tự của LinkedIn, và chuyện model để sót placeholder kiểu `[Name]`.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field, ValidationError

from saletool.llm_api import LLMError, request_json
from saletool.models import MESSAGE_CHANNELS, ChannelSpec, LLMSettings

logger = logging.getLogger(__name__)

_LANGUAGE_NAMES = {"en": "English", "vi": "Vietnamese"}

_TONE_GUIDANCE = {
    "direct": "Plain and businesslike. No pleasantries beyond one line.",
    "friendly": "Warm and human, but never chummy with a stranger.",
    "formal": "Respectful and complete. Suits senior titles and formal cultures.",
    "consultative": "Lead with a question or observation about their situation, not an offer.",
}

_SYSTEM_PROMPT = (
    "You write first-touch B2B sales messages that get replies.\n"
    "\n"
    "Rules, in priority order:\n"
    "1. NEVER invent facts. Use only what the prospect brief states. If the brief is thin, "
    "write a short honest message rather than a specific-sounding fake one.\n"
    "2. The opening line must be about THEM — their situation, not their job title and not "
    "your company. 'I saw you are the CFO of a manufacturer' is a mail merge, not "
    "personalisation. Reference the concrete situation in the brief.\n"
    "3. One idea and exactly one ask. No second CTA, no 'also'.\n"
    "4. The ask should be low friction: permission to send something, or a yes/no question. "
    "Do not demand a 30-minute call from a stranger unless asked to.\n"
    "5. No superlatives, no buzzwords, no 'I hope this email finds you well', no fake "
    "familiarity, no claims about their revenue or headcount that the brief does not state.\n"
    "6. Never output placeholders like [Name], {{company}} or TBD. If you do not know "
    "something, leave it out of the sentence entirely.\n"
    "7. Write as the sender described in the brief. Do not sign as anyone else."
)


class MessageDraft(BaseModel):
    subject: str = ""
    body: str = ""
    personalization_used: list[str] = Field(default_factory=list)


_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "subject": {"type": "string"},
        "body": {"type": "string"},
        "personalization_used": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["subject", "body", "personalization_used"],
    "additionalProperties": False,
}


def _length_rule(spec: ChannelSpec) -> str:
    parts = []
    if spec.has_subject and spec.max_subject_chars:
        parts.append(f"Subject: at most {spec.max_subject_chars} characters, no clickbait.")
    else:
        parts.append("No subject line — return an empty string for 'subject'.")

    if spec.max_body_chars:
        limit = spec.soft_body_chars or spec.max_body_chars
        parts.append(
            f"Body: HARD LIMIT {spec.max_body_chars} characters including spaces. "
            f"Aim for under {limit} — the platform rejects anything longer than the hard limit."
        )
    if spec.max_body_words:
        parts.append(f"Body: at most {spec.max_body_words} words.")

    parts.append(spec.guidance)
    return " ".join(p for p in parts if p)


def build_prompt(
    channel: str,
    language: str,
    tone: str,
    sender_brief: str,
    prospect_brief: str,
    service_brief: str,
    custom_instructions: str | None = None,
) -> str:
    spec = MESSAGE_CHANNELS[channel]
    language_name = _LANGUAGE_NAMES.get(language, "English")

    blocks = [
        f"CHANNEL: {spec.label}",
        f"LANGUAGE: write the whole message in {language_name}.",
        f"TONE: {_TONE_GUIDANCE.get(tone, _TONE_GUIDANCE['direct'])}",
        f"LENGTH: {_length_rule(spec)}",
        "",
        "SENDER (this is you)",
        sender_brief,
        "",
        "PROSPECT BRIEF (the only facts you may use about them)",
        prospect_brief,
        "",
        "WHAT YOU ARE OFFERING",
        service_brief,
    ]

    if custom_instructions:
        blocks += ["", "EXTRA INSTRUCTIONS FROM THE SENDER", custom_instructions.strip()]

    blocks += [
        "",
        "Return JSON. In 'personalization_used', list the specific facts from the prospect "
        "brief that you actually referenced — if the list would be empty, say so there rather "
        "than inventing something.",
    ]
    return "\n".join(blocks)


class MessageLLMClient:
    def __init__(self, settings: LLMSettings):
        if not settings.api_key:
            raise LLMError("LLM API key is not configured.")
        self.settings = settings

    async def write(
        self,
        channel: str,
        language: str,
        tone: str,
        sender_brief: str,
        prospect_brief: str,
        service_brief: str,
        custom_instructions: str | None = None,
    ) -> MessageDraft:
        if channel not in MESSAGE_CHANNELS:
            raise LLMError(f"Unknown channel: {channel}")

        payload = {
            "model": self.settings.model,
            # Sinh văn bản nên cần một chút biến thiên; 0.0 khiến mọi contact
            # nhận gần như cùng một câu chữ, đúng thứ làm outreach bị đánh spam.
            "temperature": max(self.settings.temperature, 0.4),
            "max_tokens": self.settings.max_output_tokens,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": build_prompt(
                        channel,
                        language,
                        tone,
                        sender_brief,
                        prospect_brief,
                        service_brief,
                        custom_instructions,
                    ),
                },
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "sales_message", "strict": True, "schema": _JSON_SCHEMA},
            },
            "provider": {"require_parameters": True},
        }

        data = await request_json(self.settings, payload)

        try:
            return MessageDraft.model_validate(data)
        except ValidationError as exc:
            logger.warning("Message lệch schema, dùng phần hợp lệ: %s", exc)
            if not isinstance(data, dict):
                raise LLMError("Model did not return a message object.") from exc
            used = data.get("personalization_used")
            return MessageDraft(
                subject=str(data.get("subject") or ""),
                body=str(data.get("body") or ""),
                personalization_used=[str(u) for u in used if u] if isinstance(used, list) else [],
            )

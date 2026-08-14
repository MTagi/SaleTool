"""Gọi LLM chấm độ phù hợp giữa 1 công ty và catalog dịch vụ của bạn.

Một quyết định thiết kế đáng nói: **LLM không nhìn thấy id thật của dịch vụ.**
Mỗi dịch vụ được đánh nhãn ngắn `S1`, `S2`… trong prompt, và code map ngược về
id. Lý do: model hay chép sai/rút gọn UUID, khi đó kết quả không ghép lại được
với dịch vụ nào. Nhãn ngắn thì gần như không sai, mà sai cũng phát hiện ngay.

LLM cũng **không** quyết định thứ hạng cuối. Nó chỉ chấm từng cặp
(công ty, dịch vụ); điểm tổng và thứ tự do code tính — xem `pipeline.py`. Như
vậy thứ hạng luôn giải thích được và không đổi giữa 2 lần chạy trên cùng dữ liệu.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field, ValidationError

from saletool.llm_api import LLMError, request_json
from saletool.models import LLMSettings, Service, ServiceFit

logger = logging.getLogger(__name__)

# Thang điểm mô tả trong prompt. Không có nó, mỗi lần chạy model tự nghĩ ra một
# thang khác nhau và điểm giữa các công ty không so sánh được với nhau.
_SYSTEM_PROMPT = (
    "You are a B2B sales analyst. You score how well a prospect company fits each "
    "service in the seller's catalog.\n"
    "Use ONLY facts given in the company profile. Never invent revenue, headcount, "
    "technology, or plans that are not stated.\n"
    "Scoring scale (use the whole range):\n"
    "  0-19   no fit — the service is irrelevant to this company\n"
    "  20-39  weak — same broad market only\n"
    "  40-59  possible — plausible but no evidence of the need\n"
    "  60-79  good — profile shows the problem this service solves\n"
    "  80-100 strong — explicit evidence of the need, size and industry both line up\n"
    "If the profile is too thin to judge (little more than a company name), cap every "
    "score at 50 and say so in 'concerns'. A confident score on no evidence is a wrong answer."
)


class _ServiceFitOut(BaseModel):
    service_ref: str
    score: int = Field(ge=0, le=100)
    rationale: str = ""


class MatchScoring(BaseModel):
    """Kết quả thô LLM trả về cho 1 công ty."""

    summary: str = ""
    signals: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)
    service_fits: list[_ServiceFitOut] = Field(default_factory=list)


_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "signals": {"type": "array", "items": {"type": "string"}},
        "concerns": {"type": "array", "items": {"type": "string"}},
        "service_fits": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "service_ref": {"type": "string"},
                    "score": {"type": "integer"},
                    "rationale": {"type": "string"},
                },
                "required": ["service_ref", "score", "rationale"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["summary", "signals", "concerns", "service_fits"],
    "additionalProperties": False,
}


def _service_label(index: int) -> str:
    return f"S{index + 1}"


def format_catalog(services: list[Service]) -> str:
    """Bày catalog cho LLM đọc, mỗi dịch vụ một khối có nhãn ngắn."""
    blocks = []
    for i, service in enumerate(services):
        lines = [f"[{_service_label(i)}] {service.name}"]
        if service.category:
            lines.append(f"  Category: {service.category}")
        if service.description:
            lines.append(f"  What it does: {service.description}")
        if service.value_proposition:
            lines.append(f"  Why buy it: {service.value_proposition}")
        if service.target_industries:
            lines.append(f"  Target industries: {', '.join(service.target_industries)}")
        if service.target_company_size:
            lines.append(f"  Target size: {service.target_company_size}")
        if service.keywords:
            lines.append(f"  Buying signals: {', '.join(service.keywords)}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


class MatchLLMClient:
    def __init__(self, settings: LLMSettings):
        if not settings.api_key:
            raise LLMError("LLM API key is not configured.")
        self.settings = settings

    async def score_company(
        self,
        company_profile: str,
        services: list[Service],
        objective: str | None = None,
    ) -> tuple[MatchScoring, list[ServiceFit]]:
        """Chấm 1 công ty với toàn bộ dịch vụ đã chọn.

        Trả về `(kết quả thô, danh sách ServiceFit đã map về id thật)`.
        """
        if not services:
            raise LLMError("No services selected to match against.")

        objective_block = (
            f"\nThe seller also asked to prioritise: {objective.strip()}\n" if objective else ""
        )
        user_prompt = (
            "SELLER'S SERVICE CATALOG\n"
            f"{format_catalog(services)}\n\n"
            "PROSPECT COMPANY PROFILE\n"
            f"{company_profile}\n"
            f"{objective_block}\n"
            "Score this company against EVERY service above. Return one entry per service, "
            "using its exact label (S1, S2, …) as 'service_ref'.\n"
            "'signals' = concrete facts from the profile that support a sale. "
            "'concerns' = what weakens the fit, including missing information. "
            "'summary' = one or two sentences a salesperson can act on."
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
                "json_schema": {"name": "service_match", "strict": True, "schema": _JSON_SCHEMA},
            },
            "provider": {"require_parameters": True},
        }

        data = await request_json(self.settings, payload)

        try:
            scoring = MatchScoring.model_validate(data)
        except ValidationError as exc:
            # Không tin tuyệt đối schema enforcement của provider. Giữ phần dùng
            # được thay vì bỏ cả công ty.
            logger.warning("Kết quả chấm điểm lệch schema, dùng phần hợp lệ: %s", exc)
            scoring = _salvage(data)

        return scoring, resolve_fits(scoring, services)


def _salvage(data: object) -> MatchScoring:
    """Vớt lại các trường hợp lệ khi model trả về không đúng schema."""
    if not isinstance(data, dict):
        return MatchScoring()

    fits = []
    for raw in data.get("service_fits") or []:
        try:
            fits.append(_ServiceFitOut.model_validate(raw))
        except ValidationError:
            continue

    def _strings(key: str) -> list[str]:
        value = data.get(key)
        return [str(v) for v in value if v] if isinstance(value, list) else []

    return MatchScoring(
        summary=str(data.get("summary") or ""),
        signals=_strings("signals"),
        concerns=_strings("concerns"),
        service_fits=fits,
    )


def resolve_fits(scoring: MatchScoring, services: list[Service]) -> list[ServiceFit]:
    """Map nhãn ngắn (S1, S2…) LLM trả về ngược lại id dịch vụ thật.

    Cũng chấp nhận model trả thẳng tên hoặc id dịch vụ — model nào cũng có lúc
    bỏ qua hướng dẫn về định dạng, và bỏ cả kết quả chỉ vì cái nhãn thì quá phí.
    Dịch vụ không được chấm sẽ nhận điểm 0 để danh sách luôn đủ.
    """
    by_key: dict[str, Service] = {}
    for i, service in enumerate(services):
        by_key[_service_label(i).lower()] = service
        by_key[service.id.lower()] = service
        by_key[service.name.strip().lower()] = service

    scored: dict[str, ServiceFit] = {}
    for raw in scoring.service_fits:
        service = by_key.get(raw.service_ref.strip().lower().strip("[]"))
        if not service:
            logger.warning("Bỏ qua điểm cho nhãn dịch vụ không nhận ra: %r", raw.service_ref)
            continue
        # Nhãn trùng nhau thì giữ điểm cao nhất — model đôi khi trả lặp.
        existing = scored.get(service.id)
        if existing and existing.score >= raw.score:
            continue
        scored[service.id] = ServiceFit(
            service_id=service.id,
            service_name=service.name,
            score=max(0, min(100, raw.score)),
            rationale=raw.rationale.strip(),
        )

    return [
        scored.get(
            service.id,
            ServiceFit(
                service_id=service.id,
                service_name=service.name,
                score=0,
                rationale="The model did not score this service.",
            ),
        )
        for service in services
    ]

"""Dựng ngữ cảnh, gọi LLM viết message, rồi **kiểm lại bằng code**.

Bước kiểm lại là phần quan trọng nhất ở đây. Prompt có ghi rõ giới hạn ký tự thì
model vẫn vượt, và vẫn để sót `[Tên công ty]` khi thiếu dữ liệu. Với LinkedIn,
vượt giới hạn không phải lỗi thẩm mỹ — nền tảng **từ chối gửi**. Nên mọi ràng
buộc đo được đều được kiểm lại sau khi model trả kết quả và ghi vào `warnings`,
hiển thị ngay cạnh message.

Code không tự sửa message: cắt ngang một câu còn tệ hơn để người dùng tự sửa.
"""

from __future__ import annotations

import logging
import re

from saletool.llm_api import LLMError
from saletool.messaging.llm import MessageLLMClient
from saletool.models import (
    MESSAGE_CHANNELS,
    AppSettings,
    ChannelSpec,
    Company,
    CompanyEnrichment,
    CompanyMatch,
    Contact,
    GeneratedMessage,
    SenderProfile,
    Service,
)
from saletool.prompt_text import MAX_LIST_ITEMS, clip_text

logger = logging.getLogger(__name__)

# Dấu hiệu model để sót chỗ trống thay vì bỏ hẳn câu. Gửi nguyên si ra ngoài là
# hỏng cả lần tiếp cận, nên bắt ở đây.
_PLACEHOLDER_PATTERNS = [
    (re.compile(r"\[[^\]\n]{2,40}\]"), "square-bracket placeholder"),
    (re.compile(r"\{\{[^}\n]{1,40}\}\}"), "curly-brace placeholder"),
    (re.compile(r"<[A-Za-z _]{2,30}>"), "angle-bracket placeholder"),
    (re.compile(r"\b(?:TBD|XYZ|ABC Company|Your Company|Company Name)\b", re.I), "filler text"),
    (re.compile(r"\bas an AI\b|\bI am an AI\b|language model", re.I), "model talking about itself"),
]


def count_words(text: str) -> int:
    return len([w for w in re.split(r"\s+", text.strip()) if w])


def build_sender_brief(sender: SenderProfile) -> str:
    lines = [f"Name: {sender.full_name}"]
    if sender.title:
        lines.append(f"Title: {sender.title}")
    lines.append(f"Company: {sender.company_name}")
    if sender.company_description:
        lines.append(f"What your company does: {clip_text(sender.company_description, 400)}")
    if sender.calendar_link:
        lines.append(f"Booking link (use only if the ask is a meeting): {sender.calendar_link}")
    if sender.signature:
        lines.append(f"Sign off exactly with: {sender.signature}")
    return "\n".join(lines)


def build_prospect_brief(
    company: Company,
    contact: Contact,
    enrichment: CompanyEnrichment | None = None,
    match: CompanyMatch | None = None,
) -> str:
    """Mọi thứ biết về người nhận + công ty của họ.

    Phần giá trị nhất nằm ở `match`: lý do LLM chấm điểm ở bước matching chính là
    câu chuyện để mở đầu message. Không có nó thì message vẫn viết được nhưng
    chung chung hơn hẳn.
    """
    lines = [
        f"Contact: {contact.full_name}",
        f"Their title: {contact.title or 'unknown'}",
        f"Their company: {company.name}",
    ]

    def add(label: str, value: str | None) -> None:
        if value:
            lines.append(f"{label}: {value}")

    add("Industry", company.industry or (enrichment.industry if enrichment else None))
    add("Location", company.location or (enrichment.headquarters if enrichment else None))
    if company.employee_count:
        add("Headcount", str(company.employee_count))
    elif enrichment and enrichment.employee_count_text:
        add("Headcount", enrichment.employee_count_text)

    if enrichment:
        add("What the company does", clip_text(enrichment.description, 500))
        if enrichment.technologies:
            add("Technology they use", ", ".join(enrichment.technologies[:MAX_LIST_ITEMS]))
        if enrichment.founded_year:
            add("Founded", str(enrichment.founded_year))

    if match:
        add("Why they were shortlisted", match.summary)
        if match.signals:
            lines.append("Signals found about them:")
            lines += [f"  - {s}" for s in match.signals[:MAX_LIST_ITEMS]]
        if match.concerns:
            lines.append("Known gaps (do NOT paper over these):")
            lines += [f"  - {c}" for c in match.concerns[:MAX_LIST_ITEMS]]

    if len(lines) <= 3:
        lines.append(
            "(Nothing else is known about them. Keep the message short and do not pretend "
            "to know their situation.)"
        )

    return "\n".join(lines)


def build_service_brief(service: Service | None, fit_rationale: str | None = None) -> str:
    if not service:
        return (
            "No specific service was selected. Introduce what the sender's company does and "
            "ask whether it is relevant, without pitching a named product."
        )

    lines = [f"Service: {service.name}"]
    if service.description:
        lines.append(f"What it does: {service.description}")
    if service.value_proposition:
        lines.append(f"Why customers pick it: {service.value_proposition}")
    if service.target_company_size:
        lines.append(f"Usual customer size: {service.target_company_size}")
    if fit_rationale:
        lines.append(f"Why it fits this company specifically: {fit_rationale}")
    return "\n".join(lines)


def validate_message(message: GeneratedMessage, spec: ChannelSpec) -> list[str]:
    """Đối chiếu message với ràng buộc thật của kênh gửi.

    Trả về danh sách cảnh báo — không sửa, không chặn. Người dùng thấy vấn đề
    ngay cạnh nội dung và tự quyết định sửa hay gửi.
    """
    warnings: list[str] = []
    body = message.body.strip()

    if not body:
        warnings.append("The model returned an empty message body.")
        return warnings

    if spec.has_subject:
        if not (message.subject or "").strip():
            warnings.append("No subject line — this channel needs one.")
        elif spec.max_subject_chars and message.subject_chars > spec.max_subject_chars:
            warnings.append(
                f"Subject is {message.subject_chars} characters "
                f"(recommended max {spec.max_subject_chars})."
            )

    if spec.max_body_chars and message.body_chars > spec.max_body_chars:
        warnings.append(
            f"Body is {message.body_chars} characters — over the {spec.max_body_chars}-character "
            "platform limit, so it cannot be sent as is."
        )
    elif spec.soft_body_chars and message.body_chars > spec.soft_body_chars:
        warnings.append(
            f"Body is {message.body_chars} characters. Fine on a paid LinkedIn account, "
            f"but free accounts cap connection notes at {spec.soft_body_chars}."
        )

    if spec.max_body_words and message.body_words > spec.max_body_words:
        warnings.append(
            f"Body is {message.body_words} words (target max {spec.max_body_words}); "
            "longer cold emails get fewer replies."
        )

    for pattern, label in _PLACEHOLDER_PATTERNS:
        found = pattern.search(body) or (message.subject and pattern.search(message.subject))
        if found:
            warnings.append(f"Contains {label}: {found.group(0)!r} — edit before sending.")

    if not message.personalization_used:
        warnings.append(
            "The model reported no personalisation — this reads as a generic blast. "
            "Enrich the company or run matching first."
        )

    # Không gọi tên người nhận là dấu hiệu message viết chung cho cả công ty.
    first_name = message.contact_name.strip().split()[-1] if message.contact_name.strip() else ""
    if first_name and first_name.lower() not in body.lower():
        warnings.append(f"Does not address {message.contact_name} by name.")

    return warnings


async def generate_message(
    company: Company,
    contact: Contact,
    settings: AppSettings,
    channel: str,
    language: str,
    tone: str,
    service: Service | None = None,
    enrichment: CompanyEnrichment | None = None,
    match: CompanyMatch | None = None,
    custom_instructions: str | None = None,
) -> GeneratedMessage:
    """Viết 1 message. Lỗi LLM ghi vào `error` chứ không raise, để 1 contact hỏng
    không làm mất cả mẻ."""
    spec = MESSAGE_CHANNELS[channel]

    message = GeneratedMessage(
        company_name=company.name,
        contact_name=contact.full_name,
        contact_title=contact.title,
        contact_email=contact.email,
        contact_linkedin_url=contact.linkedin_url,
        channel=channel,
        language=language,
        tone=tone,
        service_id=service.id if service else None,
        service_name=service.name if service else None,
    )

    fit_rationale = None
    if match and service:
        fit_rationale = next(
            (f.rationale for f in match.service_fits if f.service_id == service.id), None
        )

    try:
        draft = await MessageLLMClient(settings.llm).write(
            channel=channel,
            language=language,
            tone=tone,
            sender_brief=build_sender_brief(settings.sender),
            prospect_brief=build_prospect_brief(company, contact, enrichment, match),
            service_brief=build_service_brief(service, fit_rationale),
            custom_instructions=custom_instructions,
        )
    except LLMError as exc:
        logger.warning("Viết message thất bại cho '%s': %s", contact.full_name, exc)
        message.error = str(exc)[:300]
        return message

    message.subject = draft.subject.strip() if spec.has_subject else None
    message.body = draft.body.strip()
    message.personalization_used = [p for p in draft.personalization_used if p][:MAX_LIST_ITEMS]
    message.subject_chars = len(message.subject or "")
    message.body_chars = len(message.body)
    message.body_words = count_words(message.body)
    message.warnings = validate_message(message, spec)

    return message

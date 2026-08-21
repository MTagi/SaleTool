"""Test phần code của bước sinh message.

Trọng tâm là `validate_message`: đó là chỗ bắt các lỗi mà prompt không chặn được
— vượt giới hạn ký tự của LinkedIn (gửi không được), và placeholder còn sót.
"""

import asyncio

from saletool.llm_api import LLMError
from saletool.messaging.llm import build_prompt
from saletool.messaging.pipeline import (
    build_prospect_brief,
    build_sender_brief,
    build_service_brief,
    count_words,
    generate_message,
    validate_message,
)
from saletool.models import (
    MESSAGE_CHANNELS,
    AppSettings,
    Company,
    CompanyEnrichment,
    CompanyMatch,
    Contact,
    GeneratedMessage,
    SenderProfile,
    Service,
    ServiceFit,
)


def _message(body: str, **overrides) -> GeneratedMessage:
    payload = {
        "company_name": "Acme",
        "contact_name": "Tran Thi Lan",
        "channel": "email",
        "language": "en",
        "tone": "direct",
        "subject": "quick question about your close process",
        "body": body,
        "personalization_used": ["closes the books manually"],
    }
    payload.update(overrides)
    message = GeneratedMessage(**payload)
    message.subject_chars = len(message.subject or "")
    message.body_chars = len(message.body)
    message.body_words = count_words(message.body)
    return message


def _service(name="ERP", service_id="svc-1", **overrides) -> Service:
    payload = {
        "id": service_id,
        "name": name,
        "description": "SAP rollout",
        "created_at": "2026-08-21T00:00:00+00:00",
        "updated_at": "2026-08-21T00:00:00+00:00",
    }
    payload.update(overrides)
    return Service(**payload)


def _sender() -> SenderProfile:
    return SenderProfile(
        full_name="Tran Van A", title="Head of Sales", company_name="ABIM",
        company_description="We build ERP and data platforms.",
    )


GOOD_BODY = "Hi Lan, I noticed Acme still closes the books by hand across three plants. Worth a quick look?"


# --- Kiểm tra ràng buộc kênh gửi --------------------------------------------


def test_clean_email_produces_no_warnings():
    assert validate_message(_message(GOOD_BODY), MESSAGE_CHANNELS["email"]) == []


def test_empty_body_is_reported():
    warnings = validate_message(_message("   "), MESSAGE_CHANNELS["email"])
    assert any("empty" in w for w in warnings)


def test_long_email_is_flagged_by_word_count():
    body = "Hi Lan, " + "word " * 200
    warnings = validate_message(_message(body), MESSAGE_CHANNELS["email"])

    assert any("words" in w for w in warnings)


def test_linkedin_note_over_the_hard_limit_says_it_cannot_be_sent():
    """300 ký tự là giới hạn của LinkedIn, không phải sở thích — vượt là gửi trượt."""
    body = "Hi Lan, " + "x" * 400
    warnings = validate_message(
        _message(body, channel="linkedin_connection", subject=None),
        MESSAGE_CHANNELS["linkedin_connection"],
    )

    assert any("cannot be sent" in w for w in warnings)


def test_linkedin_note_over_the_free_account_limit_is_a_softer_warning():
    body = "Hi Lan, " + "x" * 240  # >200 (free) nhưng <300 (trả phí)
    warnings = validate_message(
        _message(body, channel="linkedin_connection", subject=None),
        MESSAGE_CHANNELS["linkedin_connection"],
    )

    assert any("free accounts" in w for w in warnings)
    assert not any("cannot be sent" in w for w in warnings)


def test_linkedin_note_within_limits_is_clean():
    warnings = validate_message(
        _message(GOOD_BODY, channel="linkedin_connection", subject=None),
        MESSAGE_CHANNELS["linkedin_connection"],
    )
    assert warnings == []


def test_missing_subject_on_a_channel_that_needs_one():
    warnings = validate_message(_message(GOOD_BODY, subject=""), MESSAGE_CHANNELS["email"])
    assert any("subject" in w.lower() for w in warnings)


def test_overlong_subject_is_flagged():
    warnings = validate_message(_message(GOOD_BODY, subject="x" * 120), MESSAGE_CHANNELS["email"])
    assert any("Subject is 120" in w for w in warnings)


# --- Bắt dấu vết model chưa điền xong ---------------------------------------


def test_square_bracket_placeholder_is_caught():
    warnings = validate_message(_message("Hi [First Name], quick question."), MESSAGE_CHANNELS["email"])
    assert any("placeholder" in w for w in warnings)


def test_template_variable_is_caught():
    warnings = validate_message(_message("Hi Lan, at {{company}} we..."), MESSAGE_CHANNELS["email"])
    assert any("placeholder" in w for w in warnings)


def test_filler_company_name_is_caught():
    warnings = validate_message(_message("Hi Lan, ABC Company helps teams."), MESSAGE_CHANNELS["email"])
    assert any("filler" in w for w in warnings)


def test_model_talking_about_itself_is_caught():
    warnings = validate_message(
        _message("Hi Lan, as an AI I cannot browse, but..."), MESSAGE_CHANNELS["email"]
    )
    assert any("model talking about itself" in w for w in warnings)


def test_no_personalisation_reported_is_flagged():
    warnings = validate_message(
        _message(GOOD_BODY, personalization_used=[]), MESSAGE_CHANNELS["email"]
    )
    assert any("generic blast" in w for w in warnings)


def test_not_addressing_the_contact_is_flagged():
    warnings = validate_message(
        _message("Hello there, quick question about your close process."), MESSAGE_CHANNELS["email"]
    )
    assert any("by name" in w for w in warnings)


# --- Dựng brief -------------------------------------------------------------


def test_sender_brief_includes_the_signature_instruction():
    sender = _sender()
    sender.signature = "Tran Van A\nABIM"

    brief = build_sender_brief(sender)

    assert "Tran Van A" in brief
    assert "Sign off exactly with" in brief


def test_prospect_brief_says_so_when_nothing_is_known():
    brief = build_prospect_brief(Company(name="Mystery Co"), Contact(full_name="Someone"))

    assert "do not pretend" in brief


def test_prospect_brief_carries_the_matching_rationale():
    """Lý do chấm điểm ở bước matching chính là chất liệu cho câu mở đầu."""
    match = CompanyMatch(
        company_name="Acme",
        summary="Closes books manually across three plants.",
        signals=["three plants", "CFO listed"],
        concerns=["no budget stated"],
    )

    brief = build_prospect_brief(
        Company(name="Acme", industry="Manufacturing"),
        Contact(full_name="Tran Thi Lan", title="CFO"),
        enrichment=CompanyEnrichment(company_name="Acme", description="Maker of parts."),
        match=match,
    )

    assert "Closes books manually" in brief
    assert "three plants" in brief
    assert "no budget stated" in brief
    assert "Maker of parts." in brief


def test_service_brief_without_a_service_tells_the_model_not_to_pitch():
    assert "without pitching a named product" in build_service_brief(None)


def test_service_brief_includes_the_per_company_reason():
    brief = build_service_brief(_service(), fit_rationale="They run three plants on spreadsheets.")
    assert "three plants on spreadsheets" in brief


# --- Prompt -----------------------------------------------------------------


def test_prompt_states_the_hard_character_limit_for_linkedin():
    prompt = build_prompt(
        "linkedin_connection", "en", "direct", "sender", "prospect", "service"
    )

    assert "HARD LIMIT 300 characters" in prompt
    assert "empty string for 'subject'" in prompt


def test_prompt_names_the_output_language():
    assert "Vietnamese" in build_prompt("email", "vi", "direct", "s", "p", "sv")


def test_custom_instructions_reach_the_prompt():
    prompt = build_prompt(
        "email", "en", "direct", "s", "p", "sv", custom_instructions="mention the expo"
    )
    assert "mention the expo" in prompt


# --- generate_message -------------------------------------------------------


def _settings() -> AppSettings:
    settings = AppSettings()
    settings.llm.api_key = "sk-test"
    settings.sender = _sender()
    return settings


def test_llm_failure_is_recorded_on_the_message_not_raised(monkeypatch):
    async def boom(*args, **kwargs):
        raise LLMError("provider is down")

    monkeypatch.setattr("saletool.messaging.llm.request_json", boom)

    message = asyncio.run(
        generate_message(
            Company(name="Acme"),
            Contact(full_name="Tran Thi Lan"),
            _settings(),
            channel="email",
            language="en",
            tone="direct",
        )
    )

    assert message.error == "provider is down"
    assert message.body == ""


def test_successful_generation_counts_and_validates(monkeypatch):
    async def wrote(*args, **kwargs):
        return {
            "subject": "quick question about your close",
            "body": GOOD_BODY,
            "personalization_used": ["closes the books manually"],
        }

    monkeypatch.setattr("saletool.messaging.llm.request_json", wrote)

    message = asyncio.run(
        generate_message(
            Company(name="Acme"),
            Contact(full_name="Tran Thi Lan", title="CFO", email="lan@acme.vn"),
            _settings(),
            channel="email",
            language="en",
            tone="direct",
            service=_service(),
        )
    )

    assert message.error is None
    assert message.body == GOOD_BODY
    assert message.body_words == count_words(GOOD_BODY)
    assert message.subject_chars == len("quick question about your close")
    assert message.contact_email == "lan@acme.vn"
    assert message.service_name == "ERP"
    assert message.warnings == []


def test_subject_is_dropped_for_channels_that_have_none(monkeypatch):
    async def wrote(*args, **kwargs):
        return {"subject": "should not be used", "body": GOOD_BODY, "personalization_used": ["x"]}

    monkeypatch.setattr("saletool.messaging.llm.request_json", wrote)

    message = asyncio.run(
        generate_message(
            Company(name="Acme"),
            Contact(full_name="Tran Thi Lan"),
            _settings(),
            channel="linkedin_connection",
            language="en",
            tone="direct",
        )
    )

    assert message.subject is None
    assert message.subject_chars == 0


def test_the_fit_rationale_for_the_chosen_service_is_passed_through(monkeypatch):
    captured = {}

    async def capture(settings, payload, timeout=None):
        captured["prompt"] = payload["messages"][-1]["content"]
        return {"subject": "s", "body": GOOD_BODY, "personalization_used": ["x"]}

    monkeypatch.setattr("saletool.messaging.llm.request_json", capture)

    match = CompanyMatch(
        company_name="Acme",
        service_fits=[
            ServiceFit(service_id="svc-1", service_name="ERP", score=80, rationale="three plants"),
            ServiceFit(service_id="svc-2", service_name="BI", score=40, rationale="not this one"),
        ],
    )

    asyncio.run(
        generate_message(
            Company(name="Acme"),
            Contact(full_name="Tran Thi Lan"),
            _settings(),
            channel="email",
            language="en",
            tone="direct",
            service=_service(),
            match=match,
        )
    )

    assert "three plants" in captured["prompt"]
    assert "not this one" not in captured["prompt"]


def test_generation_uses_some_temperature_even_when_settings_say_zero(monkeypatch):
    """Temperature 0 khiến mọi contact nhận gần như cùng một câu chữ — đúng thứ
    làm outreach bị đánh dấu spam."""
    captured = {}

    async def capture(settings, payload, timeout=None):
        captured["temperature"] = payload["temperature"]
        return {"subject": "s", "body": GOOD_BODY, "personalization_used": ["x"]}

    monkeypatch.setattr("saletool.messaging.llm.request_json", capture)

    settings = _settings()
    settings.llm.temperature = 0.0

    asyncio.run(
        generate_message(
            Company(name="Acme"),
            Contact(full_name="Tran Thi Lan"),
            settings,
            channel="email",
            language="en",
            tone="direct",
        )
    )

    assert captured["temperature"] >= 0.4

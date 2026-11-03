"""Data models shared across the pipeline."""

from __future__ import annotations

import hashlib
from typing import Literal

from pydantic import BaseModel, Field, model_validator

# Common seniority levels (matching Apollo.io/PDL classifications), used to filter
# for senior contacts at a company.
SENIORITY_LEVELS = [
    "owner",
    "founder",
    "c_suite",
    "partner",
    "vp",
    "head",
    "director",
    "manager",
    "senior",
    "entry",
    "intern",
]

DEFAULT_SENIOR_LEVELS = ["owner", "founder", "c_suite", "partner", "vp", "head", "director"]


class SearchCriteria(BaseModel):
    """Input format describing company search criteria.

    This is the input users provide for the tool to find matching companies on LinkedIn.
    """

    industries: list[str] = Field(default_factory=list, description="Industries, e.g. 'Software', 'Retail'")
    keywords: list[str] = Field(default_factory=list, description="Keywords describing the company or its business")
    locations: list[str] = Field(default_factory=list, description="Locations, e.g. 'Vietnam', 'Ho Chi Minh City'")
    company_size_min: int | None = Field(default=None, ge=0)
    company_size_max: int | None = Field(default=None, ge=0)
    expanded_target_titles: list[str] = Field(default_factory=list)
    title_expansion_status: str | None = None
    target_titles: list[str] = Field(
        default_factory=list, description="Specific job titles to find, e.g. 'CEO', 'Head of Sales'"
    )
    seniority_levels: list[str] = Field(
        default_factory=lambda: list(DEFAULT_SENIOR_LEVELS),
        description="Contact seniority levels to retrieve (defaults to senior management and above)",
    )
    max_companies: int = Field(default=20, gt=0, description="Maximum number of companies to find")
    max_contacts_per_company: int = Field(default=5, gt=0, description="Maximum contacts to retrieve per company")


class Company(BaseModel):
    id: str | None = None
    name: str
    description: str | None = None
    founded_year: int | None = None
    phone: str | None = None
    address: str | None = None
    annual_revenue: str | None = None
    total_funding: str | None = None
    technologies: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    linkedin_url: str | None = None
    domain: str | None = None
    industry: str | None = None
    location: str | None = None
    employee_count: int | None = None
    provider_id: str | None = Field(default=None, description="Internal data provider ID")


class Contact(BaseModel):
    id: str | None = None
    provider_id: str | None = None
    full_name: str
    title: str | None = None
    seniority: str | None = None
    linkedin_url: str | None = None
    email: str | None = None
    company_name: str | None = None


class CompanyResult(BaseModel):
    """Final result: one matching company with its senior contacts."""

    company: Company
    contacts: list[Contact] = Field(default_factory=list)

    @model_validator(mode="after")
    def assign_snapshot_ids(self) -> CompanyResult:
        """Generate a stable ID for legacy data without an ID in search history."""
        if not self.company.id:
            fingerprint = hashlib.sha256(
                self.company.model_dump_json(exclude={"id"}).encode("utf-8")
            ).hexdigest()
            self.company.id = self.company.provider_id or f"company:{fingerprint}"
        for index, contact in enumerate(self.contacts):
            if not contact.id:
                contact.id = contact.provider_id or f"{self.company.id}:contact:{index}"
        return self


class SearchRunSummary(BaseModel):
    """One search history row: enough to display the list, without full results
    (see SearchRunDetail)."""

    id: str = Field(description="UUID used to retrieve details or download a file")
    username: str
    created_at: str = Field(description="ISO 8601 UTC, e.g. 2026-08-13T10:00:00+00:00")
    provider: str
    criteria: SearchCriteria
    total_companies: int
    total_contacts: int


class SearchRunDetail(SearchRunSummary):
    """One search run with full results, used when viewing a run in history."""

    results: list[CompanyResult] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Configuration (Settings page)
# ---------------------------------------------------------------------------

LLM_PROVIDERS = ["openrouter", "openai_compatible"]

# Company/contact data sources for Search (step 1). Apollo is currently the only
# option, but this remains a list: `CompanyContactProvider` already provides the
# extension point, so adding a provider later only requires another entry here,
# not changes to the form or route. The frontend reads this list for its dropdown.
DATA_PROVIDERS = ["apollo"]

# Providers that require an API key. Kept separate from DATA_PROVIDERS because
# a future source might not need a key (e.g. manual file import).
DATA_PROVIDERS_REQUIRING_KEY = ["apollo"]

APOLLO_SEARCH_FIELDS = [
    "industries",
    "keywords",
    "locations",
    "company_size",
    "target_titles",
    "seniority_levels",
]

# "none" = do not use web search; only read the company's own website.
# This is also the dropdown order, arranged by attractiveness: providers with
# actual monthly free tiers come first, and Brave is last because it removed its
# free tier and has no spending cap (see enrichment/search/providers.py).
SEARCH_PROVIDERS = ["none", "tavily", "exa", "codex", "serper", "brave"]

# Which providers need an API key; the frontend uses this to show the right field.
# `codex` is excluded because a valid setup does not need a key: 9Router can run
# on the same host as the backend. With Docker Compose a key is required (see
# docs/docker.md), but requiring it here would incorrectly block the host setup.
SEARCH_PROVIDERS_REQUIRING_KEY = ["tavily", "exa", "serper", "brave"]

MASKED_SECRET = "__SALETOOL_UNCHANGED__"
"""Value the frontend sends back when the user has NOT changed an API key.

The backend never returns the real key to the client; it returns a masked value
for display. On save, if this sentinel is received, keep the existing key."""


class DataSourceSettings(BaseModel):
    """Data source for the Search step.

    The API key is stored here (Settings), not in the search form: it is a
    one-time team setting, not something entered for every run. It is encrypted
    before storage like other keys (see saletool/crypto.py), instead of passing
    through the form in plain text each time.
    """

    provider: str = "apollo"
    api_key: str | None = None
    enabled_search_fields: list[
        Literal[
            "industries",
            "keywords",
            "locations",
            "company_size",
            "target_titles",
            "seniority_levels",
        ]
    ] = Field(default_factory=lambda: list(APOLLO_SEARCH_FIELDS))


class LLMSettings(BaseModel):
    enabled: bool = True
    provider: str = "openrouter"
    api_key: str | None = None
    base_url: str = "https://openrouter.ai/api/v1"
    # Checked 2026-09-04: OpenRouter removed `google/gemini-2.0-flash-001`, which
    # now returns 404 "No endpoints found" and breaks new installations as soon
    # as they enable the LLM. The model below was tested with strict
    # `response_format` json_schema (required by llm_api.py; not every model supports it).
    model: str = "google/gemini-3.1-flash-lite"
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_output_tokens: int = Field(default=2048, gt=0)
    context_window_tokens: int = Field(default=32768, ge=2048)


class SearchSettings(BaseModel):
    provider: str = "none"
    api_key: str | None = None
    # The `codex` provider uses these two fields. If left blank,
    # CodexSearchProvider uses defaults (local 9Router + gpt-5.4), so selecting
    # `codex` and saving is enough to get started.
    base_url: str | None = Field(
        default=None, description="Responses API endpoint, e.g. http://9router:20128/v1"
    )
    model: str | None = Field(default=None, description="Model for web search, e.g. cx/gpt-5.4")
    max_results: int = Field(default=5, gt=0, le=50)


class EnrichmentSettings(BaseModel):
    """Enable or disable each stage of the enrichment pipeline.

    Execution order: structured data (cheapest and most accurate) -> company
    website -> web search -> LLM (only for missing fields).
    """

    use_structured_data: bool = Field(
        default=True, description="Stage 0: JSON-LD schema.org, meta tags, regex — no LLM cost"
    )
    use_company_website: bool = Field(default=True, description="Read the sitemap and shallow-crawl the company website")
    use_web_search: bool = Field(default=False, description="Find external pages that mention the company")
    # Start with a valid configuration before any provider keys are supplied.
    use_llm: bool = Field(default=False, description="Use an LLM to extract information that code could not parse")
    use_browser_fallback: bool = Field(
        default=True, description="Use Playwright for JavaScript-rendered pages (much slower)"
    )

    max_pages_per_company: int = Field(default=8, gt=0, le=50)
    web_search_reserved_pages: int = Field(
        default=4, ge=1, le=50,
        description="Pages reserved for external web search within the total per-company limit",
    )
    request_timeout_seconds: float = Field(default=15.0, gt=0)
    request_delay_seconds: float = Field(
        default=1.0, ge=0, description="Delay between requests to the same domain — crawl politely"
    )
    respect_robots_txt: bool = True
    user_agent: str = "SaleToolBot/1.0 (+contact: set-your-email@example.com)"

    auto_enrich_on_search: bool = Field(
        default=False, description="Automatically enrich all companies after search completes"
    )


class SenderProfile(BaseModel):
    """Who you are, used when generating messages to contacts.

    Without this information, the LLM would have to invent a sender and the
    generated message would be unusable. Message generation therefore requires
    at least `full_name` and
    `company_name`.
    """

    full_name: str = ""
    title: str = ""
    company_name: str = ""
    company_description: str = Field(
        default="", description="What your company does — 1–2 sentences used by the LLM for an introduction"
    )
    email: str = ""
    phone: str = ""
    calendar_link: str = Field(default="", description="Scheduling link, e.g. Calendly — used for the CTA")
    signature: str = Field(default="", description="Signature inserted verbatim at the end of emails")

    def is_usable(self) -> bool:
        return bool(self.full_name.strip() and self.company_name.strip())


class AppSettings(BaseModel):
    data_source: DataSourceSettings = Field(default_factory=DataSourceSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    search: SearchSettings = Field(default_factory=SearchSettings)
    enrichment: EnrichmentSettings = Field(default_factory=EnrichmentSettings)
    sender: SenderProfile = Field(default_factory=SenderProfile)
    updated_at: str | None = None
    updated_by: str | None = None


# ---------------------------------------------------------------------------
# Enrichment results
# ---------------------------------------------------------------------------


class EnrichmentSource(BaseModel):
    """Provenance — where each piece of data came from.

    This is a compliance requirement, not an optional feature: if asked "where
    did this data come from?", we must be able to answer for every record.
    """

    url: str
    fetched_at: str
    fetch_method: str = Field(description="http | browser")
    extractor: str = Field(description="json_ld | meta | regex | llm")
    ok: bool = True
    note: str | None = None


class Executive(BaseModel):
    full_name: str
    title: str | None = None
    seniority: str | None = None
    email: str | None = None
    linkedin_url: str | None = None
    source_url: str | None = None


class CompanyEnrichment(BaseModel):
    raw_markdown: str | None = None
    summary_markdown: str | None = None
    report_status: str | None = None
    report_error: str | None = None
    search_queries: list[str] = Field(default_factory=list)
    query_planning_status: str | None = None
    """Information collected after enriching one company."""

    company_name: str
    domain: str | None = None

    description: str | None = None
    industry: str | None = None
    founded_year: int | None = None
    headquarters: str | None = None
    employee_count_text: str | None = None

    emails: list[str] = Field(default_factory=list)
    phones: list[str] = Field(default_factory=list)
    addresses: list[str] = Field(default_factory=list)
    social_links: dict[str, str] = Field(default_factory=dict)
    technologies: list[str] = Field(default_factory=list)
    executives: list[Executive] = Field(default_factory=list)

    tax_code: str | None = Field(default=None, description="Tax ID / business registration number")

    sources: list[EnrichmentSource] = Field(default_factory=list)
    pages_fetched: int = 0
    llm_calls: int = 0
    enriched_at: str | None = None

    def is_empty(self) -> bool:
        """True when no meaningful information was found; used to show the Enrich again button."""
        return not any(
            [
                self.description,
                self.emails,
                self.phones,
                self.addresses,
                self.executives,
                self.social_links,
                self.tax_code,
            ]
        )


class EnrichTarget(BaseModel):
    company_profile: Company | None = None
    """A company to enrich. At least a name or domain is required."""

    company_name: str
    domain: str | None = None
    extra_context: str | None = Field(
        default=None, description="Additional hint for the LLM/search, e.g. 'fintech in Ho Chi Minh City'"
    )


# ---------------------------------------------------------------------------
# Background jobs: shared status for all three types (enrichment, matching, messaging).
# ---------------------------------------------------------------------------

#: Lifecycle states for a background job. "pending" and "running" are *unfinished*
#: states; the client keeps polling, and jobs in either state on server restart
#: are marked failed (see `api/jobs.py`).
JobStatus = Literal["pending", "running", "completed", "failed"]

#: States that allow a job to continue. Named because all three runners check
#: this condition before claiming a job.
ACTIVE_JOB_STATUSES: tuple[JobStatus, ...] = ("pending", "running")


class BackgroundJobSummary(BaseModel):
    """Shared fields for all background jobs: identity, lifecycle, and progress.

    The three job types differ in their inputs and outputs, but share these
    fields. The frontend relies on this common shape to use one polling hook for
    all three. Keep them in one model so they stay aligned when fields are added.
    """

    id: str
    username: str
    status: JobStatus
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    total: int = 0
    completed: int = 0
    failed: int = 0
    current_target: str | None = Field(
        default=None, description="Current item being processed — used to display meaningful progress"
    )
    error: str | None = Field(default=None, description="Most recent error, not the only error")


class EnrichJobSummary(BackgroundJobSummary):
    """Enrichment job: read websites for a list of companies."""

    run_id: str | None = None


class EnrichJobDetail(EnrichJobSummary):
    targets: list[EnrichTarget] = Field(default_factory=list)
    results: list[CompanyEnrichment] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Your company's service catalog
# ---------------------------------------------------------------------------


class ServiceInput(BaseModel):
    """Fields users enter or edit for one catalog service.

    Separate from `Service` so clients cannot set id/created_at.

    These descriptions are what the LLM reads when scoring fit. More specific
    details (problems solved, typical customers) produce better rankings; a
    service name alone gives the LLM little to work with.
    """

    name: str = Field(min_length=1, description="Service name, e.g. 'ERP implementation'")
    category: str | None = Field(default=None, description="Service category, e.g. 'Consulting'")
    description: str = Field(default="", description="What the service does and what problem it solves")
    value_proposition: str | None = Field(
        default=None, description="Why customers choose you over competitors"
    )
    target_industries: list[str] = Field(default_factory=list)
    target_company_size: str | None = Field(
        default=None, description="Ideal customer size, e.g. '50–500 employees'"
    )
    keywords: list[str] = Field(
        default_factory=list, description="Signals that a company may need this service"
    )
    active: bool = Field(default=True, description="Disable to keep in the catalog without matching against it")


class Service(ServiceInput):
    """One saved catalog service.

    The catalog is system-wide (like Settings): the team shares one service list
    instead of maintaining individual copies.
    """

    id: str
    created_at: str
    updated_at: str
    updated_by: str | None = None


# ---------------------------------------------------------------------------
# Service-to-company matching (LLM scoring)
# ---------------------------------------------------------------------------

# Scores below this threshold are not worth pursuing; used for UI coloring and
# quick list filtering.
MATCH_SCORE_FLOOR = 40


class ServiceFit(BaseModel):
    """How well one company fits a particular service."""

    service_id: str
    service_name: str
    score: int = Field(ge=0, le=100)
    rationale: str = Field(default="", description="Reason for this score, grounded in observed facts")


class CompanyMatch(BaseModel):
    """One company after scoring against all selected services."""

    company_id: str | None = None
    company_name: str
    domain: str | None = None
    linkedin_url: str | None = None
    industry: str | None = None
    location: str | None = None
    employee_count: int | None = None

    overall_score: int = Field(default=0, ge=0, le=100)
    rank: int = 0
    best_service_id: str | None = None
    best_service_name: str | None = None
    summary: str = Field(default="", description="1–2 sentence summary of why to pursue or avoid this company")
    signals: list[str] = Field(default_factory=list, description="Supporting evidence")
    concerns: list[str] = Field(default_factory=list, description="Factors that reduce fit")

    service_fits: list[ServiceFit] = Field(default_factory=list)

    used_enrichment: bool = Field(
        default=False, description="Whether enrichment data was available or only search results were used"
    )
    error: str | None = Field(default=None, description="Reason scoring failed, if applicable")


class MatchRequest(BaseModel):
    """Matching request: a saved search run and selected services."""

    run_id: str = Field(description="ID of the search run in history")
    service_ids: list[str] = Field(min_length=1)
    objective: str | None = Field(
        default=None,
        description="Additional ranking criteria, e.g. 'prioritize companies expanding in the north'",
    )


class MatchJobSummary(BackgroundJobSummary):
    """Matching job: score a saved search run against the service catalog."""

    run_id: str
    objective: str | None = None


class MatchJobDetail(MatchJobSummary):
    services: list[Service] = Field(
        default_factory=list,
        description="Service snapshot at run time — later catalog edits do not change these results",
    )
    results: list[CompanyMatch] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Generate messages for contacts
# ---------------------------------------------------------------------------


class ChannelSpec(BaseModel):
    """Actual constraints for each messaging channel.

    These are **not** writing preferences; they are platform limits and measured
    results, so the code validates them instead of only putting them in the prompt:

    - LinkedIn connection requests have a hard 300-character limit (200 for free
      accounts); longer messages cannot be sent.
    - InMail: 200-character subject, 1,900-character body.
    - Cold email: Apollo found that 6–8 sentences have the highest reply rate, so
      this limit is based on word count rather than characters.
    """

    label: str
    has_subject: bool
    max_subject_chars: int | None = None
    max_body_chars: int | None = None
    max_body_words: int | None = None
    soft_body_chars: int | None = Field(
        default=None, description="Messages can still be sent above this limit, but should trigger a warning"
    )
    guidance: str = ""


MESSAGE_CHANNELS: dict[str, ChannelSpec] = {
    "email": ChannelSpec(
        label="Cold email",
        has_subject=True,
        max_subject_chars=60,
        max_body_words=125,
        guidance="6-8 sentences. One idea, one ask.",
    ),
    "followup_email": ChannelSpec(
        label="Follow-up email",
        has_subject=True,
        max_subject_chars=60,
        max_body_words=90,
        guidance="Shorter than the first email. Add something new; never just 'bumping this'.",
    ),
    "linkedin_connection": ChannelSpec(
        label="LinkedIn connection note",
        has_subject=False,
        max_body_chars=300,
        soft_body_chars=200,
        guidance="No pitch. Give a reason to accept, nothing more.",
    ),
    "linkedin_inmail": ChannelSpec(
        label="LinkedIn InMail",
        has_subject=True,
        max_subject_chars=200,
        max_body_chars=1900,
        max_body_words=150,
        guidance="Warmer than email; still one clear ask.",
    ),
}

MESSAGE_TONES = ["direct", "friendly", "formal", "consultative"]
MESSAGE_LANGUAGES = ["en", "vi"]

# Apollo measured a ~7.8% reply rate when contacting 1–2 people per company,
# dropping to ~3.8% when contacting 10 or more. Warn above this threshold rather
# than blocking; users may have a reason.
RECOMMENDED_CONTACTS_PER_COMPANY = 2


class MessageTarget(BaseModel):
    """One person who needs a generated message.

    The client sends company and person IDs from the search snapshot. Names are
    only for display and compatibility with older requests when names are unique.
    """

    company_id: str | None = None
    contact_id: str | None = None
    company_name: str
    contact_name: str


class GeneratedMessage(BaseModel):
    company_id: str | None = None
    contact_id: str | None = None
    company_name: str
    contact_name: str
    contact_title: str | None = None
    contact_email: str | None = None
    contact_linkedin_url: str | None = None

    channel: str
    language: str
    tone: str

    subject: str | None = None
    body: str = ""

    service_id: str | None = None
    service_name: str | None = Field(default=None, description="Service offered in the message")
    personalization_used: list[str] = Field(
        default_factory=list, description="Facts the LLM says it used to personalize the message"
    )

    subject_chars: int = 0
    body_chars: int = 0
    body_words: int = 0

    warnings: list[str] = Field(
        default_factory=list, description="Issues detected by code after the LLM returns a result"
    )
    error: str | None = None


class MessageRequest(BaseModel):
    run_id: str = Field(description="Search run containing these contacts")
    targets: list[MessageTarget] = Field(min_length=1)
    channel: str = "email"
    tone: str = "direct"
    language: str = "en"
    match_job_id: str | None = Field(
        default=None,
        description="Matching results with the best-fit service and rationale — makes messages much more relevant",
    )
    service_id: str | None = Field(
        default=None, description="Offer a specific service instead of the best-matching service"
    )
    custom_instructions: str | None = Field(
        default=None, description="Additional instruction, e.g. 'mention last week's conference'"
    )


class MessageJobSummary(BackgroundJobSummary):
    """Message generation job for a list of contacts."""

    run_id: str
    channel: str
    language: str
    tone: str
    notices: list[str] = Field(
        default_factory=list, description="Job-level warnings, e.g. too many selected contacts at one company"
    )


class MessageJobDetail(MessageJobSummary):
    results: list[GeneratedMessage] = Field(default_factory=list)


"""Data models dùng chung cho toàn bộ pipeline."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# Các mức seniority thường gặp (khớp với cách Apollo.io/PDL phân loại),
# dùng để lọc "các cấp cao" của công ty.
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
    """Input format mô tả mục tiêu tìm kiếm công ty.

    Đây chính là "1 input format" mà người dùng cung cấp để tool tìm ra
    danh sách công ty phù hợp trên LinkedIn.
    """

    industries: list[str] = Field(default_factory=list, description="Ngành nghề, vd: 'Software', 'Retail'")
    keywords: list[str] = Field(default_factory=list, description="Từ khoá mô tả công ty/lĩnh vực kinh doanh")
    locations: list[str] = Field(default_factory=list, description="Vị trí địa lý, vd: 'Vietnam', 'Ho Chi Minh City'")
    company_size_min: int | None = Field(default=None, ge=0)
    company_size_max: int | None = Field(default=None, ge=0)
    target_titles: list[str] = Field(
        default_factory=list, description="Chức danh cụ thể muốn tìm, vd: 'CEO', 'Head of Sales'"
    )
    seniority_levels: list[str] = Field(
        default_factory=lambda: list(DEFAULT_SENIOR_LEVELS),
        description="Các cấp bậc liên hệ muốn lấy ra (mặc định: các cấp quản lý cao trở lên)",
    )
    max_companies: int = Field(default=20, gt=0, description="Số lượng công ty tối đa cần tìm")
    max_contacts_per_company: int = Field(default=5, gt=0, description="Số liên hệ tối đa lấy ra mỗi công ty")


class Company(BaseModel):
    name: str
    linkedin_url: str | None = None
    domain: str | None = None
    industry: str | None = None
    location: str | None = None
    employee_count: int | None = None
    provider_id: str | None = Field(default=None, description="ID nội bộ của nhà cung cấp dữ liệu")


class Contact(BaseModel):
    full_name: str
    title: str | None = None
    seniority: str | None = None
    linkedin_url: str | None = None
    email: str | None = None
    company_name: str | None = None


class CompanyResult(BaseModel):
    """Kết quả cuối cùng: 1 công ty phù hợp kèm danh sách liên hệ cấp cao tìm được."""

    company: Company
    contacts: list[Contact] = Field(default_factory=list)


class SearchRunSummary(BaseModel):
    """1 dòng lịch sử tìm kiếm — đủ thông tin để hiển thị danh sách, chưa kèm
    kết quả đầy đủ (xem SearchRunDetail)."""

    id: str = Field(description="UUID, dùng để tra lại chi tiết/tải file")
    username: str
    created_at: str = Field(description="ISO 8601 UTC, vd: 2026-08-13T10:00:00+00:00")
    provider: str
    criteria: SearchCriteria
    total_companies: int
    total_contacts: int


class SearchRunDetail(SearchRunSummary):
    """1 lần tìm kiếm kèm đầy đủ kết quả — dùng khi xem lại 1 lần chạy trong lịch sử."""

    results: list[CompanyResult] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Cấu hình (trang Settings)
# ---------------------------------------------------------------------------

LLM_PROVIDERS = ["openrouter", "openai_compatible"]

# Nguồn dữ liệu công ty/liên hệ cho bước Search (bước 1). Hiện chỉ có Apollo,
# nhưng vẫn để dạng danh sách: `CompanyContactProvider` là điểm mở rộng có sẵn
# nên thêm nhà cung cấp sau này chỉ là thêm phần tử ở đây, không phải sửa form
# hay route. Frontend đọc danh sách này để dựng dropdown.
DATA_PROVIDERS = ["apollo"]

# Nhà cung cấp nào bắt buộc có API key. Tách riêng khỏi DATA_PROVIDERS vì có thể
# sau này thêm nguồn không cần key (vd: import file thủ công).
DATA_PROVIDERS_REQUIRING_KEY = ["apollo"]

# "none" = không dùng web search, chỉ đọc website của chính công ty.
SEARCH_PROVIDERS = ["none", "searxng", "brave", "tavily", "serper"]

# Provider nào cần API key, provider nào không — frontend dùng để hiện đúng ô nhập.
SEARCH_PROVIDERS_REQUIRING_KEY = ["brave", "tavily", "serper"]

MASKED_SECRET = "__SALETOOL_UNCHANGED__"
"""Giá trị frontend gửi lại khi người dùng KHÔNG sửa API key.

Backend không bao giờ trả key thật về client; nó trả về bản mask để hiển thị.
Khi lưu, nếu nhận lại đúng sentinel này thì giữ nguyên key cũ."""


class DataSourceSettings(BaseModel):
    """Nguồn dữ liệu cho bước Search.

    API key nằm ở đây (Settings) chứ không nằm trong form tìm kiếm: nó là cấu
    hình một lần của cả đội, không phải thứ gõ lại mỗi lần chạy. Nhờ vậy key
    cũng được mã hoá trước khi lưu như mọi key khác (xem saletool/crypto.py),
    thay vì đi qua form ở dạng thô mỗi lượt.
    """

    provider: str = "apollo"
    api_key: str | None = None


class LLMSettings(BaseModel):
    enabled: bool = True
    provider: str = "openrouter"
    api_key: str | None = None
    base_url: str = "https://openrouter.ai/api/v1"
    model: str = "google/gemini-2.0-flash-001"
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_output_tokens: int = Field(default=2048, gt=0)


class SearchSettings(BaseModel):
    provider: str = "none"
    api_key: str | None = None
    searxng_url: str | None = Field(
        default=None, description="URL instance SearXNG tự host, vd: http://localhost:8080"
    )
    max_results: int = Field(default=5, gt=0, le=50)


class EnrichmentSettings(BaseModel):
    """Bật/tắt từng tầng của pipeline enrich.

    Thứ tự chạy: structured data (rẻ + chính xác nhất) -> website công ty ->
    web search -> LLM (chỉ cho phần còn thiếu).
    """

    use_structured_data: bool = Field(
        default=True, description="Tầng 0: JSON-LD schema.org, thẻ meta, regex — không tốn LLM"
    )
    use_company_website: bool = Field(default=True, description="Đọc sitemap + crawl nông website công ty")
    use_web_search: bool = Field(default=False, description="Tìm các trang bên ngoài nói về công ty")
    use_llm: bool = Field(default=True, description="Dùng LLM trích xuất phần không parse được bằng code")
    use_browser_fallback: bool = Field(
        default=True, description="Dùng Playwright khi trang render bằng JS (chậm hơn nhiều)"
    )

    max_pages_per_company: int = Field(default=8, gt=0, le=50)
    request_timeout_seconds: float = Field(default=15.0, gt=0)
    request_delay_seconds: float = Field(
        default=1.0, ge=0, description="Nghỉ giữa 2 request tới cùng 1 domain — giữ mức lịch sự"
    )
    respect_robots_txt: bool = True
    user_agent: str = "SaleToolBot/1.0 (+contact: set-your-email@example.com)"

    auto_enrich_on_search: bool = Field(
        default=False, description="Tự động enrich toàn bộ công ty ngay sau khi search xong"
    )


class SenderProfile(BaseModel):
    """Bạn là ai — dùng khi sinh message gửi cho contact.

    Không có phần này thì LLM buộc phải bịa ra người gửi, và message sinh ra
    không dùng được. Vì vậy bước sinh message yêu cầu tối thiểu `full_name` và
    `company_name`.
    """

    full_name: str = ""
    title: str = ""
    company_name: str = ""
    company_description: str = Field(
        default="", description="Công ty bạn làm gì — 1-2 câu, LLM dùng để viết phần giới thiệu"
    )
    email: str = ""
    phone: str = ""
    calendar_link: str = Field(default="", description="Link đặt lịch, vd Calendly — dùng cho CTA")
    signature: str = Field(default="", description="Chữ ký chèn nguyên văn cuối email")

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
# Kết quả enrich
# ---------------------------------------------------------------------------


class EnrichmentSource(BaseModel):
    """Provenance — mỗi mẩu dữ liệu đến từ đâu.

    Đây là yêu cầu tuân thủ, không phải tính năng phụ: khi bị hỏi "dữ liệu này ở
    đâu ra?" phải trả lời được cho từng bản ghi.
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
    """Thông tin thu được sau khi enrich 1 công ty."""

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

    tax_code: str | None = Field(default=None, description="Mã số thuế / mã số doanh nghiệp")

    sources: list[EnrichmentSource] = Field(default_factory=list)
    pages_fetched: int = 0
    llm_calls: int = 0
    enriched_at: str | None = None

    def is_empty(self) -> bool:
        """True khi không thu được thông tin gì đáng kể — dùng để hiện nút Enrich lại."""
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
    """1 công ty cần enrich. Ít nhất phải có tên hoặc domain."""

    company_name: str
    domain: str | None = None
    extra_context: str | None = Field(
        default=None, description="Gợi ý thêm cho LLM/search, vd: 'fintech ở TP.HCM'"
    )


# ---------------------------------------------------------------------------
# Job nền: phần trạng thái chung của cả ba loại (enrich, matching, message)
# ---------------------------------------------------------------------------

#: Vòng đời của một job nền. "pending" và "running" là hai trạng thái *chưa
#: xong* — client còn poll, và job đang ở đó lúc server khởi động lại sẽ bị
#: đánh dấu failed (xem `api/jobs.py`).
JobStatus = Literal["pending", "running", "completed", "failed"]

#: Những trạng thái mà job còn được chạy tiếp. Đặt tên vì cả ba runner đều kiểm
#: đúng điều kiện này trước khi nhận job.
ACTIVE_JOB_STATUSES: tuple[JobStatus, ...] = ("pending", "running")


class BackgroundJobSummary(BaseModel):
    """Phần chung của mọi job nền — danh tính, vòng đời, tiến độ.

    Ba loại job khác nhau ở dữ liệu vào/ra, còn phần này thì giống hệt, và
    frontend dựa đúng vào chỗ giống hệt đó để dùng chung một hook poll cho cả
    ba. Gom vào một model để chúng không lệch nhau khi thêm trường.
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
        default=None, description="Đang xử lý cái gì — để UI hiện tiến độ có nghĩa"
    )
    error: str | None = Field(default=None, description="Lỗi gần nhất, không phải lỗi duy nhất")


class EnrichJobSummary(BackgroundJobSummary):
    """Job enrich: đọc website của một danh sách công ty."""


class EnrichJobDetail(EnrichJobSummary):
    targets: list[EnrichTarget] = Field(default_factory=list)
    results: list[CompanyEnrichment] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Catalog dịch vụ của chính công ty bạn
# ---------------------------------------------------------------------------


class ServiceInput(BaseModel):
    """Phần người dùng nhập/sửa cho 1 dịch vụ trong catalog.

    Tách khỏi `Service` để client không thể tự đặt id/created_at.

    Các trường mô tả ở đây chính là thứ LLM đọc khi chấm độ phù hợp. Mô tả càng
    cụ thể (bài toán giải quyết, khách hàng điển hình) thì xếp hạng càng sát —
    chỉ ghi mỗi tên dịch vụ thì LLM gần như không có gì để bám vào.
    """

    name: str = Field(min_length=1, description="Tên dịch vụ, vd: 'Triển khai ERP'")
    category: str | None = Field(default=None, description="Nhóm dịch vụ, vd: 'Consulting'")
    description: str = Field(default="", description="Dịch vụ làm gì, giải quyết vấn đề gì")
    value_proposition: str | None = Field(
        default=None, description="Vì sao khách chọn bạn thay vì đối thủ"
    )
    target_industries: list[str] = Field(default_factory=list)
    target_company_size: str | None = Field(
        default=None, description="Quy mô khách hàng phù hợp, vd: '50-500 nhân sự'"
    )
    keywords: list[str] = Field(
        default_factory=list, description="Tín hiệu cho thấy công ty đang cần dịch vụ này"
    )
    active: bool = Field(default=True, description="Tắt để giữ lại trong catalog nhưng không đem đi map")


class Service(ServiceInput):
    """1 dịch vụ đã lưu trong catalog.

    Catalog có phạm vi toàn hệ thống (giống Settings): cả đội bán chung một bộ
    dịch vụ, không phải mỗi người một bản riêng.
    """

    id: str
    created_at: str
    updated_at: str
    updated_by: str | None = None


# ---------------------------------------------------------------------------
# Mapping dịch vụ <-> công ty (LLM chấm điểm)
# ---------------------------------------------------------------------------

# Điểm dưới ngưỡng này coi như không đáng theo đuổi — dùng để tô màu ở UI và
# để lọc nhanh danh sách.
MATCH_SCORE_FLOOR = 40


class ServiceFit(BaseModel):
    """Mức phù hợp của 1 công ty với 1 dịch vụ cụ thể."""

    service_id: str
    service_name: str
    score: int = Field(ge=0, le=100)
    rationale: str = Field(default="", description="Vì sao chấm điểm này — bám vào dữ kiện có thật")


class CompanyMatch(BaseModel):
    """1 công ty sau khi đã chấm với toàn bộ dịch vụ được chọn."""

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
    summary: str = Field(default="", description="1-2 câu tóm tắt vì sao nên/không nên tiếp cận")
    signals: list[str] = Field(default_factory=list, description="Dữ kiện ủng hộ")
    concerns: list[str] = Field(default_factory=list, description="Điểm khiến độ phù hợp giảm")

    service_fits: list[ServiceFit] = Field(default_factory=list)

    used_enrichment: bool = Field(
        default=False, description="Có dữ liệu enrich để chấm hay chỉ có thông tin từ lần search"
    )
    error: str | None = Field(default=None, description="Chấm điểm thất bại thì ghi lý do ở đây")


class MatchRequest(BaseModel):
    """Yêu cầu map: lấy 1 lần search đã lưu + các dịch vụ được chọn."""

    run_id: str = Field(description="ID của lần search trong lịch sử")
    service_ids: list[str] = Field(min_length=1)
    objective: str | None = Field(
        default=None,
        description="Tiêu chí xếp hạng thêm, vd: 'ưu tiên công ty đang mở rộng ở miền Bắc'",
    )


class MatchJobSummary(BackgroundJobSummary):
    """Job matching: chấm một lần search đã lưu với catalog dịch vụ."""

    run_id: str
    objective: str | None = None


class MatchJobDetail(MatchJobSummary):
    services: list[Service] = Field(
        default_factory=list,
        description="Bản chụp dịch vụ lúc chạy — sửa catalog sau đó không làm sai lệch kết quả cũ",
    )
    results: list[CompanyMatch] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Sinh message gửi contact
# ---------------------------------------------------------------------------


class ChannelSpec(BaseModel):
    """Ràng buộc thật của từng kênh gửi.

    Đây **không** phải sở thích viết lách mà là giới hạn của nền tảng và số liệu
    đã đo được, nên code kiểm tra lại chứ không chỉ ghi vào prompt:

    - Lời mời kết nối LinkedIn cắt cứng ở 300 ký tự (tài khoản free chỉ 200) —
      viết dài hơn là gửi không được.
    - InMail: tiêu đề 200, thân 1900 ký tự.
    - Email lạnh: Apollo đo thấy email 6–8 câu cho tỉ lệ trả lời cao nhất, nên
      giới hạn ở đây theo số từ chứ không theo ký tự.
    """

    label: str
    has_subject: bool
    max_subject_chars: int | None = None
    max_body_chars: int | None = None
    max_body_words: int | None = None
    soft_body_chars: int | None = Field(
        default=None, description="Vượt mức này vẫn gửi được nhưng nên cảnh báo"
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

# Apollo đo: gửi 1-2 người/công ty đạt tỉ lệ trả lời ~7.8%, từ 10 người trở lên
# tụt còn ~3.8%. Vượt ngưỡng này thì cảnh báo chứ không chặn — đôi khi người
# dùng có lý do riêng.
RECOMMENDED_CONTACTS_PER_COMPANY = 2


class MessageTarget(BaseModel):
    """1 người cần viết message.

    Client chỉ gửi tên công ty + tên người; backend tự tra lại trong lần search
    đã lưu. Làm vậy để client không thể bịa ra contact không có trong dữ liệu.
    """

    company_name: str
    contact_name: str


class GeneratedMessage(BaseModel):
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
    service_name: str | None = Field(default=None, description="Dịch vụ được chào trong message")
    personalization_used: list[str] = Field(
        default_factory=list, description="Dữ kiện LLM khai là đã dùng để cá nhân hoá"
    )

    subject_chars: int = 0
    body_chars: int = 0
    body_words: int = 0

    warnings: list[str] = Field(
        default_factory=list, description="Vấn đề phát hiện bằng code sau khi LLM trả kết quả"
    )
    error: str | None = None


class MessageRequest(BaseModel):
    run_id: str = Field(description="Lần search chứa các contact này")
    targets: list[MessageTarget] = Field(min_length=1)
    channel: str = "email"
    tone: str = "direct"
    language: str = "en"
    match_job_id: str | None = Field(
        default=None,
        description="Kết quả matching để lấy dịch vụ khớp nhất + lý do — có thì message sát hơn hẳn",
    )
    service_id: str | None = Field(
        default=None, description="Ép chào 1 dịch vụ cụ thể thay vì lấy dịch vụ khớp nhất"
    )
    custom_instructions: str | None = Field(
        default=None, description="Yêu cầu thêm, vd: 'nhắc tới hội thảo tuần trước'"
    )


class MessageJobSummary(BackgroundJobSummary):
    """Job sinh message cho một danh sách contact."""

    run_id: str
    channel: str
    language: str
    tone: str
    notices: list[str] = Field(
        default_factory=list, description="Cảnh báo ở mức cả job, vd: chọn quá nhiều người 1 công ty"
    )


class MessageJobDetail(MessageJobSummary):
    results: list[GeneratedMessage] = Field(default_factory=list)


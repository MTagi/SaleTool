"""Provider dựa trên Apollo.io API (https://docs.apollo.io).

Apollo tổng hợp dữ liệu công ty/liên hệ (kèm link LinkedIn, chức danh, seniority)
và cung cấp qua REST API chính thức. Cần API key hợp lệ (biến môi trường
APOLLO_API_KEY hoặc truyền trực tiếp).

Bốn điều về API này cần biết vì nó quyết định cách code ở đây được viết:

1. **Base path là `/api/v1`**, không phải `/v1`.
2. **Tìm người phải dùng `mixed_people/api_search`**, không phải
   `mixed_people/search` — endpoint sau trả 403 trên gói Basic.
3. **Search KHÔNG trả email.** Kết quả chỉ cho biết người đó *có* email hay
   không; muốn lấy email thật phải gọi tiếp People Enrichment, và **đó mới là
   chỗ trừ credit**. Vì vậy ở đây chỉ enrich những người search đã báo là có
   email — trả tiền cho một lần tra chắc chắn trượt là vô nghĩa.
4. **`organization_industry_tag_ids` nhận tag ID của Apollo**, không nhận tên
   ngành. Người dùng gõ "Fintech" vào đó thì Apollo lặng lẽ bỏ qua. Xem
   `_industry_filters()`.
"""

from __future__ import annotations

import logging
import re

import httpx

from saletool.models import Company, Contact, SearchCriteria
from saletool.providers.base import CompanyContactProvider

logger = logging.getLogger(__name__)

API_BASE = "https://api.apollo.io/api/v1"
ORGANIZATION_SEARCH_URL = f"{API_BASE}/mixed_companies/search"
PEOPLE_SEARCH_URL = f"{API_BASE}/mixed_people/api_search"
PEOPLE_ENRICH_URL = f"{API_BASE}/people/bulk_match"

# Giới hạn của Apollo, không phải lựa chọn của chúng ta.
MAX_PER_PAGE = 100
BULK_MATCH_LIMIT = 10

# Tag ID của Apollo là chuỗi 24 ký tự hex (kiểu ObjectId).
_TAG_ID_RE = re.compile(r"^[0-9a-f]{24}$", re.IGNORECASE)

# Apollo trả email chưa mở khoá dưới dạng `email_not_unlocked@domain.com`.
# Chỉ khớp phần định danh, không khớp `@domain.com` — có công ty dùng domain đó thật.
_LOCKED_EMAIL_RE = re.compile(r"email_not_unlocked", re.IGNORECASE)

# Search chỉ nói "có email hay không". Các giá trị này nghĩa là có gì đó để lấy.
_WORTH_ENRICHING = {"verified", "likely", "guessed", "extrapolated"}


def _industry_filters(industries: list[str]) -> dict:
    """Tách tên ngành (tự do) khỏi tag ID thật của Apollo.

    Apollo có hai đường lọc ngành và chúng không thay thế được cho nhau:
    `organization_industry_tag_ids` cần đúng tag ID nội bộ, còn
    `q_organization_keyword_tags` khớp theo từ khoá trong mô tả công ty.

    Người dùng gõ tên ngành thì phải đi đường thứ hai — đẩy tên vào ô tag ID
    chỉ làm bộ lọc im lặng không có tác dụng. Ai đã tra được tag ID thật thì
    dán vào cùng ô đó và code tự nhận ra.
    """
    tag_ids = [i for i in industries if _TAG_ID_RE.match(i.strip())]
    keywords = [i for i in industries if not _TAG_ID_RE.match(i.strip())]

    filters: dict = {}
    if tag_ids:
        filters["organization_industry_tag_ids"] = tag_ids
    if keywords:
        filters["keyword_tags"] = keywords
    return filters


def _is_usable_email(email: str | None) -> bool:
    return bool(email) and not _LOCKED_EMAIL_RE.search(email or "")


def _worth_enriching(person: dict) -> bool:
    """Người này có đáng bỏ 1 credit ra tra email không?

    Apollo nói trước qua `has_email`/`email_status`. Bỏ qua bước kiểm này nghĩa
    là trả tiền cho cả những bản ghi chắc chắn không có email.
    """
    if _is_usable_email(person.get("email")):
        return False  # đã có sẵn, không cần tra
    if person.get("has_email") is True:
        return True
    return str(person.get("email_status") or "").lower() in _WORTH_ENRICHING


class ApolloProvider(CompanyContactProvider):
    name = "apollo"

    def __init__(
        self,
        api_key: str,
        client: httpx.Client | None = None,
        timeout: float = 30.0,
        reveal_emails: bool = True,
        reveal_personal_emails: bool = False,
    ):
        """`reveal_emails`: gọi People Enrichment để lấy email công việc.

        Bật mặc định vì danh sách liên hệ không có email thì gần như vô dụng —
        nhưng **bước này tốn credit**, nên tắt được bằng `reveal_emails=False`
        khi chỉ muốn khảo sát xem có bao nhiêu công ty/người khớp tiêu chí.

        `reveal_personal_emails` mặc định **tắt**: email cá nhân tốn thêm credit,
        và Apollo không trả về với người ở vùng áp dụng GDPR. Email công việc mới
        là thứ dùng cho B2B outreach.
        """
        if not api_key:
            raise ValueError("Thiếu Apollo API key (APOLLO_API_KEY)")
        self.api_key = api_key
        self._client = client or httpx.Client(timeout=timeout)
        self.reveal_emails = reveal_emails
        self.reveal_personal_emails = reveal_personal_emails

    def _headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "X-Api-Key": self.api_key,
        }

    def _post(self, url: str, payload: dict) -> dict:
        resp = self._client.post(url, json=payload, headers=self._headers())
        if resp.status_code == 403:
            raise RuntimeError(
                "Apollo trả 403 — API key không có quyền cho endpoint này. "
                "Kiểm tra gói thuê bao và xem key đã bật quyền API chưa."
            )
        resp.raise_for_status()
        return resp.json()

    # -- Công ty -----------------------------------------------------------

    def search_companies(self, criteria: SearchCriteria) -> list[Company]:
        """Lấy đủ `max_companies`, **có phân trang**.

        Apollo trả tối đa 100 bản ghi/trang. Trước đây code chỉ lấy trang 1 nên
        yêu cầu 250 công ty âm thầm chỉ ra 100 — không báo lỗi, chỉ thiếu.
        """
        keyword_tags = list(criteria.keywords)
        industry = _industry_filters(criteria.industries)
        keyword_tags += industry.pop("keyword_tags", [])

        base_payload: dict = dict(industry)
        if keyword_tags:
            base_payload["q_organization_keyword_tags"] = keyword_tags
        if criteria.locations:
            base_payload["organization_locations"] = criteria.locations
        if criteria.company_size_min is not None or criteria.company_size_max is not None:
            base_payload["organization_num_employees_ranges"] = [
                f"{criteria.company_size_min or 1},{criteria.company_size_max or ''}"
            ]

        companies: list[Company] = []
        page = 1
        while len(companies) < criteria.max_companies:
            remaining = criteria.max_companies - len(companies)
            payload = {**base_payload, "page": page, "per_page": min(remaining, MAX_PER_PAGE)}
            data = self._post(ORGANIZATION_SEARCH_URL, payload)

            organizations = data.get("organizations") or []
            if not organizations:
                break

            companies.extend(
                Company(
                    name=org.get("name", ""),
                    linkedin_url=org.get("linkedin_url"),
                    domain=org.get("primary_domain") or org.get("website_url"),
                    industry=org.get("industry"),
                    location=org.get("city") or org.get("country"),
                    employee_count=org.get("estimated_num_employees"),
                    provider_id=org.get("id"),
                )
                for org in organizations
            )

            # Apollo báo tổng số trang; hết trang thì dừng thay vì gọi thừa.
            total_pages = (data.get("pagination") or {}).get("total_pages")
            if total_pages is not None and page >= total_pages:
                break
            page += 1

        return companies[: criteria.max_companies]

    # -- Liên hệ -----------------------------------------------------------

    def search_contacts(self, company: Company, criteria: SearchCriteria) -> list[Contact]:
        if not company.provider_id:
            return []

        payload: dict = {
            "page": 1,
            "per_page": min(criteria.max_contacts_per_company, MAX_PER_PAGE),
            "organization_ids": [company.provider_id],
        }
        if criteria.seniority_levels:
            payload["person_seniorities"] = criteria.seniority_levels
        if criteria.target_titles:
            payload["person_titles"] = criteria.target_titles

        data = self._post(PEOPLE_SEARCH_URL, payload)
        people = (data.get("people") or [])[: criteria.max_contacts_per_company]

        if self.reveal_emails:
            people = self._reveal_emails(people)

        return [
            Contact(
                full_name=person.get("name", ""),
                title=person.get("title"),
                seniority=person.get("seniority"),
                linkedin_url=person.get("linkedin_url"),
                email=person.get("email") if _is_usable_email(person.get("email")) else None,
                company_name=company.name,
            )
            for person in people
        ]

    def _reveal_emails(self, people: list[dict]) -> list[dict]:
        """Tra email thật cho những người search báo là có email.

        Lỗi ở bước này **không** làm hỏng cả lần search: danh sách liên hệ không
        email vẫn dùng được (còn LinkedIn URL), mất cả danh sách thì không.
        """
        # Giữ vị trí trong danh sách gốc để ghép kết quả trả về đúng người.
        targets = [(i, p) for i, p in enumerate(people) if _worth_enriching(p)]
        if not targets:
            return people

        revealed: dict[int, str] = {}
        for start in range(0, len(targets), BULK_MATCH_LIMIT):
            chunk = targets[start : start + BULK_MATCH_LIMIT]
            batch = [person for _, person in chunk]
            payload = {
                "reveal_personal_emails": self.reveal_personal_emails,
                "details": [
                    {
                        k: v
                        for k, v in (
                            ("id", person.get("id")),
                            ("first_name", person.get("first_name")),
                            ("last_name", person.get("last_name")),
                            ("name", person.get("name")),
                            ("organization_name", (person.get("organization") or {}).get("name")),
                            ("linkedin_url", person.get("linkedin_url")),
                        )
                        if v
                    }
                    for person in batch
                ],
            }

            try:
                data = self._post(PEOPLE_ENRICH_URL, payload)
            except (httpx.HTTPError, RuntimeError) as exc:
                logger.warning("Apollo enrichment thất bại, bỏ qua email: %s", exc)
                return people

            # Apollo trả `matches` đúng thứ tự đã gửi, kể cả phần tử null.
            # strict=False có chủ đích: Apollo có lúc trả ít hơn số đã gửi.
            matches = data.get("matches") or []
            for (index, _), match in zip(chunk, matches, strict=False):
                if match and _is_usable_email(match.get("email")):
                    revealed[index] = match["email"]

        return [
            {**person, "email": revealed[i]} if i in revealed else person
            for i, person in enumerate(people)
        ]

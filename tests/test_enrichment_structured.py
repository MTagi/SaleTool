"""Test tầng 0 — chỗ này phải chính xác vì nó được ưu tiên hơn LLM."""

from saletool.enrichment.structured import extract_structured

JSON_LD_PAGE = """
<html><head>
<title>Acme Fintech</title>
<meta property="og:description" content="Nền tảng thanh toán cho SME." />
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Organization",
  "name": "Acme Fintech JSC",
  "email": "hello@acmefintech.vn",
  "telephone": "+84 28 1234 5678",
  "foundingDate": "2018-05-01",
  "address": {
    "@type": "PostalAddress",
    "streetAddress": "12 Nguyen Hue",
    "addressLocality": "Ho Chi Minh City",
    "addressCountry": "VN"
  },
  "sameAs": ["https://www.linkedin.com/company/acme-fintech", "https://facebook.com/acmefintech"]
}
</script>
</head><body>
<a href="mailto:sales@acmefintech.vn">Sales</a>
<a href="tel:+842899998888">Hotline</a>
</body></html>
"""


def test_extracts_from_json_ld():
    data = extract_structured(JSON_LD_PAGE, text="")

    assert data.name == "Acme Fintech JSC"
    assert data.founded_year == 2018
    assert "hello@acmefintech.vn" in data.emails
    assert "Ho Chi Minh City" in data.addresses[0]
    assert data.social_links["linkedin"] == "https://www.linkedin.com/company/acme-fintech"
    assert data.social_links["facebook"] == "https://facebook.com/acmefintech"


def test_extracts_mailto_and_tel_links():
    data = extract_structured(JSON_LD_PAGE, text="")

    assert "sales@acmefintech.vn" in data.emails

    digits_only = {"".join(ch for ch in p if ch.isdigit()) for p in data.phones}
    assert "842899998888" in digits_only  # từ tel:
    assert "842812345678" in digits_only  # từ JSON-LD telephone


def test_falls_back_to_meta_and_title():
    html = """
    <html><head>
    <title>Beta Payments</title>
    <meta name="description" content="Cổng thanh toán." />
    </head><body></body></html>
    """
    data = extract_structured(html, text="")

    assert data.name == "Beta Payments"
    assert data.description == "Cổng thanh toán."


def test_tax_code_needs_a_nearby_keyword():
    # Có từ khoá -> nhận
    with_kw = extract_structured("<html></html>", text="Mã số thuế: 0312345678")
    assert with_kw.tax_code == "0312345678"

    # Không có từ khoá -> không nhận (tránh bắt nhầm số điện thoại/số nhà)
    without_kw = extract_structured("<html></html>", text="Số tài khoản 0312345678")
    assert without_kw.tax_code is None


def test_filters_out_noise_emails():
    data = extract_structured(
        "<html></html>", text="lien he: real@company.vn hoac noreply@example.com"
    )

    assert "real@company.vn" in data.emails
    assert "noreply@example.com" not in data.emails


def test_handles_broken_html_without_raising():
    data = extract_structured("<html><head><script>{bad json</script><div>", text="")
    assert data is not None


def test_deduplicates_emails_case_insensitively():
    data = extract_structured("<html></html>", text="A@Company.vn and a@company.vn")
    assert data.emails == ["a@company.vn"]


# --- Hồi quy: 2 lỗi phát hiện khi chạy thật với website mẫu ---


def test_tax_code_is_not_reported_as_a_phone_number():
    """Mã số thuế VN cũng là 10 chữ số bắt đầu bằng 0 -> khớp pattern số ĐT."""
    data = extract_structured(
        "<html></html>", text="Mã số thuế: 0312345678. Hotline: 028 3822 1234"
    )

    assert data.tax_code == "0312345678"
    assert all("0312345678" not in p.replace(" ", "") for p in data.phones)
    assert any("38221234" in p.replace(" ", "") for p in data.phones)


def test_same_phone_in_different_formats_is_deduplicated():
    from saletool.enrichment.structured import normalize_phone

    # Ba cách viết phổ biến của cùng một số.
    assert normalize_phone("+84 28 3822 1234") == normalize_phone("+842838221234")
    assert normalize_phone("028 3822 1234") == normalize_phone("+842838221234")

    data = extract_structured(
        "<html></html>", text="Tel: +84 28 3822 1234 hoac 028 3822 1234"
    )
    assert len(data.phones) == 1


SHARE_BUTTON_PAGE = """
<html><body>
<a href="https://www.facebook.com/sharer/sharer.php?u=https://acme.vn">Share</a>
<a href="https://twitter.com/intent/tweet?url=https://acme.vn">Tweet</a>
<a href="https://www.linkedin.com/shareArticle?url=https://acme.vn">Share</a>
<a href="https://www.youtube.com/watch?v=abc123">Xem video</a>
<a href="https://www.facebook.com/acmevn">Fanpage</a>
<a href="https://www.linkedin.com/company/acme-vn/ ">LinkedIn</a>
</body></html>
"""


def test_share_buttons_are_not_treated_as_company_profiles():
    data = extract_structured(SHARE_BUTTON_PAGE, text="")

    # Nút share nằm trước link thật trong HTML — link thật vẫn phải thắng.
    assert data.social_links["facebook"] == "https://www.facebook.com/acmevn"
    assert "sharer" not in data.social_links["facebook"]
    assert "twitter" not in data.social_links  # chỉ có intent/tweet -> bỏ hẳn
    assert "youtube" not in data.social_links  # /watch là video, không phải kênh


def test_social_url_is_stripped():
    data = extract_structured(SHARE_BUTTON_PAGE, text="")

    assert data.social_links["linkedin"] == "https://www.linkedin.com/company/acme-vn/"


def test_href_with_leading_whitespace_is_still_recognised():
    """href trải trên nhiều dòng bắt đầu bằng xuống dòng/khoảng trắng.

    Trước đây bị loại ngay ở bước startswith() nên link mất hẳn, dù
    social_profile() có strip — vì strip chạy sau cái cổng đó.
    """
    html = """
    <html><body>
      <a href="
          https://www.linkedin.com/company/acme-vn
      ">LinkedIn</a>
      <a href="  mailto:sales@acme.vn  ">Email</a>
      <a href=" tel:+842838221234 ">Hotline</a>
    </body></html>
    """
    data = extract_structured(html, text="")

    assert data.social_links.get("linkedin") == "https://www.linkedin.com/company/acme-vn"
    assert "sales@acme.vn" in data.emails
    assert data.phones, "tel: có khoảng trắng đầu bị mất"

import pytest

from saletool.seniority import infer_seniority


@pytest.mark.parametrize(
    "title,expected",
    [
        ("Chief Executive Officer", "c_suite"),
        ("CEO", "c_suite"),
        ("Founder & CEO", "founder"),  # founder checked before c_suite
        ("Co-Founder", "founder"),
        ("VP of Business Development", "vp"),
        ("Head of Sales", "head"),
        ("Director of Marketing", "director"),
        ("Sales Manager", "manager"),
        ("Software Engineer", None),
        ("", None),
        (None, None),
    ],
)
def test_infer_seniority(title, expected):
    assert infer_seniority(title) == expected

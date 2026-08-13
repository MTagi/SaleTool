import pytest
from fastapi.testclient import TestClient

from saletool.web.app import app
from saletool.web.users_db import create_user


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "web_test_users.db"
    monkeypatch.setenv("SALETOOL_DB_PATH", str(db_path))
    create_user("alice", "s3cret-pass", path=db_path)

    with TestClient(app) as c:
        yield c


def test_dashboard_redirects_when_not_logged_in(client):
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"


def test_login_wrong_password_shows_error(client):
    resp = client.post("/login", data={"username": "alice", "password": "wrong"})
    assert resp.status_code == 401
    assert "Sai tên đăng nhập" in resp.text


def test_login_success_reaches_dashboard(client):
    resp = client.post("/login", data={"username": "alice", "password": "s3cret-pass"}, follow_redirects=True)
    assert resp.status_code == 200
    assert "Tìm công ty" in resp.text


def test_search_with_mock_provider_and_download(client):
    client.post("/login", data={"username": "alice", "password": "s3cret-pass"})

    resp = client.post(
        "/search",
        data={
            "industries": "",
            "keywords": "fintech",
            "locations": "",
            "company_size_min": "",
            "company_size_max": "",
            "target_titles": "",
            "seniority_levels": ["c_suite", "vp"],
            "max_companies": "3",
            "max_contacts_per_company": "2",
            "provider": "mock",
        },
    )
    assert resp.status_code == 200
    assert "fintech Company 1" in resp.text
    assert "3 công ty" in resp.text

    csv_resp = client.get("/download/csv")
    assert csv_resp.status_code == 200
    assert "text/csv" in csv_resp.headers["content-type"]
    assert "fintech Company 1" in csv_resp.text


def test_logout_clears_session(client):
    client.post("/login", data={"username": "alice", "password": "s3cret-pass"})
    resp = client.get("/logout", follow_redirects=False)
    assert resp.status_code == 303

    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/login"

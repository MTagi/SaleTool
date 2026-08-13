import pytest
from fastapi.testclient import TestClient

from saletool.api.app import app
from saletool.db.sqlite_repo import SQLiteUserRepository
from saletool.security import hash_password


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "api_test_users.db"
    monkeypatch.setenv("SALETOOL_DB_BACKEND", "sqlite")
    monkeypatch.setenv("SALETOOL_DB_PATH", str(db_path))

    repo = SQLiteUserRepository(db_path)
    repo.create_user("alice", hash_password("s3cret-pass"))
    repo.create_user("bob", hash_password("another-pass"))

    with TestClient(app) as c:
        yield c


def _login(client, username="alice", password="s3cret-pass") -> str:
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def test_login_wrong_password_returns_401(client):
    resp = client.post("/api/auth/login", json={"username": "alice", "password": "wrong"})
    assert resp.status_code == 401


def test_login_success_returns_token(client):
    resp = client.post("/api/auth/login", json={"username": "alice", "password": "s3cret-pass"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["username"] == "alice"
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_me_requires_token(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_me_with_valid_token(client):
    token = _login(client)
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == {"username": "alice"}


def test_search_requires_auth(client):
    resp = client.post("/api/search", data={"provider": "mock"})
    assert resp.status_code == 401


def test_search_with_mock_provider_and_download(client):
    token = _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.post(
        "/api/search",
        headers=headers,
        data={
            "keywords": "fintech",
            "seniority_levels": ["c_suite", "vp"],
            "max_companies": "3",
            "max_contacts_per_company": "2",
            "provider": "mock",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_companies"] == 3
    assert body["total_contacts"] == 6
    assert body["companies"][0]["company"]["name"].startswith("fintech")

    csv_resp = client.get("/api/download/csv", headers=headers)
    assert csv_resp.status_code == 200
    assert "text/csv" in csv_resp.headers["content-type"]
    assert "fintech Company 1" in csv_resp.text

    json_resp = client.get("/api/download/json", headers=headers)
    assert json_resp.status_code == 200
    assert "application/json" in json_resp.headers["content-type"]


def test_download_without_prior_search_returns_404(client):
    # Dùng "bob" (chưa từng chạy search) để không bị đụng _results_store của
    # "alice" từ các test khác trong cùng tiến trình pytest.
    token = _login(client, username="bob", password="another-pass")
    resp = client.get("/api/download/csv", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404


def test_search_apollo_without_api_key_returns_400(client):
    token = _login(client)
    resp = client.post(
        "/api/search",
        headers={"Authorization": f"Bearer {token}"},
        data={"provider": "apollo"},
    )
    assert resp.status_code == 400

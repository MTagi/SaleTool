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


def _run_search(client, headers, **overrides):
    data = {
        "keywords": "fintech",
        "seniority_levels": ["c_suite", "vp"],
        "max_companies": "3",
        "max_contacts_per_company": "2",
        "provider": "mock",
    }
    data.update(overrides)
    return client.post("/api/search", headers=headers, data=data)


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

    resp = _run_search(client, headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["run_id"]
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
    # "bob" chưa từng chạy search — lịch sử được lưu DB, tách theo user.
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


def test_search_persists_history_across_multiple_runs(client):
    token = _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    first = _run_search(client, headers, keywords="fintech").json()
    second = _run_search(client, headers, keywords="payments").json()

    runs = client.get("/api/search/runs", headers=headers).json()
    assert [r["id"] for r in runs] == [second["run_id"], first["run_id"]]
    assert runs[0]["provider"] == "mock"
    assert runs[0]["criteria"]["keywords"] == ["payments"]


def test_get_run_detail_returns_full_results(client):
    token = _login(client)
    headers = {"Authorization": f"Bearer {token}"}
    run = _run_search(client, headers).json()

    resp = client.get(f"/api/search/runs/{run['run_id']}", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == run["run_id"]
    assert len(body["results"]) == 3


def test_get_run_detail_404_for_unknown_id(client):
    token = _login(client)
    resp = client.get("/api/search/runs/not-a-real-id", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404


def test_get_run_detail_404_for_other_users_run(client):
    alice_headers = {"Authorization": f"Bearer {_login(client)}"}
    run = _run_search(client, alice_headers).json()

    bob_headers = {"Authorization": f"Bearer {_login(client, username='bob', password='another-pass')}"}
    resp = client.get(f"/api/search/runs/{run['run_id']}", headers=bob_headers)
    assert resp.status_code == 404


def test_download_specific_run_by_id(client):
    token = _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    first = _run_search(client, headers, keywords="fintech").json()
    _run_search(client, headers, keywords="payments").json()  # 2nd run becomes "latest"

    resp = client.get(f"/api/download/csv?run_id={first['run_id']}", headers=headers)
    assert resp.status_code == 200
    assert "fintech Company 1" in resp.text


def test_change_password_requires_auth(client):
    resp = client.post(
        "/api/auth/change-password",
        json={"current_password": "s3cret-pass", "new_password": "brand-new-pass"},
    )
    assert resp.status_code == 401


def test_change_password_wrong_current_password_returns_401(client):
    token = _login(client)
    resp = client.post(
        "/api/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": "wrong", "new_password": "brand-new-pass"},
    )
    assert resp.status_code == 401


def test_change_password_too_short_returns_400(client):
    token = _login(client)
    resp = client.post(
        "/api/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": "s3cret-pass", "new_password": "short"},
    )
    assert resp.status_code == 400


def test_change_password_success_then_login_with_new_password(client):
    token = _login(client)
    resp = client.post(
        "/api/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": "s3cret-pass", "new_password": "brand-new-pass"},
    )
    assert resp.status_code == 200

    assert client.post("/api/auth/login", json={"username": "alice", "password": "s3cret-pass"}).status_code == 401
    assert client.post("/api/auth/login", json={"username": "alice", "password": "brand-new-pass"}).status_code == 200

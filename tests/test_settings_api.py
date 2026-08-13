import pytest
from fastapi.testclient import TestClient

from saletool.api.app import app
from saletool.db.sqlite_repo import SQLiteUserRepository
from saletool.models import MASKED_SECRET
from saletool.security import hash_password


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "settings_test.db"
    monkeypatch.setenv("SALETOOL_DB_BACKEND", "sqlite")
    monkeypatch.setenv("SALETOOL_DB_PATH", str(db_path))
    monkeypatch.setenv("SALETOOL_SECRET_KEY", "c" * 64)

    SQLiteUserRepository(db_path).create_user("alice", hash_password("s3cret-pass"))

    with TestClient(app) as c:
        yield c


def _auth(client) -> dict:
    resp = client.post("/api/auth/login", json={"username": "alice", "password": "s3cret-pass"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _valid_payload(**overrides) -> dict:
    payload = {
        "llm": {
            "enabled": True,
            "provider": "openrouter",
            "api_key": "sk-or-v1-testkey1234",
            "base_url": "https://openrouter.ai/api/v1",
            "model": "google/gemini-2.0-flash-001",
            "temperature": 0.0,
            "max_output_tokens": 2048,
        },
        "search": {"provider": "none", "api_key": None, "searxng_url": None, "max_results": 5},
        "enrichment": {
            "use_structured_data": True,
            "use_company_website": True,
            "use_web_search": False,
            "use_llm": True,
            "use_browser_fallback": True,
            "max_pages_per_company": 8,
            "request_timeout_seconds": 15.0,
            "request_delay_seconds": 1.0,
            "respect_robots_txt": True,
            "user_agent": "SaleToolBot/1.0",
            "auto_enrich_on_search": False,
        },
    }
    payload.update(overrides)
    return payload


def test_settings_requires_auth(client):
    assert client.get("/api/settings").status_code == 401


def test_defaults_returned_when_never_saved(client):
    resp = client.get("/api/settings", headers=_auth(client))

    assert resp.status_code == 200
    body = resp.json()
    assert body["settings"]["search"]["provider"] == "none"
    assert body["settings"]["llm"]["api_key"] is None
    assert "searxng" in body["options"]["search_providers"]


def test_api_key_is_never_returned_in_clear(client):
    headers = _auth(client)
    client.put("/api/settings", headers=headers, json=_valid_payload())

    body = client.get("/api/settings", headers=headers).json()

    assert body["settings"]["llm"]["api_key"] == "••••••••1234"
    assert "sk-or-v1-testkey1234" not in resp_text(body)
    assert body["settings"]["llm"]["api_key_set"] is True


def resp_text(payload) -> str:
    import json

    return json.dumps(payload)


def test_masked_sentinel_keeps_existing_key(client):
    headers = _auth(client)
    client.put("/api/settings", headers=headers, json=_valid_payload())

    # Lưu lại mà không sửa key -> key cũ phải được giữ nguyên.
    payload = _valid_payload()
    payload["llm"]["api_key"] = MASKED_SECRET
    payload["llm"]["model"] = "meta-llama/llama-3.3-70b-instruct"
    resp = client.put("/api/settings", headers=headers, json=payload)

    assert resp.status_code == 200
    assert resp.json()["settings"]["llm"]["api_key"] == "••••••••1234"
    assert resp.json()["settings"]["llm"]["model"] == "meta-llama/llama-3.3-70b-instruct"


def test_resending_the_mask_also_keeps_existing_key(client):
    headers = _auth(client)
    client.put("/api/settings", headers=headers, json=_valid_payload())

    payload = _valid_payload()
    payload["llm"]["api_key"] = "••••••••1234"
    resp = client.put("/api/settings", headers=headers, json=payload)

    assert resp.json()["settings"]["llm"]["api_key_set"] is True


def test_rejects_paid_search_provider_without_key(client):
    payload = _valid_payload()
    payload["search"] = {"provider": "brave", "api_key": None, "searxng_url": None, "max_results": 5}

    resp = client.put("/api/settings", headers=_auth(client), json=payload)

    assert resp.status_code == 400
    assert "API key" in resp.json()["detail"]


def test_rejects_searxng_without_url(client):
    payload = _valid_payload()
    payload["search"] = {"provider": "searxng", "api_key": None, "searxng_url": None, "max_results": 5}

    resp = client.put("/api/settings", headers=_auth(client), json=payload)

    assert resp.status_code == 400
    assert "instance URL" in resp.json()["detail"]


def test_rejects_web_search_enabled_with_no_provider(client):
    payload = _valid_payload()
    payload["enrichment"]["use_web_search"] = True  # search.provider vẫn là "none"

    resp = client.put("/api/settings", headers=_auth(client), json=payload)

    assert resp.status_code == 400


def test_rejects_llm_enabled_without_key(client):
    payload = _valid_payload()
    payload["llm"]["api_key"] = None

    resp = client.put("/api/settings", headers=_auth(client), json=payload)

    assert resp.status_code == 400


def test_rejects_unknown_search_provider(client):
    payload = _valid_payload()
    payload["search"] = {"provider": "hax0r", "api_key": "k", "searxng_url": None, "max_results": 5}

    resp = client.put("/api/settings", headers=_auth(client), json=payload)
    assert resp.status_code == 400


def test_settings_persist_across_requests(client):
    headers = _auth(client)
    payload = _valid_payload()
    payload["enrichment"]["max_pages_per_company"] = 3
    client.put("/api/settings", headers=headers, json=payload)

    body = client.get("/api/settings", headers=headers).json()

    assert body["settings"]["enrichment"]["max_pages_per_company"] == 3
    assert body["settings"]["updated_by"] == "alice"

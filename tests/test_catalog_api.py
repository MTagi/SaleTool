import pytest
from fastapi.testclient import TestClient

from saletool.api.app import app
from saletool.db.sqlite_repo import SQLiteUserRepository
from saletool.security import hash_password


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "catalog_test.db"
    monkeypatch.setenv("SALETOOL_DB_BACKEND", "sqlite")
    monkeypatch.setenv("SALETOOL_DB_PATH", str(db_path))
    monkeypatch.setenv("SALETOOL_SECRET_KEY", "e" * 64)

    repo = SQLiteUserRepository(db_path)
    repo.create_user("alice", hash_password("s3cret-pass"))
    repo.create_user("bob", hash_password("another-pass"))

    with TestClient(app) as c:
        yield c


def _auth(client, username="alice", password="s3cret-pass") -> dict:
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _service(**overrides) -> dict:
    payload = {
        "name": "ERP implementation",
        "category": "Consulting",
        "description": "End-to-end SAP B1 rollout for manufacturers.",
        "value_proposition": "Fixed price, live in 12 weeks.",
        "target_industries": ["Manufacturing", "Logistics"],
        "target_company_size": "50-500 employees",
        "keywords": ["legacy ERP", "manual reporting"],
        "active": True,
    }
    payload.update(overrides)
    return payload


def test_catalog_requires_auth(client):
    assert client.get("/api/catalog").status_code == 401
    assert client.post("/api/catalog", json=_service()).status_code == 401


def test_catalog_starts_empty(client):
    assert client.get("/api/catalog", headers=_auth(client)).json() == []


def test_create_returns_the_saved_service(client):
    resp = client.post("/api/catalog", headers=_auth(client), json=_service())

    assert resp.status_code == 201
    body = resp.json()
    assert body["id"]
    assert body["name"] == "ERP implementation"
    assert body["target_industries"] == ["Manufacturing", "Logistics"]
    assert body["updated_by"] == "alice"
    assert body["created_at"] == body["updated_at"]


def test_created_service_shows_up_in_the_list(client):
    headers = _auth(client)
    client.post("/api/catalog", headers=headers, json=_service())

    services = client.get("/api/catalog", headers=headers).json()
    assert len(services) == 1
    assert services[0]["name"] == "ERP implementation"


def test_catalog_is_shared_between_users(client):
    """Catalog là của công ty, không phải của từng người — bob phải thấy đúng
    thứ alice thêm vào, khác với lịch sử search."""
    client.post("/api/catalog", headers=_auth(client), json=_service())

    bob_view = client.get("/api/catalog", headers=_auth(client, "bob", "another-pass")).json()
    assert len(bob_view) == 1


def test_update_replaces_fields_and_stamps_the_editor(client):
    headers = _auth(client)
    service_id = client.post("/api/catalog", headers=headers, json=_service()).json()["id"]

    bob = _auth(client, "bob", "another-pass")
    resp = client.put(
        f"/api/catalog/{service_id}",
        headers=bob,
        json=_service(name="ERP migration", keywords=[], active=False),
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "ERP migration"
    assert body["keywords"] == []
    assert body["active"] is False
    assert body["updated_by"] == "bob"
    assert body["id"] == service_id


def test_update_keeps_the_original_created_at(client):
    headers = _auth(client)
    created = client.post("/api/catalog", headers=headers, json=_service()).json()

    updated = client.put(
        f"/api/catalog/{created['id']}", headers=headers, json=_service(name="Renamed")
    ).json()

    assert updated["created_at"] == created["created_at"]


def test_updating_an_unknown_id_is_404(client):
    resp = client.put("/api/catalog/nope", headers=_auth(client), json=_service())
    assert resp.status_code == 404


def test_delete_removes_it(client):
    headers = _auth(client)
    service_id = client.post("/api/catalog", headers=headers, json=_service()).json()["id"]

    assert client.delete(f"/api/catalog/{service_id}", headers=headers).status_code == 204
    assert client.get("/api/catalog", headers=headers).json() == []


def test_deleting_twice_is_404(client):
    headers = _auth(client)
    service_id = client.post("/api/catalog", headers=headers, json=_service()).json()["id"]

    client.delete(f"/api/catalog/{service_id}", headers=headers)
    assert client.delete(f"/api/catalog/{service_id}", headers=headers).status_code == 404


def test_blank_name_is_rejected(client):
    resp = client.post("/api/catalog", headers=_auth(client), json=_service(name="   "))
    assert resp.status_code == 400


def test_whitespace_and_empty_list_entries_are_cleaned(client):
    resp = client.post(
        "/api/catalog",
        headers=_auth(client),
        json=_service(
            name="  Data platform  ",
            category="   ",
            target_industries=["Retail", "  ", " Fintech "],
            keywords=[""],
        ),
    )

    body = resp.json()
    assert body["name"] == "Data platform"
    assert body["category"] is None  # chuỗi toàn khoảng trắng -> None, không phải ""
    assert body["target_industries"] == ["Retail", "Fintech"]
    assert body["keywords"] == []


def test_services_are_listed_by_name(client):
    headers = _auth(client)
    for name in ("Zeta audit", "alpha rollout", "Middle service"):
        client.post("/api/catalog", headers=headers, json=_service(name=name))

    names = [s["name"] for s in client.get("/api/catalog", headers=headers).json()]
    assert names == ["alpha rollout", "Middle service", "Zeta audit"]

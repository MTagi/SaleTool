import pytest

from saletool.db.sqlite_repo import SQLiteSearchRunRepository, SQLiteUserRepository
from saletool.models import Company, CompanyResult, Contact, SearchCriteria


@pytest.fixture
def repo(tmp_path):
    return SQLiteUserRepository(tmp_path / "test_users.db")


def test_create_and_get_password_hash(repo):
    repo.create_user("alice", "hashed-pw")

    assert repo.get_password_hash("alice") == "hashed-pw"
    assert repo.get_password_hash("bob") is None


def test_create_duplicate_user_raises(repo):
    repo.create_user("alice", "hashed-pw")

    with pytest.raises(ValueError):
        repo.create_user("alice", "another-hash")


def test_create_user_rejects_empty_fields(repo):
    with pytest.raises(ValueError):
        repo.create_user("", "hashed-pw")
    with pytest.raises(ValueError):
        repo.create_user("alice", "")


def test_update_password_hash(repo):
    repo.create_user("alice", "old-hash")

    repo.update_password_hash("alice", "new-hash")

    assert repo.get_password_hash("alice") == "new-hash"


def test_update_password_hash_unknown_user_raises(repo):
    with pytest.raises(ValueError):
        repo.update_password_hash("nobody", "new-hash")


@pytest.fixture
def run_repo(tmp_path):
    return SQLiteSearchRunRepository(tmp_path / "test_runs.db")


def _sample_results() -> list[CompanyResult]:
    return [
        CompanyResult(
            company=Company(name="Acme Fintech", industry="Financial Services"),
            contacts=[Contact(full_name="Nguyen Van A", title="CEO", seniority="c_suite")],
        )
    ]


def test_save_and_get_run(run_repo):
    criteria = SearchCriteria(keywords=["fintech"], max_companies=5)
    results = _sample_results()

    summary = run_repo.save_run(username="alice", provider="mock", criteria=criteria, results=results)

    assert summary.id
    assert summary.total_companies == 1
    assert summary.total_contacts == 1

    detail = run_repo.get_run("alice", summary.id)
    assert detail is not None
    assert detail.criteria.keywords == ["fintech"]
    assert detail.results[0].company.name == "Acme Fintech"
    assert detail.results[0].contacts[0].full_name == "Nguyen Van A"


def test_get_run_scoped_to_owner(run_repo):
    criteria = SearchCriteria()
    summary = run_repo.save_run(username="alice", provider="mock", criteria=criteria, results=[])

    assert run_repo.get_run("bob", summary.id) is None
    assert run_repo.get_run("alice", "not-a-real-id") is None


def test_list_runs_most_recent_first(run_repo):
    criteria = SearchCriteria()
    first = run_repo.save_run(username="alice", provider="mock", criteria=criteria, results=[])
    second = run_repo.save_run(username="alice", provider="csv_import", criteria=criteria, results=[])
    run_repo.save_run(username="bob", provider="mock", criteria=criteria, results=[])

    runs = run_repo.list_runs("alice")

    assert [r.id for r in runs] == [second.id, first.id]
    assert all(r.username == "alice" for r in runs)


def test_get_latest_run(run_repo):
    criteria = SearchCriteria()
    run_repo.save_run(username="alice", provider="mock", criteria=criteria, results=[])
    second = run_repo.save_run(username="alice", provider="mock", criteria=criteria, results=_sample_results())

    latest = run_repo.get_latest_run("alice")

    assert latest.id == second.id
    assert latest.results[0].company.name == "Acme Fintech"


def test_get_latest_run_none_when_no_history(run_repo):
    assert run_repo.get_latest_run("nobody") is None


def test_ordering_holds_for_many_saves_in_the_same_clock_tick(run_repo):
    """The two ordering tests above were flaky on Windows.

    The system clock advances in ~15.6 ms increments, so consecutive saves may
    share `created_at`. When timestamps match, `ORDER BY created_at` leaves the
    order to the database engine. Thirty records in a tight loop will fall in
    one tick; correct ordering proves the issue is fixed.

    This affects more than tests: it can misorder History and make `/api/download`
    without run_id return the wrong run.
    """
    criteria = SearchCriteria()
    saved = [
        run_repo.save_run(username="alice", provider="mock", criteria=criteria, results=[])
        for _ in range(30)
    ]

    # Test precondition: records must actually be saved close together.
    assert saved[-1].created_at > saved[0].created_at

    runs = run_repo.list_runs("alice", limit=30)
    assert [r.id for r in runs] == [s.id for s in reversed(saved)]
    assert run_repo.get_latest_run("alice").id == saved[-1].id


def test_ordering_survives_rows_written_before_the_monotonic_clock(run_repo, monkeypatch):
    """OLD rows in a real database can still share created_at; `rowid` breaks those ties.

    Simulate this by freezing the clock so every record has the same timestamp.
    """
    frozen = "2026-09-01T00:00:00+00:00"
    monkeypatch.setattr("saletool.db.sqlite_repo.now_iso", lambda: frozen)

    criteria = SearchCriteria()
    saved = [
        run_repo.save_run(username="alice", provider="mock", criteria=criteria, results=[])
        for _ in range(10)
    ]
    assert len({s.created_at for s in saved}) == 1, "timestamps must match to reproduce the case"

    runs = run_repo.list_runs("alice", limit=10)
    assert [r.id for r in runs] == [s.id for s in reversed(saved)]
    assert run_repo.get_latest_run("alice").id == saved[-1].id


def test_every_settings_api_key_is_encrypted_at_rest(tmp_path, monkeypatch):
    """All three keys must be encrypted before storage, not just llm/search.

    The Apollo key was previously missed: DataSourceSettings promised it would be
    encrypted like every other key, but the repository encrypted only llm/search,
    leaving it in plaintext in the .db file — the exact accidental exposure
    crypto.py is meant to prevent.
    """
    import sqlite3

    from saletool.db.sqlite_repo import SQLiteSettingsRepository
    from saletool.models import AppSettings

    monkeypatch.setenv("SALETOOL_SECRET_KEY", "0" * 64)
    path = tmp_path / "settings.db"
    repo = SQLiteSettingsRepository(path)

    settings = AppSettings()
    settings.llm.api_key = "sk-llm-plaintext"
    settings.search.api_key = "sk-search-plaintext"
    settings.data_source.api_key = "sk-apollo-plaintext"
    repo.save_settings(settings, updated_by="alice")

    with sqlite3.connect(path) as conn:
        raw = conn.execute("SELECT settings_json FROM app_settings WHERE id = 1").fetchone()[0]

    for secret in ("sk-llm-plaintext", "sk-search-plaintext", "sk-apollo-plaintext"):
        assert secret not in raw

    # Reading it back must return the real key; otherwise Apollo/LLM receive garbage.
    loaded = repo.get_settings()
    assert loaded.llm.api_key == "sk-llm-plaintext"
    assert loaded.search.api_key == "sk-search-plaintext"
    assert loaded.data_source.api_key == "sk-apollo-plaintext"


def test_apollo_key_saved_before_the_fix_still_reads_back(tmp_path, monkeypatch):
    """Existing plaintext values must remain readable: decrypt() passes through
    values without the prefix, and the next save upgrades them automatically."""
    import json
    import sqlite3

    from saletool.db.sqlite_repo import SQLiteSettingsRepository
    from saletool.models import AppSettings

    monkeypatch.setenv("SALETOOL_SECRET_KEY", "0" * 64)
    path = tmp_path / "settings.db"
    repo = SQLiteSettingsRepository(path)
    repo.save_settings(AppSettings(), updated_by="alice")

    legacy = AppSettings().model_dump(mode="json")
    legacy["data_source"]["api_key"] = "sk-apollo-legacy"
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE app_settings SET settings_json = ? WHERE id = 1", (json.dumps(legacy),))

    assert repo.get_settings().data_source.api_key == "sk-apollo-legacy"

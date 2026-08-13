import pytest

from saletool.db.factory import get_search_run_repository, get_user_repository
from saletool.db.sqlite_repo import SQLiteSearchRunRepository, SQLiteUserRepository


def test_factory_defaults_to_sqlite(tmp_path, monkeypatch):
    monkeypatch.delenv("SALETOOL_DB_BACKEND", raising=False)
    monkeypatch.setenv("SALETOOL_DB_PATH", str(tmp_path / "users.db"))

    repo = get_user_repository()

    assert isinstance(repo, SQLiteUserRepository)


def test_factory_unknown_backend_raises(monkeypatch):
    monkeypatch.setenv("SALETOOL_DB_BACKEND", "not-a-real-backend")

    with pytest.raises(ValueError):
        get_user_repository()


def test_search_run_factory_defaults_to_sqlite(tmp_path, monkeypatch):
    monkeypatch.delenv("SALETOOL_DB_BACKEND", raising=False)
    monkeypatch.setenv("SALETOOL_DB_PATH", str(tmp_path / "runs.db"))

    repo = get_search_run_repository()

    assert isinstance(repo, SQLiteSearchRunRepository)


def test_search_run_factory_unknown_backend_raises(monkeypatch):
    monkeypatch.setenv("SALETOOL_DB_BACKEND", "not-a-real-backend")

    with pytest.raises(ValueError):
        get_search_run_repository()

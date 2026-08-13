"""Test MongoUserRepository/MongoSearchRunRepository qua mongomock — không cần
MongoDB server thật, nhưng dùng cùng driver pymongo thật (chỉ khác client) nên
khớp hành vi thực tế."""

import mongomock
import pytest

from saletool.db.mongo_repo import MongoSearchRunRepository, MongoUserRepository
from saletool.models import Company, CompanyResult, Contact, SearchCriteria


@pytest.fixture
def repo():
    client = mongomock.MongoClient()
    return MongoUserRepository(uri="mongodb://unused", db_name="testdb", client=client)


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


@pytest.fixture
def run_repo():
    client = mongomock.MongoClient()
    return MongoSearchRunRepository(uri="mongodb://unused", db_name="testdb", client=client)


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

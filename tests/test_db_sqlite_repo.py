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
    """Hai test xếp thứ tự phía trên từng chớp tắt trên Windows.

    Lý do: đồng hồ hệ thống nhảy từng ~15,6ms nên nhiều lần lưu liên tiếp nhận
    đúng cùng một `created_at`, và `ORDER BY created_at` khi bằng nhau thì thứ
    tự do engine tự quyết. 30 bản ghi lưu trong một vòng lặp chặt chắc chắn rơi
    vào cùng một tick — nếu thứ tự vẫn đúng thì lỗi đó đã hết.

    Đây không chỉ là chuyện của test: cùng lỗi làm trang History xếp sai và
    `/api/download` không kèm run_id trả về nhầm lần chạy.
    """
    criteria = SearchCriteria()
    saved = [
        run_repo.save_run(username="alice", provider="mock", criteria=criteria, results=[])
        for _ in range(30)
    ]

    # Tiền đề của bài test: chúng phải thực sự được lưu sát nhau.
    assert saved[-1].created_at > saved[0].created_at

    runs = run_repo.list_runs("alice", limit=30)
    assert [r.id for r in runs] == [s.id for s in reversed(saved)]
    assert run_repo.get_latest_run("alice").id == saved[-1].id


def test_ordering_survives_rows_written_before_the_monotonic_clock(run_repo, monkeypatch):
    """Dòng CŨ trong DB thật vẫn có created_at trùng nhau — tiebreaker `rowid` lo phần đó.

    Giả lập bằng cách đóng băng đồng hồ, để mọi bản ghi mang đúng một mốc.
    """
    frozen = "2026-09-01T00:00:00+00:00"
    monkeypatch.setattr("saletool.db.sqlite_repo.now_iso", lambda: frozen)

    criteria = SearchCriteria()
    saved = [
        run_repo.save_run(username="alice", provider="mock", criteria=criteria, results=[])
        for _ in range(10)
    ]
    assert len({s.created_at for s in saved}) == 1, "phải trùng mốc thì mới đúng tình huống cần thử"

    runs = run_repo.list_runs("alice", limit=10)
    assert [r.id for r in runs] == [s.id for s in reversed(saved)]
    assert run_repo.get_latest_run("alice").id == saved[-1].id

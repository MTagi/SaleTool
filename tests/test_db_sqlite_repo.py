import pytest

from saletool.db.sqlite_repo import SQLiteUserRepository


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

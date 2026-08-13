import pytest

from saletool.web.users_db import create_user, verify_user


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test_users.db"


def test_create_and_verify_user(db_path):
    create_user("alice", "s3cret-pass", path=db_path)

    assert verify_user("alice", "s3cret-pass", path=db_path)
    assert not verify_user("alice", "wrong-pass", path=db_path)
    assert not verify_user("bob", "s3cret-pass", path=db_path)


def test_create_duplicate_user_raises(db_path):
    create_user("alice", "s3cret-pass", path=db_path)

    with pytest.raises(ValueError):
        create_user("alice", "another-pass", path=db_path)


def test_create_user_rejects_empty_fields(db_path):
    with pytest.raises(ValueError):
        create_user("", "s3cret-pass", path=db_path)
    with pytest.raises(ValueError):
        create_user("alice", "", path=db_path)

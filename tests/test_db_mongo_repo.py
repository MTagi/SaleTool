"""Test MongoUserRepository qua mongomock — không cần MongoDB server thật,
nhưng dùng cùng driver pymongo thật (chỉ khác client) nên khớp hành vi thực tế."""

import mongomock
import pytest

from saletool.db.mongo_repo import MongoUserRepository


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

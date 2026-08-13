import pytest

from saletool.crypto import decrypt, encrypt, mask


@pytest.fixture(autouse=True)
def secret_key(monkeypatch):
    monkeypatch.setenv("SALETOOL_SECRET_KEY", "a" * 64)


def test_encrypt_decrypt_roundtrip():
    encrypted = encrypt("sk-or-v1-secret-value")

    assert encrypted != "sk-or-v1-secret-value"
    assert encrypted.startswith("enc:v1:")
    assert decrypt(encrypted) == "sk-or-v1-secret-value"


def test_encrypt_is_idempotent():
    once = encrypt("my-key")
    twice = encrypt(once)

    assert twice == once
    assert decrypt(twice) == "my-key"


def test_empty_values_pass_through():
    assert encrypt(None) is None
    assert encrypt("") is None
    assert decrypt(None) is None


def test_plaintext_legacy_value_returned_as_is():
    # Giá trị lưu từ trước khi bật mã hoá vẫn đọc được.
    assert decrypt("legacy-plaintext-key") == "legacy-plaintext-key"


def test_decrypt_returns_none_when_secret_key_changed(monkeypatch):
    encrypted = encrypt("my-key")
    monkeypatch.setenv("SALETOOL_SECRET_KEY", "b" * 64)

    assert decrypt(encrypted) is None


def test_encrypt_requires_secret_key(monkeypatch):
    monkeypatch.delenv("SALETOOL_SECRET_KEY", raising=False)

    with pytest.raises(RuntimeError):
        encrypt("my-key")


def test_mask_hides_all_but_last_four():
    assert mask("sk-or-v1-abcdefgh1234") == "••••••••1234"
    assert mask("abc") == "•••"
    assert mask(None) is None

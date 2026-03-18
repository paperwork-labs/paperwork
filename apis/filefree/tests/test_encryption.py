import pytest
from cryptography.fernet import Fernet

from app.utils.encryption import decrypt, encrypt


def test_encrypt_decrypt_round_trip() -> None:
    plaintext = "123-45-6789"
    ciphertext = encrypt(plaintext)
    assert ciphertext != plaintext
    assert decrypt(ciphertext) == plaintext


def test_encrypt_produces_different_output_each_time() -> None:
    plaintext = "same-input"
    c1 = encrypt(plaintext)
    c2 = encrypt(plaintext)
    assert c1 != c2
    assert decrypt(c1) == decrypt(c2) == plaintext


def test_decrypt_with_wrong_data_raises() -> None:
    wrong_key = Fernet.generate_key().decode()
    f = Fernet(wrong_key.encode())
    ciphertext = f.encrypt(b"test").decode()

    with pytest.raises(ValueError, match="Decryption failed"):
        decrypt(ciphertext)


def test_encrypt_empty_string() -> None:
    ciphertext = encrypt("")
    assert decrypt(ciphertext) == ""

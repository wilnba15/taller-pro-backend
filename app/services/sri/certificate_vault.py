import os

from cryptography.fernet import Fernet, InvalidToken


def _get_fernet() -> Fernet:
    key = os.getenv("SRI_CERT_MASTER_KEY")

    if not key:
        raise ValueError(
            "Falta SRI_CERT_MASTER_KEY en las variables de entorno"
        )

    try:
        return Fernet(key.encode("utf-8"))
    except Exception as exc:
        raise ValueError(
            "SRI_CERT_MASTER_KEY no tiene un formato Fernet válido"
        ) from exc


def encrypt_bytes(data: bytes) -> str:
    if not data:
        raise ValueError("No se puede cifrar un archivo vacío")

    return _get_fernet().encrypt(data).decode("utf-8")


def decrypt_bytes(ciphertext: str) -> bytes:
    try:
        return _get_fernet().decrypt(ciphertext.encode("utf-8"))
    except InvalidToken as exc:
        raise ValueError(
            "No se pudo descifrar el certificado del taller"
        ) from exc


def encrypt_text(value: str) -> str:
    return encrypt_bytes(value.encode("utf-8"))


def decrypt_text(ciphertext: str) -> str:
    return decrypt_bytes(ciphertext).decode("utf-8")

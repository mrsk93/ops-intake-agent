from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class EncryptedCredential:
    ciphertext: str
    key_version: str
    algorithm: str = "external-kms-v1"


class CredentialEncryptionPort(Protocol):
    async def encrypt(self, plaintext: str, *, key_version: str) -> EncryptedCredential: ...

    async def decrypt(self, credential: EncryptedCredential) -> str: ...


class CredentialEncryptionUnavailable:
    async def encrypt(self, plaintext: str, *, key_version: str) -> EncryptedCredential:
        del plaintext, key_version
        raise RuntimeError("CREDENTIAL_ENCRYPTION_NOT_CONFIGURED")

    async def decrypt(self, credential: EncryptedCredential) -> str:
        del credential
        raise RuntimeError("CREDENTIAL_ENCRYPTION_NOT_CONFIGURED")


class DeterministicTestCipher:
    """Test-only reversible cipher; never use it for production credentials."""

    async def encrypt(self, plaintext: str, *, key_version: str) -> EncryptedCredential:
        key = hashlib.sha256(key_version.encode()).digest()
        raw = plaintext.encode()
        encrypted = bytes(value ^ key[index % len(key)] for index, value in enumerate(raw))
        return EncryptedCredential(
            ciphertext=base64.urlsafe_b64encode(encrypted).decode(),
            key_version=key_version,
            algorithm="deterministic-test-only",
        )

    async def decrypt(self, credential: EncryptedCredential) -> str:
        key = hashlib.sha256(credential.key_version.encode()).digest()
        encrypted = base64.urlsafe_b64decode(credential.ciphertext.encode())
        raw = bytes(value ^ key[index % len(key)] for index, value in enumerate(encrypted))
        return raw.decode()

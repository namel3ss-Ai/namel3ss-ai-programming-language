from __future__ import annotations

import base64
import hashlib
import hmac
import os

from ..errors import Namel3ssError


def hash_password(password: str, iterations: int = 600_000) -> str:
    if not isinstance(password, str):
        raise Namel3ssError("Password must be a string.")
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return "pbkdf2_sha256${}${}${}".format(
        iterations,
        base64.b64encode(salt).decode("utf-8"),
        base64.b64encode(dk).decode("utf-8"),
    )


def verify_password(password: str, password_hash: str) -> bool:
    try:
        scheme, iter_str, salt_b64, hash_b64 = password_hash.split("$", 3)
        if scheme != "pbkdf2_sha256":
            raise ValueError("Unsupported password hash scheme")
        iterations = int(iter_str)
        salt = base64.b64decode(salt_b64.encode("utf-8"))
        expected = base64.b64decode(hash_b64.encode("utf-8"))
    except Exception:
        raise Namel3ssError("Invalid password hash format.")
    try:
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    except Exception:
        return False
    return hmac.compare_digest(candidate, expected)

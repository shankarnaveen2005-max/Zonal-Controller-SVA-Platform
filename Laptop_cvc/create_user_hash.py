"""Create a PBKDF2 password hash for SVA_USERS_JSON deployment secrets."""

import hashlib
import secrets


password = input("Password (visible): ")
salt = secrets.token_bytes(16)
iterations = 310_000
digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
print(
    f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"
)

from passlib.context import CryptContext


pwd_context = CryptContext(
    # New website passwords use PBKDF2-SHA256, which accepts the API's 128
    # character limit and avoids bcrypt's 72-byte boundary. Keep bcrypt as a
    # deprecated verifier so pre-existing bot/admin hashes remain valid.
    schemes=["pbkdf2_sha256", "bcrypt"],
    deprecated="auto",
)


def hash_password(password: str):
    return pwd_context.hash(password)


def verify_password(
    password: str,
    hashed: str,
):
    return pwd_context.verify(
        password,
        hashed,
    )

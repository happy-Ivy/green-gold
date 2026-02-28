import hashlib
import secrets

def hash_otp(otp: str, salt: str) -> str:
    return hashlib.sha256((salt + otp).encode("utf-8")).hexdigest()

def gen_otp() -> str:
    # 6 digits
    return f"{secrets.randbelow(1_000_000):06d}"

def gen_code(length: int = 8) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # avoid confusing chars
    return "".join(secrets.choice(alphabet) for _ in range(length))

import hashlib
import secrets
import string

def gen_otp() -> str:
    """6 位數 OTP"""
    return f"{secrets.randbelow(1_000_000):06d}"

def hash_otp(otp: str) -> str:
    """OTP 雜湊（避免明碼存 DB）"""
    return hashlib.sha256(otp.encode("utf-8")).hexdigest()

def gen_code(length: int = 8) -> str:
    """交易代碼（預設 8 碼，大寫英數）"""
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))
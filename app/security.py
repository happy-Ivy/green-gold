import hashlib
import hmac
import os
import random
import string

def gen_otp(length: int = 6) -> str:
    return "".join(random.choice(string.digits) for _ in range(length))

def hash_otp(otp: str) -> str:
    secret = os.getenv("APP_HASH_SECRET", "CHANGE_ME_HASH_SECRET")
    return hmac.new(secret.encode(), otp.encode(), hashlib.sha256).hexdigest()

def verify_otp(otp: str, otp_hash: str) -> bool:
    return hmac.compare_digest(hash_otp(otp), otp_hash)
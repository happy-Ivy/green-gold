import secrets
import string

def gen_code(length: int = 8) -> str:
    """交易代碼（預設 8 碼，大寫英數）"""
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))
import random
import string

def gen_prefix_3letters() -> str:
    return "".join(random.choices(string.ascii_uppercase, k=3))

def format_points_3digits(points: int) -> str:
    return f"{points:03d}"

def gen_tx_code_6(points: int) -> str:
    # 每次都重新隨機前三碼
    return gen_prefix_3letters() + format_points_3digits(points)
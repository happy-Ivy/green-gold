import os
from aiosmtplib import SMTP
from email.message import EmailMessage

def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default)

async def send_otp_email(to_email: str, otp: str) -> None:
    dev_print = _env("DEV_PRINT_OTP", "1") == "1"
    if dev_print:
        print(f"[DEV OTP] Send to {to_email}: {otp}")
        return

    host = _env("SMTP_HOST")
    port = int(_env("SMTP_PORT", "587"))
    username = _env("SMTP_USERNAME")
    password = _env("SMTP_PASSWORD")
    from_email = _env("SMTP_FROM", username)

    if not host or not username or not password:
        raise RuntimeError("SMTP env not configured. Set SMTP_HOST/SMTP_USERNAME/SMTP_PASSWORD.")

    msg = EmailMessage()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = "Your Green Points login code"
    msg.set_content(f"Your OTP code is: {otp}\nThis code expires in 10 minutes.")

    smtp = SMTP(hostname=host, port=port, start_tls=True)
    await smtp.connect()
    await smtp.login(username, password)
    await smtp.send_message(msg)
    await smtp.quit()

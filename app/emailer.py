import os
import httpx

async def send_otp_email(to_email: str, otp: str) -> None:
    """
    Send OTP email.
    Priority:
      1) If RESEND_API_KEY exists -> send via Resend API (recommended on Railway)
      2) Else, if DEV_PRINT_OTP=1 -> print OTP to logs (dev mode)
      3) Else -> raise error (avoid SMTP timeout on Railway)
    """
    dev_print = os.getenv("DEV_PRINT_OTP", "0") == "1"

    resend_key = os.getenv("RESEND_API_KEY", "").strip()
    email_from = os.getenv("EMAIL_FROM", "onboarding@resend.dev").strip()

    if resend_key:
        subject = "Green Points 驗證碼"
        html = f"""
        <div style="font-family:Arial,sans-serif;line-height:1.6">
          <h2>Green Points 驗證碼</h2>
          <p>你的驗證碼是：</p>
          <div style="font-size:28px;font-weight:bold;letter-spacing:2px">{otp}</div>
          <p>此驗證碼 10 分鐘內有效。</p>
        </div>
        """

        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {resend_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": email_from,
                    "to": [to_email],
                    "subject": subject,
                    "html": html,
                },
            )
            if r.status_code >= 400:
                raise RuntimeError(f"Resend send failed: {r.status_code} {r.text}")
        return

    # Dev fallback
    if dev_print:
        print(f"[DEV OTP] Send to {to_email}: {otp}")
        return

    raise RuntimeError(
        "Email provider not configured. Set RESEND_API_KEY (recommended) or DEV_PRINT_OTP=1."
    )
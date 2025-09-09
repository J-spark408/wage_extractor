import os, smtplib, ssl
from email.message import EmailMessage
from email.utils import formataddr

# -------------------------
# Request forgot pin to email
# -------------------------

def send_pin_email(to_email: str, pin: str):
    host = os.environ.get("SMTP_HOST")
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER")
    pwd  = os.environ.get("SMTP_PASSWORD")
    from_addr = formataddr(("Info from Jspark", os.environ.get("EMAIL_FROM", user)))

    if not all([host, port, user, pwd, from_addr]):
        raise RuntimeError("SMTP is not configured (missing env vars).")

    msg = EmailMessage()
    msg["Subject"] = "Your new access PIN"  
    msg["From"] = from_addr
    msg["To"] = to_email
    msg.set_content(
        f"Hello,\n\nYour new PIN is: {pin}\n\n"
        f"If you didn't request this, you can ignore this email or contact support."  # CHANGED
    )

    context = ssl.create_default_context()
    with smtplib.SMTP(host, port) as server:
        server.starttls(context=context)
        server.login(user, pwd)
        server.send_message(msg)
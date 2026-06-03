import smtplib
import os

from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()

EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")


def send_fire_alert(message_body):

    msg = MIMEText(message_body)

    msg["Subject"] = "🔥 Fire Risk Alert"
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_SENDER

    server = smtplib.SMTP(
        "smtp.gmail.com",
        587
    )

    server.starttls()

    server.login(
        EMAIL_SENDER,
        EMAIL_PASSWORD
    )

    server.sendmail(
        EMAIL_SENDER,
        EMAIL_SENDER,
        msg.as_string()
    )

    server.quit()

    print("✅ Alert sent!")
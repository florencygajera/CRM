import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

def send_email_smtp(*, host: str, port: int, username: str, password: str,
                   to_email: str, subject: str, body: str,
                   attachment_bytes: bytes | None = None,
                   attachment_name: str = "attachment.pdf"):
    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = username
    msg["To"] = to_email

    msg.attach(MIMEText(body, "plain", "utf-8"))

    if attachment_bytes:
        part = MIMEApplication(attachment_bytes, Name=attachment_name)
        part["Content-Disposition"] = f'attachment; filename="{attachment_name}"'
        msg.attach(part)

    server = smtplib.SMTP(host, port)
    server.starttls()
    server.login(username, password)
    server.sendmail(username, [to_email], msg.as_string())
    server.quit()

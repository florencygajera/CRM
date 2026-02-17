from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Optional

from app.core.config import settings
from app.integration.email import send_email_smtp
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.tasks.ping_task")
def ping_task():
    print("✅ CELERY PING OK:", datetime.now())
    return "pong"


def _hash_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


@celery_app.task(
    name="app.workers.tasks.send_email",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 5},
)
def send_email(self, to_email: str, subject: str, body: str, attachment_bytes: Optional[bytes]=None, attachment_name: str="receipt.pdf"):
    send_email_smtp(
        host=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        username=settings.SMTP_USER,
        password=settings.SMTP_PASS,
        to_email=to_email,
        subject=subject,
        body=body,
        attachment_bytes=attachment_bytes,
        attachment_name=attachment_name,
    )
    return {"ok": True, "attachment_sha256": _hash_bytes(attachment_bytes) if attachment_bytes else None}


@celery_app.task(
    name="app.workers.tasks.send_booking_email",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 5},
)
def send_booking_email(self, to_email: str, subject: str, body: str, attachment_bytes: Optional[bytes]=None, attachment_name: str="receipt.pdf"):
    send_email_smtp(
        host=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        username=settings.SMTP_USER,
        password=settings.SMTP_PASS,
        to_email=to_email,
        subject=subject,
        body=body,
        attachment_bytes=attachment_bytes,
        attachment_name=attachment_name,
    )
    return {"ok": True, "attachment_sha256": _hash_bytes(attachment_bytes) if attachment_bytes else None}

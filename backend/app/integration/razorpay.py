import hmac, hashlib, json
from typing import Any

def verify_razorpay_webhook_signature(raw_body: bytes, signature: str, webhook_secret: str) -> bool:
    digest = hmac.new(webhook_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, signature)

def rupees_to_paisa(amount_rupees: float) -> int:
    # Razorpay expects integer paisa
    return int(round(float(amount_rupees) * 100))

def verify_razorpay_checkout_signature(order_id: str, payment_id: str, signature: str, key_secret: str) -> bool:
    msg = f"{order_id}|{payment_id}".encode()
    expected = hmac.new(key_secret.encode(), msg, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)

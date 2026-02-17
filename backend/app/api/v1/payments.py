import uuid
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.deps import get_db, get_token_payload
from app.core.config import settings
from app.integration.razorpay import verify_razorpay_webhook_signature
from app.integration.razorpay_client import client

from app.models.appointment import Appointment, PaymentStatus as ApptPayStatus
from app.models.customer import Customer
from app.models.payment import Payment, PaymentProvider, PaymentStatus
from app.models.payment_event import PaymentEvent
from app.schemas.payment import CreateRazorpayOrderIn, CreateRazorpayOrderOut
from app.schemas.payment import RazorpayVerifyIn
from app.integration.razorpay import verify_razorpay_checkout_signature
from app.schemas.payment import RefundIn
router = APIRouter(prefix="/payments", tags=["Payments"])


@router.post("/razorpay/order", response_model=CreateRazorpayOrderOut)
def create_razorpay_order(
    body: CreateRazorpayOrderIn,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_token_payload),
):
    # Safely get tenant_id from payload
    tenant_id_str = payload.get("tenant_id")
    if not tenant_id_str:
        raise HTTPException(status_code=400, detail="Missing tenant_id in token")
    try:
        tenant_id = uuid.UUID(tenant_id_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid tenant_id format")
    
    appt_id = body.appointment_id

    appt = db.scalar(select(Appointment).where(Appointment.tenant_id == tenant_id, Appointment.id == appt_id))
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")

    # Set due on appointment
    appt.amount_due = body.amount
    appt.currency = body.currency
    appt.payment_status = ApptPayStatus.UNPAID

    # Create Razorpay order (SDK)
    order = client.order.create({
        "amount": int(round(float(body.amount) * 100)),  # paisa
        "currency": body.currency,
        "receipt": f"appt_{appt_id}",
        "notes": {"tenant_id": str(tenant_id), "appointment_id": str(appt_id)},
    })
    provider_order_id = order["id"]

    customer = db.scalar(select(Customer).where(Customer.tenant_id == tenant_id, Customer.id == appt.customer_id))

    # Create payment row
    pay = Payment(
        tenant_id=tenant_id,
        appointment_id=appt.id,
        customer_id=appt.customer_id,
        provider=PaymentProvider.RAZORPAY,
        status=PaymentStatus.CREATED,
        amount=body.amount,
        currency=body.currency,
        provider_order_id=provider_order_id,
    )
    db.add(pay)
    db.flush()  # ensures pay.id is available without commit

    # Store "order.created" event
    db.add(PaymentEvent(
        tenant_id=tenant_id,
        provider=PaymentProvider.RAZORPAY,
        event_type="order.created",
        provider_event_id=provider_order_id,
        provider_payment_id=None,
        provider_order_id=provider_order_id,
        payload=order,
    ))

    db.commit()
    db.refresh(pay)

    return {
        "success": True,
        "data": {
            "payment_id": str(pay.id),
            "provider": pay.provider,
            "provider_order_id": pay.provider_order_id,
            "amount": float(pay.amount),
            "currency": pay.currency,
            "razorpay_key_id": settings.RAZORPAY_KEY_ID,
            "customer": {
                "name": customer.full_name if customer else "",
                "email": customer.email if customer else "",
                "phone": customer.phone if customer else "",
            },
        },
    }


@router.post("/razorpay/webhook")
async def razorpay_webhook(request: Request, db: Session = Depends(get_db)):
    raw = await request.body()
    sig = request.headers.get("X-Razorpay-Signature", "")
    if not sig:
        raise HTTPException(status_code=400, detail="Missing signature")

    if not verify_razorpay_webhook_signature(raw, sig, settings.RAZORPAY_WEBHOOK_SECRET):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    payload_json = await request.json()
    event_type = payload_json.get("event", "")
    event_id = payload_json.get("payload", {}).get("payment", {}).get("entity", {}).get("id")
    
    # Handle case where event_id might be in order entity
    if not event_id:
        event_id = payload_json.get("payload", {}).get("order", {}).get("entity", {}).get("id")
    # Handle case where event_id might be in refund entity
    if not event_id:
        event_id = payload_json.get("payload", {}).get("refund", {}).get("entity", {}).get("id")

    # Safe extraction for multiple webhook types
    payment_entity = ((payload_json.get("payload") or {}).get("payment") or {}).get("entity") or {}
    order_entity = ((payload_json.get("payload") or {}).get("order") or {}).get("entity") or {}
    refund_entity = ((payload_json.get("payload") or {}).get("refund") or {}).get("entity") or {}

    provider_order_id = (
        payment_entity.get("order_id")
        or order_entity.get("id")
        or refund_entity.get("order_id")
        or ""
    )
    provider_payment_id = (
        payment_entity.get("id")
        or refund_entity.get("payment_id")
        or ""
    )
    status = (
        payment_entity.get("status")
        or order_entity.get("status")
        or refund_entity.get("status")
        or ""
    )

    # Resolve tenant_id from notes if possible
    notes = payment_entity.get("notes") or order_entity.get("notes") or {}
    tenant_id_str = notes.get("tenant_id")

    pay = None
    if tenant_id_str and provider_order_id:
        try:
            tenant_uuid = uuid.UUID(tenant_id_str)
            pay = db.scalar(select(Payment).where(
                Payment.tenant_id == tenant_uuid,
                Payment.provider_order_id == provider_order_id
            ))
        except Exception:
            pay = None

    # Fallback: find by provider_order_id only if not found above
    if not pay and provider_order_id:
        pay = db.scalar(select(Payment).where(Payment.provider_order_id == provider_order_id))

    if not pay:
        # accept webhook but do nothing (idempotent)
        return {"success": True}

    # Idempotency check
    if event_id:
        existing = db.scalar(
            select(PaymentEvent).where(
                PaymentEvent.tenant_id == pay.tenant_id,
                PaymentEvent.provider_event_id == event_id
            )
        )
        if existing:
            return {"success": True}

    # Store webhook event
    db.add(PaymentEvent(
    tenant_id=pay.tenant_id,
    provider=PaymentProvider.RAZORPAY,
    event_type=event_type or "unknown",
    provider_event_id=event_id,
    provider_order_id=provider_order_id or None,
    provider_payment_id=provider_payment_id or None,
    payload=payload_json,
))


    # Update Payment status
    if status == "authorized":
        pay.status = PaymentStatus.AUTHORIZED
    elif status == "captured":
        pay.status = PaymentStatus.CAPTURED
    elif status == "failed":
        pay.status = PaymentStatus.FAILED
    elif status == "refunded":
        pay.status = PaymentStatus.REFUNDED

    if provider_payment_id:
        pay.provider_payment_id = provider_payment_id

    # Update Appointment payment_status
    appt = db.scalar(select(Appointment).where(Appointment.id == pay.appointment_id))
    if appt:
        if pay.status == PaymentStatus.CAPTURED:
            appt.payment_status = ApptPayStatus.PAID
        elif pay.status == PaymentStatus.FAILED:
            appt.payment_status = ApptPayStatus.FAILED
        elif pay.status == PaymentStatus.REFUNDED:
            appt.payment_status = ApptPayStatus.REFUNDED

    db.commit()
    return {"success": True}



@router.post("/razorpay/verify")
def razorpay_verify(
    body: RazorpayVerifyIn,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_token_payload),
):
    tenant_id = uuid.UUID(payload["tenant_id"])

    pay = db.scalar(select(Payment).where(Payment.id == body.payment_id, Payment.tenant_id == tenant_id))
    if not pay:
        raise HTTPException(status_code=404, detail="Payment not found")

    if pay.provider_order_id != body.razorpay_order_id:
        raise HTTPException(status_code=400, detail="Order ID mismatch")

    ok = verify_razorpay_checkout_signature(
        order_id=body.razorpay_order_id,
        payment_id=body.razorpay_payment_id,
        signature=body.razorpay_signature,
        key_secret=settings.RAZORPAY_KEY_SECRET,
    )
    if not ok:
        raise HTTPException(status_code=400, detail="Invalid signature")

    rp_payment = client.payment.fetch(body.razorpay_payment_id)
    rp_status = rp_payment.get("status", "")

    pay.provider_payment_id = body.razorpay_payment_id
    if rp_status == "captured":
        pay.status = PaymentStatus.CAPTURED
    elif rp_status == "authorized":
        pay.status = PaymentStatus.AUTHORIZED
    elif rp_status == "failed":
        pay.status = PaymentStatus.FAILED

    appt = db.scalar(select(Appointment).where(Appointment.id == pay.appointment_id, Appointment.tenant_id == tenant_id))
    if appt:
        if pay.status == PaymentStatus.CAPTURED:
            appt.payment_status = ApptPayStatus.PAID

            from app.services.receipt_service import generate_receipt_pdf
            from app.workers.tasks import send_booking_email

            pdf_bytes = generate_receipt_pdf(
                receipt_no=str(pay.id),
                customer_name="Customer",
                amount=float(pay.amount),
                currency=pay.currency,
            )

            # You must update your Celery task to support attachments
            send_booking_email.delay(
                to_email="customer@email.com",
                subject="Payment Receipt",
                body="Your payment was successful.",
                attachment=pdf_bytes
            )

            db.add(PaymentEvent(
                tenant_id=tenant_id,
                provider=PaymentProvider.RAZORPAY,
                event_type="checkout.verified",
                provider_event_id=None,
                provider_order_id=body.razorpay_order_id,
                provider_payment_id=body.razorpay_payment_id,
                payload={"razorpay_payment": rp_payment},
            ))

            db.commit()
        elif pay.status == PaymentStatus.FAILED:
            appt.payment_status = ApptPayStatus.FAILED

    return {"success": True, "payment_status": pay.status}


@router.post("/razorpay/refund")
def razorpay_refund(
    body: RefundIn,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_token_payload),
):
    tenant_id = uuid.UUID(payload["tenant_id"])

    # ✅ OPTIONAL BUT RECOMMENDED: admin-only guard
    # if payload.get("role") not in ["ADMIN", "OWNER"]:
    #     raise HTTPException(status_code=403, detail="Not allowed")

    pay = db.scalar(select(Payment).where(Payment.id == body.payment_id, Payment.tenant_id == tenant_id))
    if not pay:
        raise HTTPException(status_code=404, detail="Payment not found")

    if pay.provider != PaymentProvider.RAZORPAY:
        raise HTTPException(status_code=400, detail="Not a Razorpay payment")

    if not pay.provider_payment_id:
        raise HTTPException(status_code=400, detail="Payment not captured / missing provider_payment_id")

    refund_payload = {}
    if body.amount is not None:
        if body.amount <= 0:
            raise HTTPException(status_code=400, detail="Refund amount must be > 0")
        refund_payload["amount"] = int(round(float(body.amount) * 100))  # paisa

    # ✅ Create refund via Razorpay
    refund = client.payment.refund(pay.provider_payment_id, refund_payload)

    # ✅ Update status
    pay.status = PaymentStatus.REFUNDED

    appt = db.scalar(select(Appointment).where(Appointment.id == pay.appointment_id, Appointment.tenant_id == tenant_id))
    if appt:
        appt.payment_status = ApptPayStatus.REFUNDED

    # ✅ Log event
    db.add(PaymentEvent(
        tenant_id=tenant_id,
        provider=PaymentProvider.RAZORPAY,
        event_type="refund.created",
        provider_event_id=refund.get("id"),
        provider_order_id=pay.provider_order_id,
        provider_payment_id=pay.provider_payment_id,
        payload=refund,
    ))

    db.commit()
    return {"success": True, "refund": refund}

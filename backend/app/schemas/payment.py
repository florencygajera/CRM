from pydantic import BaseModel
from uuid import UUID

class CreateOrderIn(BaseModel):
    appointment_id: UUID
    amount: float  # in INR
    currency: str = "INR"

class CreateOrderOut(BaseModel):
    payment_id: UUID
    provider: str
    provider_order_id: str
    amount: float
    currency: str
    key_id: str

class RazorpayVerifyIn(BaseModel):
    payment_id: UUID
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str

# Razorpay-specific order creation schemas
class CreateRazorpayOrderIn(BaseModel):
    appointment_id: UUID
    amount: float  # in INR
    currency: str = "INR"

class CreateRazorpayOrderOut(BaseModel):
    success: bool
    data: dict
class RefundIn(BaseModel):
    payment_id: UUID
    amount: float | None = None  # if None => full refund

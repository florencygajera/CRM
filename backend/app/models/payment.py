import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Numeric, Index, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class PaymentStatus:
    CREATED = "CREATED"
    AUTHORIZED = "AUTHORIZED"
    CAPTURED = "CAPTURED"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class PaymentProvider:
    RAZORPAY = "RAZORPAY"
    STRIPE = "STRIPE"


class Payment(Base):
    __tablename__ = "payments"

    __table_args__ = (
        Index("ix_payments_tenant_appt", "tenant_id", "appointment_id","branch_id"),
    )


    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    branch_id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("branches.id", ondelete="RESTRICT"),
    nullable=False,
    index=True,
)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False
    )

    appointment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True
    )

    provider: Mapped[str] = mapped_column(
        String(50),
        default=PaymentProvider.RAZORPAY
    )

    provider_order_id: Mapped[str] = mapped_column(String(255))
    provider_payment_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    amount: Mapped[float] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(10), default="INR")

    status: Mapped[str] = mapped_column(
        String(50),
        default=PaymentStatus.CREATED
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow
    )

receipt_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
refund_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
refund_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
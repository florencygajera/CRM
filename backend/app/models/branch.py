import uuid
from sqlalchemy import String, DateTime, func,ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class Branch(Base):
    __tablename__ = "branches"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True, nullable=False)
    branch_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True),ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False,index=True,)

    __table_args__ = (Index("ix_payments_tenant_branch", "tenant_id", "branch_id"),)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    address: Mapped[str] = mapped_column(String(500), default="", nullable=False)

    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

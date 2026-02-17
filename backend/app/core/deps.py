import uuid
from typing import Generator
from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.session import SessionLocal
from app.core.security import decode_token
from app.models.branch import Branch
from app.models.user import UserRole


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_token_payload(authorization: str = Header(...)) -> dict:
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    token = authorization.split(" ", 1)[1].strip()
    return decode_token(token)


def require_roles(*roles: str):
    def _checker(payload: dict = Depends(get_token_payload)):
        role = payload.get("role")
        if role not in roles:
            raise HTTPException(status_code=403, detail="Not enough permissions")
        return True
    return _checker


def get_branch_id(
    x_branch_id: str = Header(..., alias="X-Branch-Id"),
    db: Session = Depends(get_db),
    payload: dict = Depends(get_token_payload),
) -> uuid.UUID:
    tenant_id = uuid.UUID(payload["tenant_id"])
    try:
        branch_id = uuid.UUID(x_branch_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid X-Branch-Id")

    branch = db.scalar(select(Branch).where(Branch.id == branch_id, Branch.tenant_id == tenant_id))
    if not branch:
        raise HTTPException(status_code=403, detail="Branch not found for tenant")

    return branch_id

from fastapi import Depends, HTTPException, Header
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.db.session import SessionLocal,get_db
from app.core.security import decode_token
import uuid
from sqlalchemy import select
from app.core.deps import get_token_payload  # if already in same file, remove this line
from app.models.branch import Branch


oauth2 = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_token_payload(token: str = Depends(oauth2)) -> dict:
    try:
        payload = decode_token(token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token")
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Access token required")
    return payload

def require_roles(*allowed: str):
    def _guard(payload: dict = Depends(get_token_payload)) -> dict:
        role = payload.get("role")
        if role not in allowed:
            raise HTTPException(status_code=403, detail="Forbidden")
        return payload
    return _guard

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
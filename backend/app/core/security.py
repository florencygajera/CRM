from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from passlib.context import CryptContext
from app.core.config import settings
import hashlib
import hmac

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGO = "HS256"

def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.
    
    Args:
        password: The plain text password to hash.
        
    Returns:
        The hashed password as a string.
        
    Raises:
        ValueError: If password is empty or None.
    """
    if not password:
        raise ValueError("Password cannot be empty")
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters long")
    return pwd_context.hash(password)

def verify_password(password: str, password_hash: str) -> bool:
    """
    Verify a password against a hash.
    
    Args:
        password: The plain text password to verify.
        password_hash: The hashed password to compare against.
        
    Returns:
        True if the password matches the hash, False otherwise.
    """
    if not password or not password_hash:
        return False
    return pwd_context.verify(password, password_hash)

def create_access_token(*, sub: str, tenant_id: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=settings.JWT_ACCESS_MINUTES)
    payload = {
        "type": "access",
        "sub": sub,
        "tenant_id": tenant_id,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": exp,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=ALGO)

def create_refresh_token(*, sub: str, tenant_id: str, role: str) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(days=settings.JWT_REFRESH_DAYS)
    payload = {
        "type": "refresh",
        "sub": sub,
        "tenant_id": tenant_id,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": exp,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=ALGO)

def decode_token(token: str) -> dict:
    """
    Decode and validate a JWT token.
    
    Args:
        token: The JWT token string to decode.
        
    Returns:
        The decoded token payload as a dictionary.
        
    Raises:
        ValueError: If the token is invalid or expired.
    """
    from jose import ExpiredSignatureError
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[ALGO])
    except ExpiredSignatureError:
        raise ValueError("Token has expired") from None
    except JWTError:
        raise ValueError("Invalid token") from None

def hash_refresh_token(token: str) -> str:
    """
    Hash refresh tokens before storing in DB.
    Using HMAC with JWT_SECRET as pepper prevents rainbow-table attacks.
    """
    if not token:
        raise ValueError("Missing refresh token")
    return hmac.new(
        key=settings.JWT_SECRET.encode("utf-8"),
        msg=token.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()

def verify_refresh_token_hash(token: str, token_hash: str) -> bool:
    if not token or not token_hash:
        return False
    return hmac.compare_digest(hash_refresh_token(token), token_hash)
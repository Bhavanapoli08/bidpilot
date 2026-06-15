from datetime import datetime, timedelta
from jose import JWTError, jwt
import bcrypt
from fastapi import HTTPException, status
from app.config import settings
from typing import Optional, Dict

# bcrypt only hashes the first 72 bytes; longer inputs raise in newer versions.
_BCRYPT_MAX_BYTES = 72


def _to_bytes(password: str) -> bytes:
    """Encode and truncate a password to bcrypt's 72-byte limit."""
    encoded = password.encode("utf-8")
    return encoded[:_BCRYPT_MAX_BYTES]


class JWTHandler:
    @staticmethod
    def hash_password(password: str) -> str:
        hashed = bcrypt.hashpw(_to_bytes(password), bcrypt.gensalt())
        return hashed.decode("utf-8")

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        try:
            return bcrypt.checkpw(
                _to_bytes(plain_password),
                hashed_password.encode("utf-8"),
            )
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        to_encode = data.copy()
        expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    
    @staticmethod
    def create_refresh_token(data: dict) -> str:
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode.update({"exp": expire, "type": "refresh"})
        return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    
    @staticmethod
    def verify_token(token: str) -> Dict:
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            user_id = payload.get("sub")
            org_id = payload.get("org_id")
            if not user_id or not org_id:
                raise JWTError("Missing claims")
            return {"user_id": user_id, "org_id": org_id}
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )

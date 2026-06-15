"""
Authentication API: register, login, refresh, me.
"""
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database import get_db
from app.auth.jwt_handler import JWTHandler
from app.auth.dependencies import get_current_user
from app.models import User, Organization, Subscription, UserRole, SubscriptionTier
from app.schemas import UserRegister, UserLogin, TokenResponse, UserResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["authentication"])
security = HTTPBearer()


@router.post("/register", response_model=TokenResponse)
async def register(data: UserRegister, db: Session = Depends(get_db)):
    """Register a new organization with an owner user."""
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    org = Organization(name=data.organization_name, email=data.email)
    db.add(org)
    db.flush()

    user = User(
        organization_id=org.id,
        email=data.email,
        password_hash=JWTHandler.hash_password(data.password),
        role=UserRole.OWNER,
    )
    db.add(user)

    # Default free subscription
    db.add(Subscription(
        organization_id=org.id,
        tier=SubscriptionTier.FREE,
        price_per_month=0,
    ))

    db.commit()
    db.refresh(user)

    payload = {"sub": str(user.id), "org_id": str(org.id)}
    logger.info(f"Registered new org: {org.name} ({data.email})")
    return TokenResponse(
        access_token=JWTHandler.create_access_token(payload),
        refresh_token=JWTHandler.create_refresh_token(payload),
    )


@router.post("/login", response_model=TokenResponse)
async def login(creds: UserLogin, db: Session = Depends(get_db)):
    """Authenticate a user and issue tokens."""
    user = db.query(User).filter(User.email == creds.email).first()
    if not user or not JWTHandler.verify_password(creds.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    user.last_login = datetime.utcnow()
    db.commit()

    payload = {"sub": str(user.id), "org_id": str(user.organization_id)}
    return TokenResponse(
        access_token=JWTHandler.create_access_token(payload),
        refresh_token=JWTHandler.create_refresh_token(payload),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    """Exchange a refresh token for a new access token."""
    claims = JWTHandler.verify_token(credentials.credentials)
    user = db.query(User).filter(User.id == claims["user_id"]).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    payload = {"sub": str(user.id), "org_id": str(user.organization_id)}
    return TokenResponse(
        access_token=JWTHandler.create_access_token(payload),
        refresh_token=JWTHandler.create_refresh_token(payload),
    )


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    """Return the currently authenticated user."""
    return user

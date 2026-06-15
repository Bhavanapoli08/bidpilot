"""
Reusable FastAPI auth dependencies: current user, current org, role gates.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database import get_db
from app.auth.jwt_handler import JWTHandler
from app.models import User, Organization, UserRole

security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the current user from the bearer token."""
    claims = JWTHandler.verify_token(credentials.credentials)
    user = db.query(User).filter(User.id == claims["user_id"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User account is disabled")
    return user


def get_current_org(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Organization:
    """Resolve the current organization for the authenticated user."""
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    if not org.is_active:
        raise HTTPException(status_code=403, detail="Organization is disabled")
    return org


def require_role(*allowed_roles: str):
    """Dependency factory enforcing that the user holds one of allowed_roles."""
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role: {', '.join(allowed_roles)}",
            )
        return user
    return checker


# Convenience gates
require_owner = require_role(UserRole.OWNER)
require_admin = require_role(UserRole.OWNER, UserRole.ADMIN)

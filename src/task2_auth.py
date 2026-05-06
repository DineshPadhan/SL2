from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
import sys

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parent.parent))

from src.config import settings
from src.database import get_db
from src.models import Institution, Role, User
from src.schemas import (
    AuthResponse,
    LoginRequest,
    MonitoringTokenRequest,
    SignupRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])
bearer_scheme = HTTPBearer(auto_error=False)
monitoring_bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_token(subject: dict, expires_delta: timedelta) -> str:
    issued_at = datetime.now(UTC)
    payload = {
        **subject,
        "iat": int(issued_at.timestamp()),
        "exp": int((issued_at + expires_delta).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired") from exc
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc


def build_auth_response(user: User) -> AuthResponse:
    token = create_token(
        {"user_id": user.id, "role": user.role.value, "token_use": "access"},
        timedelta(hours=settings.access_token_expiry_hours),
    )
    return AuthResponse(access_token=token, user=UserResponse.model_validate(user))


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    payload = decode_token(credentials.credentials)
    if payload.get("token_use") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token")

    user = db.get(User, payload.get("user_id"))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if payload.get("role") != user.role.value:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token role does not match user role")
    return user


def require_roles(*roles: Role) -> Callable:
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Role not permitted")
        return current_user

    return dependency


def get_monitoring_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(monitoring_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    payload = decode_token(credentials.credentials)
    if payload.get("token_use") != "monitoring" or payload.get("scope") != "read:monitoring":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid monitoring token")
    if payload.get("role") != Role.MONITORING_OFFICER.value:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid monitoring role")

    user = db.get(User, payload.get("user_id"))
    if user is None or user.role != Role.MONITORING_OFFICER:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if payload.get("role") != user.role.value:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token role does not match user role")
    return user


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: Session = Depends(get_db)) -> AuthResponse:
    existing_user = db.query(User).filter(User.email == payload.email).first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    if payload.institution_id is not None and db.get(Institution, payload.institution_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Institution not found")

    user = User(
        name=payload.name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        institution_id=payload.institution_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return build_auth_response(user)


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    user = db.query(User).filter(User.email == payload.email).first()
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return build_auth_response(user)


@router.post("/monitoring-token", response_model=TokenResponse)
def issue_monitoring_token(
    payload: MonitoringTokenRequest,
    current_user: User = Depends(require_roles(Role.MONITORING_OFFICER)),
) -> TokenResponse:
    if payload.key != settings.monitoring_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid monitoring API key")

    token = create_token(
        {
            "user_id": current_user.id,
            "role": current_user.role.value,
            "token_use": "monitoring",
            "scope": "read:monitoring",
        },
        timedelta(hours=settings.monitoring_token_expiry_hours),
    )
    return TokenResponse(access_token=token)

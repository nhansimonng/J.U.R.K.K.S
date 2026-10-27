"""Stateless Supabase Auth requests; never share a signed-in client between users."""
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field, SecretStr, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import config
from app.database import get_db
from app.models.user import User

router = APIRouter(tags=["Authentication"])
bearer = HTTPBearer(auto_error=False)


class LoginRequest(BaseModel):
    email: EmailStr
    password: SecretStr = Field(min_length=1, max_length=1024)


class RegisterRequest(LoginRequest):
    password: SecretStr = Field(min_length=8, max_length=1024)
    username: str = Field(min_length=1, max_length=50)

    @field_validator("username")
    @classmethod
    def clean_username(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Username cannot be blank")
        return value


class UserResponse(BaseModel):
    id: UUID
    email: EmailStr
    username: str


class ProfileResponse(UserResponse):
    created_at: datetime


class SessionResponse(BaseModel):
    user: UserResponse
    access_token: str
    expires_at: datetime


class ConfirmationResponse(BaseModel):
    confirmation_required: Literal[True] = True
    message: str = "Check your email to confirm your account, then log in."


def auth_request(method, path, *, token=None, payload=None, params=None):
    if not config.SUPABASE_URL or not config.SUPABASE_ANON_KEY:
        raise HTTPException(503, "Authentication is not configured")
    headers = {"apikey": config.SUPABASE_ANON_KEY}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        with httpx.Client(timeout=10) as client:
            result = client.request(method, f"{config.SUPABASE_URL.rstrip('/')}/auth/v1/{path}",
                                    headers=headers, json=payload, params=params)
    except httpx.RequestError:
        raise HTTPException(503, "Authentication service unavailable") from None
    if result.status_code == 429:
        raise HTTPException(429, "Too many requests. Try again later.")
    if result.status_code >= 500:
        raise HTTPException(503, "Authentication service unavailable")
    if result.status_code == 204:
        return {}
    try:
        data = result.json()
    except ValueError:
        raise HTTPException(502, "Invalid authentication service response") from None
    if not isinstance(data, dict):
        raise HTTPException(502, "Invalid authentication service response")
    if not result.is_success:
        code = data.get("error_code") or data.get("code")
        if code == "email_not_confirmed":
            raise HTTPException(403, "Confirm your email before logging in")
        if path == "token":
            raise HTTPException(401, "Invalid email or password")
        if path in ("user", "logout"):
            raise HTTPException(401, "Invalid or expired access token")
        if code in ("user_already_exists", "email_exists"):
            raise HTTPException(400, "Email already in use")
        if code == "weak_password":
            raise HTTPException(400, "Password too weak")
        raise HTTPException(400, "Unable to register account")
    return data


def get_access_token(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    if credentials is None:
        raise HTTPException(401, "Authentication required")
    return credentials.credentials


def get_current_user(token: str = Depends(get_access_token)):
    # Supabase verifies the token; never trust a locally decoded, unsigned JWT.
    return auth_request("GET", "user", token=token)


def get_profile(identity, db):
    user_id = UUID(identity["id"])
    profile = db.get(User, user_id)
    if profile is None:
        username = (identity.get("user_metadata") or {}).get("username")
        if not isinstance(username, str) or not username.strip():
            raise HTTPException(409, "Account is missing a username")
        profile = User(id=user_id, username=username.strip()[:50])
        db.add(profile)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            profile = db.get(User, user_id)
            if profile is None:
                raise
        db.refresh(profile)
    return profile


def session_response(data, db):
    identity = data["user"]
    profile = get_profile(identity, db)
    expires_at = (datetime.fromtimestamp(data["expires_at"], timezone.utc)
                  if data.get("expires_at") else
                  datetime.now(timezone.utc) + timedelta(seconds=data["expires_in"]))
    return SessionResponse(user=UserResponse(id=profile.id, email=identity["email"],
                                            username=profile.username),
                           access_token=data["access_token"], expires_at=expires_at)


@router.post("/api/auth/register", status_code=201,
             response_model=SessionResponse | ConfirmationResponse)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    data = auth_request("POST", "signup", payload={"email": str(body.email),
                        "password": body.password.get_secret_value(),
                        "data": {"username": body.username}})
    if not data.get("access_token"):
        # Also preserves Supabase's protection against account enumeration.
        return ConfirmationResponse()
    return session_response(data, db)


@router.post("/api/auth/login", response_model=SessionResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    data = auth_request("POST", "token", params={"grant_type": "password"},
                        payload={"email": str(body.email),
                                 "password": body.password.get_secret_value()})
    return session_response(data, db)


@router.post("/api/auth/logout", status_code=204)
def logout(token: str = Depends(get_access_token)):
    auth_request("POST", "logout", token=token, params={"scope": "local"})
    return Response(status_code=204)


@router.get("/api/users/me", response_model=ProfileResponse)
def me(identity: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = get_profile(identity, db)
    return ProfileResponse(id=profile.id, email=identity["email"],
                           username=profile.username, created_at=profile.created_at)

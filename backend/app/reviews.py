"""Gym reviews, community equipment reports, and validated photo uploads."""
from datetime import timezone
from io import BytesIO
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4
import re
import warnings

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import config, integrations
from app.api_schemas import EquipmentList, EquipmentItem, ReviewsList, ReviewCreated, ReportCreated, PhotoCreated
from app.auth import get_access_token, get_current_user, get_profile
from app.community import normalize
from app.database import get_db
from app.models import Equipment, Gym, GymReview, ModerationReport, User

router = APIRouter(tags=["Reviews and Equipment"])
PHOTO_LIMIT = 500 * 1024


def require_gym(db, gym_id, lock=False):
    query = select(Gym).where(Gym.id == gym_id)
    if lock:
        query = query.with_for_update()
    gym = db.scalar(query)
    if gym is None:
        raise HTTPException(404, "Gym not found")
    return gym


def equipment_item(item):
    return {"id": item.id, "name": item.name, "availability": item.availability,
            "condition": item.condition}


class EquipmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=200)
    availability: Literal["available", "unavailable", "unconfirmed"]
    condition: Literal["good", "fair", "worn", "broken"]

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        if not normalize(value):
            raise ValueError("Equipment name is required")
        return normalize(value)


@router.get("/api/gyms/{gym_id}/equipment", response_model=EquipmentList)
def get_equipment(gym_id: UUID, identity: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    require_gym(db, gym_id)
    return {"equipment": [equipment_item(e) for e in db.scalars(select(Equipment).where(
        Equipment.gym_id == gym_id).order_by(Equipment.name, Equipment.id))]}


@router.post("/api/gyms/{gym_id}/equipment", status_code=201, response_model=EquipmentItem)
def set_equipment(gym_id: UUID, body: EquipmentRequest,
                  identity: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    # Gym lock prevents duplicate name inserts from concurrent requests.
    require_gym(db, gym_id, lock=True)
    item = db.scalar(select(Equipment).where(Equipment.gym_id == gym_id,
                                             func.lower(Equipment.name) == body.name))
    if item is None:
        item = Equipment(gym_id=gym_id, **body.model_dump())
        db.add(item)
    else:
        item.availability, item.condition = body.availability, body.condition
    db.commit()
    db.refresh(item)
    return equipment_item(item)


def photo_url(path):
    if not path or not config.SUPABASE_URL:
        return None
    # Only server-generated paths, never a URL provided by a user.
    if not re.fullmatch(r"reviews/[0-9a-f-]{36}/[0-9a-f-]{36}\.(jpg|png)", path):
        return None
    return f"{config.SUPABASE_URL.rstrip('/')}/storage/v1/object/public/{config.REVIEW_PHOTO_BUCKET}/{path}"


def review_item(review, username):
    created = review.created_at
    if created and created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return {"id": review.id, "user_id": review.user_id, "username": username,
            "gym_id": review.gym_id, "rating": review.rating, "review_text": review.review_text,
            "busy_hour_info": review.busy_hour_info, "photo_url": photo_url(review.photo_path),
            "created_at": created}


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rating: int = Field(strict=True, ge=1, le=5)
    review_text: str | None = Field(None, max_length=1000)
    busy_hour_info: str | None = Field(None, max_length=100)
    photo_path: str | None = Field(None, max_length=200)


def storage_headers(token):
    if not config.SUPABASE_URL or not config.SUPABASE_ANON_KEY:
        raise HTTPException(503, "Photo storage is not configured")
    return {"apikey": config.SUPABASE_ANON_KEY, "Authorization": f"Bearer {token}"}


@router.get("/api/gyms/{gym_id}/reviews", response_model=ReviewsList)
def list_reviews(gym_id: UUID, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
                 identity: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    require_gym(db, gym_id)
    total = db.scalar(select(func.count(GymReview.id)).where(GymReview.gym_id == gym_id))
    rows = db.execute(select(GymReview, User.username).join(User, User.id == GymReview.user_id)
                      .where(GymReview.gym_id == gym_id).order_by(GymReview.created_at.desc(), GymReview.id.desc())
                      .limit(limit).offset(offset)).all()
    return {"reviews": [review_item(*row) for row in rows], "total": total}


@router.post("/api/gyms/{gym_id}/reviews", status_code=201, response_model=ReviewCreated)
def create_review(gym_id: UUID, body: ReviewRequest, identity: dict = Depends(get_current_user),
                  token: str = Depends(get_access_token), db: Session = Depends(get_db)):
    require_gym(db, gym_id)
    if body.photo_path:
        pattern = rf"reviews/{re.escape(identity['id'])}/[0-9a-f-]{{36}}\.(jpg|png)"
        if not re.fullmatch(pattern, body.photo_path):
            raise HTTPException(400, "Attach a photo uploaded by your account")
        integrations.request("GET", f"{config.SUPABASE_URL}/storage/v1/object/info/"
                             f"{config.REVIEW_PHOTO_BUCKET}/{body.photo_path}", "Photo storage",
                             headers=storage_headers(token))
    profile = get_profile(identity, db)
    review = GymReview(user_id=profile.id, gym_id=gym_id, **body.model_dump())
    db.add(review)
    db.commit()
    db.refresh(review)
    average = db.scalar(select(func.avg(GymReview.rating)).where(GymReview.gym_id == gym_id))
    return {**review_item(review, profile.username), "average_rating": round(float(average), 1)}


class ReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value):
        if not value.strip():
            raise ValueError("A reason is required")
        return value.strip()


@router.post("/api/reviews/{review_id}/reports", status_code=201, response_model=ReportCreated)
def report_review(review_id: UUID, body: ReportRequest,
                  identity: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    if db.get(GymReview, review_id) is None:
        raise HTTPException(404, "Review not found")
    profile = get_profile(identity, db)
    report = ModerationReport(user_id=profile.id, review_id=review_id, reason=body.reason, status="pending")
    db.add(report)
    db.commit()
    db.refresh(report)
    return {"id": report.id, "review_id": report.review_id, "status": report.status}


@router.post("/api/reviews/photo", status_code=201, response_model=PhotoCreated)
def upload_photo(file: UploadFile = File(...), identity: dict = Depends(get_current_user),
                 token: str = Depends(get_access_token)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in (".jpg", ".png"):
        raise HTTPException(400, "Only .jpg and .png files are allowed")
    content = file.file.read(PHOTO_LIMIT + 1)
    if len(content) > PHOTO_LIMIT:
        raise HTTPException(400, "Photo is too large")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as picture:
                if picture.format != ("JPEG" if suffix == ".jpg" else "PNG"):
                    raise ValueError()
                if picture.width * picture.height > 16_000_000:
                    raise ValueError()
                picture.verify()
            # Re-encode to remove metadata and trailing payloads.
            with Image.open(BytesIO(content)) as picture:
                output = BytesIO()
                picture.convert("RGB" if suffix == ".jpg" else "RGBA").save(
                    output, format="JPEG" if suffix == ".jpg" else "PNG")
                content = output.getvalue()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(400, "Invalid or oversized image") from None
    if len(content) > PHOTO_LIMIT:
        raise HTTPException(400, "Photo is too large")
    path = f"reviews/{identity['id']}/{uuid4()}{suffix}"
    headers = storage_headers(token)
    integrations.request("POST", f"{config.SUPABASE_URL}/storage/v1/object/{config.REVIEW_PHOTO_BUCKET}/{path}",
                         "Photo storage", headers={**headers, "Content-Type": "image/jpeg" if suffix == ".jpg" else "image/png",
                                                   "x-upsert": "false"}, content=content)
    return {"photo_path": path}

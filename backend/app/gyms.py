from uuid import UUID
from math import asin, cos, radians, sin, sqrt

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Gym, GymReview, Equipment
from app import places

router = APIRouter(prefix="/api/gyms", tags=["gyms"])


class GymSummary(BaseModel):
    id: UUID
    name: str
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    average_rating: float | None = None
    review_count: int = 0
    distance_km: float | None = None


class GymListResponse(BaseModel):
    gyms: list[GymSummary]


class GymDetail(GymSummary):
    equipment: list = []
    busy_hours: list = []


def gym_with_ratings():
    """Base query: each gym plus its average rating and review count."""
    return (
        select(
            Gym,
            func.round(func.avg(GymReview.rating), 1),
            func.count(GymReview.id),
        )
        .outerjoin(GymReview, GymReview.gym_id == Gym.id)
        .group_by(Gym.id)
    )


def to_summary(gym, avg_rating, review_count) -> dict:
    return {
        "id": gym.id,
        "name": gym.name,
        "address": gym.address,
        "latitude": float(gym.latitude) if gym.latitude is not None else None,
        "longitude": float(gym.longitude) if gym.longitude is not None else None,
        "average_rating": float(avg_rating) if avg_rating is not None else None,
        "review_count": review_count,
    }


@router.get("", response_model=GymListResponse, response_model_exclude_unset=True)
def search_gyms(
    query: str = Query(default="", max_length=200),
    lat: float | None = Query(None, ge=-90, le=90, allow_inf_nan=False),
    lng: float | None = Query(None, ge=-180, le=180, allow_inf_nan=False),
    radius_km: float = Query(10, gt=0, le=50, allow_inf_nan=False),
    equipment: str = Query("", max_length=1000),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    text = query.strip()
    if (lat is None) != (lng is None):
        raise HTTPException(400, "Provide both latitude and longitude")
    names = {" ".join(name.lower().split()) for name in equipment.split(",") if name.strip()}
    if not text and lat is None and not names:
        raise HTTPException(status_code=400, detail="Enter a gym name or location")
    imported_ids = places.import_places(db, text, lat, lng, radius_km) if text or lat is not None else []

    # Escape % and _ so users can't use them as wildcards
    safe = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    pattern = f"%{safe}%"

    statement = gym_with_ratings()
    if text:
        statement = statement.where(
            or_(
                Gym.name.ilike(pattern, escape="\\"),
                Gym.address.ilike(pattern, escape="\\"),
                Gym.id.in_(imported_ids),
            )
        )
    for name in names:
        statement = statement.where(select(Equipment.id).where(
            Equipment.gym_id == Gym.id, func.lower(Equipment.name) == name,
            Equipment.availability == "available",
            or_(Equipment.condition.is_(None), Equipment.condition != "broken")).exists())
    if lat is not None:
        # Bounding latitude reduces rows before exact great-circle distance filtering.
        statement = statement.where(Gym.latitude.between(lat - radius_km / 111, lat + radius_km / 111))
    rows = db.execute(statement.order_by(Gym.name, Gym.id)).all()
    results = []
    for row in rows:
        item = to_summary(*row)
        if lat is not None:
            if item["latitude"] is None or item["longitude"] is None:
                continue
            a = sin(radians(item["latitude"] - lat) / 2) ** 2 + cos(radians(lat)) * cos(
                radians(item["latitude"])) * sin(radians(item["longitude"] - lng) / 2) ** 2
            distance = 6371 * 2 * asin(sqrt(min(1, max(0, a))))
            if distance > radius_km:
                continue
            item["distance_km"] = round(distance, 2)
        results.append(item)
    if lat is not None:
        results.sort(key=lambda item: (item["distance_km"], item["name"]))
    return {"gyms": results[:50]}


@router.get("/{gym_id}", response_model=GymDetail, response_model_exclude_unset=True)
def get_gym(
    gym_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    row = db.execute(gym_with_ratings().where(Gym.id == gym_id)).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Gym not found")
    items = db.scalars(select(Equipment).where(Equipment.gym_id == gym_id).order_by(Equipment.name)).all()
    hours = db.execute(select(GymReview.busy_hour_info, func.count(GymReview.id)).where(
        GymReview.gym_id == gym_id, GymReview.busy_hour_info.is_not(None),
        func.trim(GymReview.busy_hour_info) != "").group_by(GymReview.busy_hour_info)
        .order_by(func.count(GymReview.id).desc(), GymReview.busy_hour_info)).all()
    return {**to_summary(*row), "equipment": [{"id": e.id, "name": e.name,
            "availability": e.availability, "condition": e.condition} for e in items],
            "busy_hours": [{"label": label, "mentions": count} for label, count in hours]}

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Gym, GymReview

router = APIRouter(prefix="/api/gyms", tags=["gyms"])


class GymSummary(BaseModel):
    id: UUID
    name: str
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    average_rating: float | None = None
    review_count: int = 0


class GymListResponse(BaseModel):
    gyms: list[GymSummary]


class GymDetail(GymSummary):
    # Equipment is skipped for now; empty lists keep the contract shape
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


@router.get("", response_model=GymListResponse)
def search_gyms(
    query: str = Query(default=""),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    text = query.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Enter a gym name or location")

    # Escape % and _ so users can't use them as wildcards
    safe = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    pattern = f"%{safe}%"

    rows = db.execute(
        gym_with_ratings()
        .where(
            or_(
                Gym.name.ilike(pattern, escape="\\"),
                Gym.address.ilike(pattern, escape="\\"),
            )
        )
        .order_by(Gym.name)
        .limit(50)
    ).all()

    return {"gyms": [to_summary(*row) for row in rows]}


@router.get("/{gym_id}", response_model=GymDetail)
def get_gym(
    gym_id: UUID,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    row = db.execute(gym_with_ratings().where(Gym.id == gym_id)).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Gym not found")
    return to_summary(*row)
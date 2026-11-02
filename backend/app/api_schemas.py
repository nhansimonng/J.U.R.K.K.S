"""Response shapes for the frontend and generated OpenAPI documentation."""
from datetime import date, datetime
from uuid import UUID
from pydantic import BaseModel
from app.workout_plans import PlanResponse, ExerciseResponse


class PublicPlan(PlanResponse):
    author_username: str | None


class PublicPlans(BaseModel):
    plans: list[PublicPlan]


class Bookmark(BaseModel):
    id: UUID
    plan_id: UUID


class EquipmentItem(BaseModel):
    id: UUID
    name: str
    availability: str | None
    condition: str | None


class EquipmentList(BaseModel):
    equipment: list[EquipmentItem]


class ReviewItem(BaseModel):
    id: UUID
    user_id: UUID
    username: str
    gym_id: UUID
    rating: int
    review_text: str | None
    busy_hour_info: str | None
    photo_url: str | None
    created_at: datetime


class ReviewCreated(ReviewItem):
    average_rating: float


class ReviewsList(BaseModel):
    reviews: list[ReviewItem]
    total: int


class ReportCreated(BaseModel):
    id: UUID
    review_id: UUID
    status: str


class PhotoCreated(BaseModel):
    photo_path: str


class Alternative(BaseModel):
    name: str
    muscle_group: str | None
    required_equipment: list[str]


class CompatibilityItem(BaseModel):
    exercise_id: UUID
    exercise_name: str
    status: str
    missing_equipment: list[str]
    alternatives: list[Alternative]


class CompatibilityResponse(BaseModel):
    gym_id: UUID
    plan_id: UUID
    compatible: bool
    results: list[CompatibilityItem]


class FoodItem(BaseModel):
    food_id: str
    name: str
    reference_portion: float
    reference_unit: str
    reference_calories: float


class FoodResults(BaseModel):
    foods: list[FoodItem]
    cached_only: bool


class CalorieEntry(BaseModel):
    id: UUID
    food_name: str
    portion: float
    portion_unit: str | None
    calories: float


class CalorieCreated(CalorieEntry):
    log_date: date
    daily_total: float


class CalorieDay(BaseModel):
    date: date
    entries: list[CalorieEntry]
    daily_total: float

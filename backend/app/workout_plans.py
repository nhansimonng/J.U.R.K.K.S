"""Personal workout plans and their exercises, following API contract section 8."""
from collections import defaultdict
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth import get_current_user, get_profile
from app.database import get_db
from app.models.exercise import Exercise
from app.models.plan import Plan

router = APIRouter(tags=["Workout Plans"])
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
PositiveCount = Annotated[int, Field(strict=True, gt=0, le=2147483647)]


class ExerciseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name
    muscle_group: Name | None = None
    sets: PositiveCount
    reps: PositiveCount
    required_equipment: list[Name] = Field(default_factory=list, max_length=50)


class PlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name
    fitness_goal: Name | None = None
    is_public: bool = Field(default=False, strict=True)
    exercises: list[ExerciseRequest] = Field(min_length=1, max_length=100)


class ExerciseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    muscle_group: str | None
    sets: int | None
    reps: int | None
    required_equipment: list[str] | None


class PlanResponse(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    fitness_goal: str | None
    is_public: bool
    exercises: list[ExerciseResponse]


class PlanListResponse(BaseModel):
    plans: list[PlanResponse]


def plan_response(plan, exercises):
    return PlanResponse(id=plan.id, user_id=plan.user_id, name=plan.name,
                        fitness_goal=plan.fitness_goal, is_public=bool(plan.is_public),
                        exercises=exercises)


def find_plan(db, plan_id, user_id, *, owner_only=False, lock=False):
    query = select(Plan).where(Plan.id == plan_id)
    if lock:
        query = query.with_for_update()
    plan = db.scalar(query)
    if plan is None:
        raise HTTPException(404, "Workout plan not found")
    if plan.user_id != UUID(user_id) and (owner_only or not plan.is_public):
        raise HTTPException(403, "You do not have access to this workout plan")
    return plan


def add_exercises(db, plan_id, exercises):
    rows = [Exercise(plan_id=plan_id, **exercise.model_dump()) for exercise in exercises]
    db.add_all(rows)
    db.flush()
    return rows


@router.post("/api/workout-plans", status_code=201, response_model=PlanResponse)
def create_plan(body: PlanRequest, identity: dict = Depends(get_current_user),
                db: Session = Depends(get_db)):
    profile = get_profile(identity, db)
    try:
        plan = Plan(user_id=profile.id, **body.model_dump(exclude={"exercises"}))
        db.add(plan)
        db.flush()
        exercises = add_exercises(db, plan.id, body.exercises)
        result = plan_response(plan, exercises)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return result


@router.get("/api/users/me/workout-plans", response_model=PlanListResponse)
def my_plans(identity: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    plans = db.scalars(select(Plan).where(Plan.user_id == UUID(identity["id"]))
                       .order_by(Plan.name, Plan.id)).all()
    grouped = defaultdict(list)
    if plans:
        exercises = db.scalars(select(Exercise).where(Exercise.plan_id.in_([p.id for p in plans]))
                              .order_by(Exercise.id)).all()
        for exercise in exercises:
            grouped[exercise.plan_id].append(exercise)
    return {"plans": [plan_response(plan, grouped[plan.id]) for plan in plans]}


@router.get("/api/workout-plans/{plan_id}", response_model=PlanResponse)
def get_plan(plan_id: UUID, identity: dict = Depends(get_current_user),
             db: Session = Depends(get_db)):
    plan = find_plan(db, plan_id, identity["id"])
    exercises = db.scalars(select(Exercise).where(Exercise.plan_id == plan.id)
                          .order_by(Exercise.id)).all()
    return plan_response(plan, exercises)


@router.put("/api/workout-plans/{plan_id}", response_model=PlanResponse)
def update_plan(plan_id: UUID, body: PlanRequest, identity: dict = Depends(get_current_user),
                db: Session = Depends(get_db)):
    try:
        plan = find_plan(db, plan_id, identity["id"], owner_only=True, lock=True)
        for field, value in body.model_dump(exclude={"exercises"}).items():
            setattr(plan, field, value)
        # PUT replaces the full exercise list; exercise IDs are regenerated.
        db.execute(delete(Exercise).where(Exercise.plan_id == plan.id))
        exercises = add_exercises(db, plan.id, body.exercises)
        result = plan_response(plan, exercises)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return result


@router.delete("/api/workout-plans/{plan_id}", status_code=204)
def delete_plan(plan_id: UUID, identity: dict = Depends(get_current_user),
                db: Session = Depends(get_db)):
    try:
        plan = find_plan(db, plan_id, identity["id"], owner_only=True, lock=True)
        # Existing ON DELETE CASCADE foreign keys remove exercises and saved plans.
        db.delete(plan)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return Response(status_code=204)

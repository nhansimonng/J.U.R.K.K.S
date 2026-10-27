"""Save, list, and delete the authenticated user's workout entries."""
from datetime import date
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user, get_profile
from app.database import get_db
from app.models.workout_log import WorkoutLog

router = APIRouter(tags=["Workout Logs"])


class WorkoutLogRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exercise_name: str = Field(min_length=1, max_length=200)
    sets: int = Field(strict=True, gt=0, le=2147483647)
    reps: int = Field(strict=True, gt=0, le=2147483647)
    weight: float = Field(ge=0, allow_inf_nan=False, strict=True)
    weight_unit: Literal["lb", "kg"]
    log_date: date

    @field_validator("exercise_name")
    @classmethod
    def clean_name(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Exercise name is required")
        return value


class WorkoutLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    exercise_name: str
    sets: int | None
    reps: int | None
    weight: float | None
    weight_unit: str | None
    log_date: date


class WorkoutHistoryResponse(BaseModel):
    logs: list[WorkoutLogResponse]


@router.post("/api/workout-logs", status_code=201, response_model=WorkoutLogResponse)
def create_log(body: WorkoutLogRequest, identity: dict = Depends(get_current_user),
               db: Session = Depends(get_db)):
    profile = get_profile(identity, db)
    log = WorkoutLog(user_id=profile.id, **body.model_dump())
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


@router.get("/api/users/me/workout-logs", response_model=WorkoutHistoryResponse)
def list_logs(from_date: date | None = Query(None, alias="from"),
              to_date: date | None = Query(None, alias="to"),
              identity: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    if from_date and to_date and from_date > to_date:
        raise HTTPException(400, "From date must not be after to date")
    query = select(WorkoutLog).where(WorkoutLog.user_id == UUID(identity["id"]))
    if from_date:
        query = query.where(WorkoutLog.log_date >= from_date)
    if to_date:
        query = query.where(WorkoutLog.log_date <= to_date)
    logs = db.scalars(query.order_by(WorkoutLog.log_date.desc(), WorkoutLog.id.desc())).all()
    return {"logs": logs}


@router.delete("/api/workout-logs/{log_id}", status_code=204)
def delete_log(log_id: UUID, identity: dict = Depends(get_current_user),
               db: Session = Depends(get_db)):
    log = db.scalar(select(WorkoutLog).where(WorkoutLog.id == log_id,
                                           WorkoutLog.user_id == UUID(identity["id"])))
    if log is None:
        raise HTTPException(404, "Workout log not found")
    db.delete(log)
    db.commit()
    return Response(status_code=204)

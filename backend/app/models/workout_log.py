import uuid

from sqlalchemy import Column, Date, ForeignKey, Integer, Numeric, Text, func
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class WorkoutLog(Base):
    __tablename__ = "workout_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    exercise_name = Column(Text, nullable=False)
    sets = Column(Integer)
    reps = Column(Integer)
    weight = Column(Numeric)
    weight_unit = Column(Text)
    log_date = Column(Date, nullable=False, server_default=func.current_date())
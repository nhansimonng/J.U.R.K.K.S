import uuid

from sqlalchemy import Column, Date, ForeignKey, Numeric, Text, func
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class CalorieLog(Base):
    __tablename__ = "calorie_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    food_name = Column(Text, nullable=False)
    portion = Column(Numeric)
    portion_unit = Column(Text)
    calories = Column(Numeric)
    log_date = Column(Date, nullable=False, server_default=func.current_date())
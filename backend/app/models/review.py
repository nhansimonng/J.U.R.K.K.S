import uuid

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class GymReview(Base):
    __tablename__ = "gym_reviews"
    __table_args__ = (CheckConstraint("rating between 1 and 5", name="rating_range"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    gym_id = Column(UUID(as_uuid=True), ForeignKey("gyms.id", ondelete="CASCADE"), nullable=False)
    rating = Column(Integer, nullable=False)
    review_text = Column(String(1000))
    photo_path = Column(Text)
    busy_hour_info = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
import uuid

from sqlalchemy import ARRAY, Column, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class Exercise(Base):
    __tablename__ = "exercises"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id = Column(UUID(as_uuid=True), ForeignKey("plans.id", ondelete="CASCADE"), nullable=False)
    name = Column(Text, nullable=False)
    muscle_group = Column(Text)
    sets = Column(Integer)
    reps = Column(Integer)
    required_equipment = Column(ARRAY(Text))
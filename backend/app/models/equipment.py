import uuid

from sqlalchemy import Column, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class Equipment(Base):
    __tablename__ = "equipment"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    gym_id = Column(UUID(as_uuid=True), ForeignKey("gyms.id", ondelete="CASCADE"), nullable=False)
    name = Column(Text, nullable=False)
    availability = Column(Text)
    condition = Column(Text)
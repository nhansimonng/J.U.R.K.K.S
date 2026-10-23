import uuid

from sqlalchemy import Column, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class Gym(Base):
    __tablename__ = "gyms"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False)
    address = Column(Text)
    latitude = Column(Numeric)
    longitude = Column(Numeric)
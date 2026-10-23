from sqlalchemy import Column, DateTime, Text, func
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class User(Base):
    __tablename__ = "users"

    # Same id as the matching Supabase Auth user, so no default here
    id = Column(UUID(as_uuid=True), primary_key=True)
    username = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
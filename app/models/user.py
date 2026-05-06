from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    workshop_id = Column(
        Integer,
        ForeignKey("workshops.id"),
        nullable=False,
        index=True
    )

    full_name = Column(String(150), nullable=False)

    email = Column(String(150), unique=True, nullable=False)

    password_hash = Column(String(255), nullable=False)

    role = Column(String(30), nullable=False, default="admin")

    status = Column(String(30), nullable=False, default="active")

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    workshop = relationship("Workshop")
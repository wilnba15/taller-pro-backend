from sqlalchemy import Column, DateTime, Integer, String, func
from sqlalchemy.orm import relationship

from app.database import Base


class SwmUser(Base):
    __tablename__ = "swm_users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(150), nullable=False)
    email = Column(String(150), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    phone = Column(String(30), nullable=True)
    city = Column(String(80), nullable=True)
    country = Column(String(80), nullable=True, default="Ecuador")
    status = Column(String(30), nullable=False, default="active")
    reset_token_hash = Column(String(64), nullable=True, index=True)
    reset_token_expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    vehicles = relationship(
        "SwmVehicle",
        back_populates="user",
        cascade="all, delete-orphan",
    )

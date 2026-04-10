from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class Workshop(Base):
    __tablename__ = "workshops"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False, unique=True)
    owner_name = Column(String(150), nullable=True)
    phone = Column(String(20), nullable=True)
    email = Column(String(120), nullable=True)
    address = Column(String(200), nullable=True)
    status = Column(String(30), nullable=False, default="activo")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    clients = relationship("Client", back_populates="workshop", cascade="all, delete")
    vehicles = relationship("Vehicle", back_populates="workshop", cascade="all, delete")
    work_orders = relationship("WorkOrder", back_populates="workshop", cascade="all, delete")
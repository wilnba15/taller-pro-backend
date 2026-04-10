from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    workshop_id = Column(Integer, ForeignKey("workshops.id"), nullable=False, index=True)

    full_name = Column(String(150), nullable=False)
    identification = Column(String(20), nullable=False)
    phone = Column(String(20), nullable=False)
    email = Column(String(120), nullable=True)
    address = Column(String(200), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    workshop = relationship("Workshop", back_populates="clients")
    vehicles = relationship("Vehicle", back_populates="client", cascade="all, delete")
    work_orders = relationship("WorkOrder", back_populates="client", cascade="all, delete")
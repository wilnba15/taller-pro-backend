from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)
    workshop_id = Column(Integer, ForeignKey("workshops.id"), nullable=False)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)

    plate = Column(String(20), nullable=False)
    brand = Column(String(50), nullable=True)
    model = Column(String(50), nullable=True)
    year = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    workshop = relationship("Workshop", back_populates="vehicles")
    client = relationship("Client", back_populates="vehicles")
    work_orders = relationship("WorkOrder", back_populates="vehicle", cascade="all, delete")
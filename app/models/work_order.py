from sqlalchemy import Column, Integer, String, Text, Date, Numeric, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class WorkOrder(Base):
    __tablename__ = "work_orders"

    id = Column(Integer, primary_key=True, index=True)
    workshop_id = Column(Integer, ForeignKey("workshops.id"), nullable=False, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)

    entry_date = Column(Date, nullable=False)
    estimated_delivery_date = Column(Date, nullable=True)
    status = Column(String(30), nullable=False, default="pendiente")

    issue_description = Column(Text, nullable=False)
    diagnosis = Column(Text, nullable=True)
    work_performed = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    labor_cost = Column(Numeric(10, 2), nullable=False, default=0)
    parts_cost = Column(Numeric(10, 2), nullable=False, default=0)
    total = Column(Numeric(10, 2), nullable=False, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    workshop = relationship("Workshop", back_populates="work_orders")
    client = relationship("Client", back_populates="work_orders")
    vehicle = relationship("Vehicle", back_populates="work_orders")
    photos = relationship("WorkOrderPhoto", back_populates="work_order", cascade="all, delete-orphan")
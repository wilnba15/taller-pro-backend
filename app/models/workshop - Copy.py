from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Workshop(Base):
    __tablename__ = "workshops"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False, unique=True)
    business_name = Column(String(180), nullable=True)
    ruc = Column(String(20), nullable=True)
    owner_name = Column(String(150), nullable=True)
    phone = Column(String(20), nullable=True)
    email = Column(String(120), nullable=True)
    address = Column(String(200), nullable=True)
    logo_url = Column(String(500), nullable=True)
    footer_text = Column(Text, nullable=True)
    setup_completed = Column(Boolean, nullable=False, default=False, server_default="false")
    status = Column(String(30), nullable=False, default="activo")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    clients = relationship("Client", back_populates="workshop", cascade="all, delete")
    vehicles = relationship("Vehicle", back_populates="workshop", cascade="all, delete")
    work_orders = relationship("WorkOrder", back_populates="workshop", cascade="all, delete")

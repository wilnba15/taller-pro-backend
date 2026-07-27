from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class InventoryProduct(Base):
    __tablename__ = "inventory_products"

    id = Column(Integer, primary_key=True, index=True)
    workshop_id = Column(Integer, ForeignKey("workshops.id", ondelete="CASCADE"), nullable=False, index=True)
    code = Column(String(50), nullable=True)
    name = Column(String(180), nullable=False)
    category = Column(String(100), nullable=True)
    brand = Column(String(100), nullable=True)
    stock = Column(Numeric(12, 2), nullable=False, default=0, server_default="0")
    minimum_stock = Column(Numeric(12, 2), nullable=False, default=0, server_default="0")
    cost = Column(Numeric(12, 2), nullable=False, default=0, server_default="0")
    sale_price = Column(Numeric(12, 2), nullable=False, default=0, server_default="0")
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    workshop = relationship("Workshop", back_populates="inventory_products")

from sqlalchemy import Column, Integer, String, Text, Numeric, DateTime, ForeignKey, func
from app.database import Base


class WorkOrderItem(Base):
    __tablename__ = "work_order_items"

    id = Column(Integer, primary_key=True, index=True)
    work_order_id = Column(Integer, ForeignKey("work_orders.id", ondelete="CASCADE"), nullable=False)
    item_type = Column(String(20), nullable=False)  # 'repuesto' o 'mano_obra'
    description = Column(Text, nullable=False)
    quantity = Column(Numeric(10, 2), nullable=False, default=1)
    unit_price = Column(Numeric(10, 2), nullable=False, default=0)
    subtotal = Column(Numeric(10, 2), nullable=False, default=0)
    created_at = Column(DateTime, server_default=func.now())
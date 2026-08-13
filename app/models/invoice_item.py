from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    invoice_id = Column(
        Integer,
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    item_type = Column(
        String(20),
        nullable=False,
    )

    description = Column(
        Text,
        nullable=False,
    )

    quantity = Column(
        Numeric(12, 2),
        nullable=False,
        default=1,
    )

    unit_price = Column(
        Numeric(12, 2),
        nullable=False,
        default=0,
    )

    discount = Column(
        Numeric(12, 2),
        nullable=False,
        default=0,
        server_default="0",
    )

    subtotal = Column(
        Numeric(12, 2),
        nullable=False,
        default=0,
    )

    tax_rate = Column(
        Numeric(5, 2),
        nullable=False,
        default=0,
    )

    tax_amount = Column(
        Numeric(12, 2),
        nullable=False,
        default=0,
    )

    total = Column(
        Numeric(12, 2),
        nullable=False,
        default=0,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    invoice = relationship(
        "Invoice",
        back_populates="items",
    )
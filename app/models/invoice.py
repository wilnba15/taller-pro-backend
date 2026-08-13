from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Invoice(Base):
    __tablename__ = "invoices"

    __table_args__ = (
        UniqueConstraint(
            "workshop_id",
            "work_order_id",
            name="uq_invoice_workshop_work_order",
        ),
        UniqueConstraint(
            "workshop_id",
            "invoice_number",
            name="uq_invoice_workshop_number",
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    workshop_id = Column(
        Integer,
        ForeignKey("workshops.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    work_order_id = Column(
        Integer,
        ForeignKey("work_orders.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    client_id = Column(
        Integer,
        ForeignKey("clients.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    establishment_code = Column(
        String(3),
        nullable=False,
    )

    emission_point_code = Column(
        String(3),
        nullable=False,
    )

    sequential = Column(
        Integer,
        nullable=False,
    )

    invoice_number = Column(
        String(17),
        nullable=False,
        index=True,
    )

    issue_date = Column(
        Date,
        nullable=False,
    )

    # SNAPSHOT DEL CLIENTE
    client_name = Column(
        String(150),
        nullable=False,
    )

    client_identification = Column(
        String(20),
        nullable=False,
    )

    client_email = Column(
        String(120),
        nullable=True,
    )

    client_address = Column(
        String(200),
        nullable=True,
    )

    # TOTALES
    subtotal_0 = Column(
        Numeric(12, 2),
        nullable=False,
        default=0,
        server_default="0",
    )

    subtotal_taxed = Column(
        Numeric(12, 2),
        nullable=False,
        default=0,
        server_default="0",
    )

    tax_amount = Column(
        Numeric(12, 2),
        nullable=False,
        default=0,
        server_default="0",
    )

    discount = Column(
        Numeric(12, 2),
        nullable=False,
        default=0,
        server_default="0",
    )

    total = Column(
        Numeric(12, 2),
        nullable=False,
        default=0,
        server_default="0",
    )

    status = Column(
        String(30),
        nullable=False,
        default="borrador",
        server_default="borrador",
        index=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    workshop = relationship("Workshop")
    work_order = relationship("WorkOrder")
    client = relationship("Client")

    items = relationship(
        "InvoiceItem",
        back_populates="invoice",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
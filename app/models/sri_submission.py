from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class SriSubmission(Base):
    __tablename__ = "sri_submissions"

    __table_args__ = (
        UniqueConstraint(
            "workshop_id",
            "invoice_id",
            name="uq_sri_submission_workshop_invoice",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)

    workshop_id = Column(
        Integer,
        ForeignKey("workshops.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    invoice_id = Column(
        Integer,
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    electronic_signature_id = Column(
        Integer,
        ForeignKey("electronic_signatures.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    access_key = Column(String(49), nullable=False, index=True)
    environment = Column(String(20), nullable=False, default="pruebas")

    reception_status = Column(String(30), nullable=True, index=True)
    reception_messages = Column(Text, nullable=True)
    reception_raw = Column(Text, nullable=True)
    received_at = Column(DateTime(timezone=True), nullable=True)

    authorization_status = Column(String(30), nullable=True, index=True)
    authorization_number = Column(String(60), nullable=True, index=True)
    authorization_date = Column(String(80), nullable=True)
    authorization_environment = Column(String(30), nullable=True)
    authorization_messages = Column(Text, nullable=True)
    authorization_raw = Column(Text, nullable=True)
    authorized_xml = Column(Text, nullable=True)
    authorized_at = Column(DateTime(timezone=True), nullable=True)

    status = Column(
        String(30),
        nullable=False,
        default="pendiente",
        server_default="pendiente",
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

    invoice = relationship("Invoice")
    electronic_signature = relationship("ElectronicSignature")
    workshop = relationship("Workshop")

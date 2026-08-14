from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class ElectronicSignature(Base):
    __tablename__ = "electronic_signatures"
    __table_args__ = (
        UniqueConstraint("workshop_id", "invoice_id", name="uq_electronic_signature_workshop_invoice"),
        UniqueConstraint("electronic_document_id", name="uq_electronic_signature_document"),
    )

    id = Column(Integer, primary_key=True, index=True)
    workshop_id = Column(Integer, ForeignKey("workshops.id", ondelete="CASCADE"), nullable=False, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    electronic_document_id = Column(Integer, ForeignKey("electronic_documents.id", ondelete="CASCADE"), nullable=False, index=True)

    certificate_subject = Column(Text, nullable=False)
    certificate_issuer = Column(Text, nullable=False)
    certificate_serial = Column(String(120), nullable=False)
    valid_from = Column(DateTime(timezone=True), nullable=False)
    valid_to = Column(DateTime(timezone=True), nullable=False)

    signature_algorithm = Column(String(100), nullable=False, default="RSA-SHA1", server_default="RSA-SHA1")
    signed_xml = Column(Text, nullable=False)
    status = Column(String(30), nullable=False, default="firmado", server_default="firmado", index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    invoice = relationship("Invoice")
    electronic_document = relationship("ElectronicDocument")
    workshop = relationship("Workshop")

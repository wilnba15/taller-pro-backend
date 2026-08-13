from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class ElectronicDocument(Base):
    __tablename__ = "electronic_documents"

    __table_args__ = (
        UniqueConstraint(
            "workshop_id",
            "invoice_id",
            name="uq_electronic_document_workshop_invoice",
        ),
        UniqueConstraint(
            "workshop_id",
            "access_key",
            name="uq_electronic_document_workshop_access_key",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    workshop_id = Column(Integer, ForeignKey("workshops.id", ondelete="CASCADE"), nullable=False, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    document_type = Column(String(2), nullable=False, default="01", server_default="01")
    xml_version = Column(String(10), nullable=False, default="2.1.0", server_default="2.1.0")
    environment = Column(String(20), nullable=False, default="pruebas", server_default="pruebas")
    numeric_code = Column(String(8), nullable=False)
    access_key = Column(String(49), nullable=False, index=True)
    xml_content = Column(Text, nullable=False)
    status = Column(String(30), nullable=False, default="generado", server_default="generado", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    invoice = relationship("Invoice")
    workshop = relationship("Workshop")

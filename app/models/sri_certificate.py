from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class SriCertificate(Base):
    __tablename__ = "sri_certificates"

    __table_args__ = (
        UniqueConstraint(
            "workshop_id",
            name="uq_sri_certificate_workshop",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)

    workshop_id = Column(
        Integer,
        ForeignKey("workshops.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    filename = Column(String(255), nullable=False)
    encrypted_p12 = Column(Text, nullable=False)
    encrypted_password = Column(Text, nullable=False)

    certificate_subject = Column(Text, nullable=False)
    certificate_issuer = Column(Text, nullable=False)
    certificate_serial = Column(String(120), nullable=False)

    valid_from = Column(DateTime(timezone=True), nullable=False)
    valid_to = Column(DateTime(timezone=True), nullable=False)

    sha256 = Column(String(64), nullable=False)
    status = Column(
        String(30),
        nullable=False,
        default="configurado",
        server_default="configurado",
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

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class SriSetting(Base):
    __tablename__ = "sri_settings"

    id = Column(Integer, primary_key=True, index=True)

    workshop_id = Column(
        Integer,
        ForeignKey("workshops.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Por ahora solo configuración interna.
    # Más adelante se usará para ambiente SRI real.
    environment = Column(
        String(20),
        nullable=False,
        default="pruebas",
        server_default="pruebas",
    )

    establishment_code = Column(
        String(3),
        nullable=False,
        default="001",
        server_default="001",
    )

    emission_point_code = Column(
        String(3),
        nullable=False,
        default="001",
        server_default="001",
    )

    invoice_sequence = Column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )

    # Valor editable desde configuración.
    default_tax_rate = Column(
        Numeric(5, 2),
        nullable=False,
        default=15,
        server_default="15",
    )

    accounting_required = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    special_taxpayer_code = Column(
        String(20),
        nullable=True,
    )

    rimpe_type = Column(
        String(50),
        nullable=True,
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
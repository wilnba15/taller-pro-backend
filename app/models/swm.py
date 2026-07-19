from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import relationship

from app.database import Base


class SwmVehicle(Base):
    __tablename__ = "swm_vehicles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("swm_users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    owner_name = Column(String(120), nullable=True)
    model = Column(String(50), nullable=False)
    year = Column(Integer, nullable=False)
    engine = Column(String(80), nullable=True)
    transmission = Column(String(80), nullable=True)
    city = Column(String(80), nullable=True)
    usage_type = Column(String(80), nullable=True)
    current_mileage = Column(Integer, nullable=False, default=0)

    plate = Column(String(30), nullable=True)
    vin = Column(String(80), nullable=True)
    color = Column(String(50), nullable=True)
    fuel_type = Column(String(50), nullable=True, default="Gasolina")
    purchase_date = Column(Date, nullable=True)
    nickname = Column(String(80), nullable=True)
    photo_url = Column(String(500), nullable=True)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("SwmUser", back_populates="vehicles")

    service_records = relationship(
        "SwmServiceRecord",
        back_populates="vehicle",
        cascade="all, delete-orphan",
    )

    service_orders = relationship(
        "SwmServiceOrder",
        back_populates="vehicle",
        cascade="all, delete-orphan",
    )

    fuel_records = relationship(
        "SwmFuelRecord",
        back_populates="vehicle",
        cascade="all, delete-orphan",
    )

    ai_queries = relationship(
        "SwmAiQuery",
        back_populates="vehicle",
        cascade="all, delete-orphan",
    )


class SwmMaintenanceSchedule(Base):
    __tablename__ = "swm_maintenance_schedule"

    id = Column(Integer, primary_key=True, index=True)
    mileage = Column(Integer, nullable=False, index=True)
    item_code = Column(String(80), nullable=False)
    item_name = Column(String(200), nullable=False)
    category = Column(String(80), nullable=True)
    description = Column(Text, nullable=True)
    is_required = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, server_default=func.now())

    service_records = relationship("SwmServiceRecord", back_populates="schedule")


class SwmServiceOrder(Base):
    __tablename__ = "swm_service_orders"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(
        Integer,
        ForeignKey("swm_vehicles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    order_number = Column(String(50), nullable=True, index=True)

    # maintenance = mantenimiento programado
    # repair/bodywork/accident/diagnostic/other = eventos no programados
    order_type = Column(String(50), nullable=False, default="maintenance", index=True)
    title = Column(String(180), nullable=True)
    description = Column(Text, nullable=True)

    service_mileage = Column(Integer, nullable=False)
    service_date = Column(Date, nullable=False)

    workshop = Column(String(150), nullable=True)
    mechanic_name = Column(String(120), nullable=True)

    labor_cost = Column(Numeric(10, 2), nullable=False, default=0)
    parts_cost = Column(Numeric(10, 2), nullable=False, default=0)
    total_cost = Column(Numeric(10, 2), nullable=False, default=0)

    invoice_number = Column(String(80), nullable=True)
    status = Column(String(50), nullable=False, default="realizado")
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, server_default=func.now())

    vehicle = relationship("SwmVehicle", back_populates="service_orders")
    records = relationship(
        "SwmServiceRecord",
        back_populates="service_order",
        cascade="all, delete-orphan",
    )


class SwmServiceRecord(Base):
    __tablename__ = "swm_service_records"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(
        Integer,
        ForeignKey("swm_vehicles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    service_order_id = Column(
        Integer,
        ForeignKey("swm_service_orders.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    schedule_id = Column(
        Integer,
        ForeignKey("swm_maintenance_schedule.id"),
        nullable=True,
    )
    service_mileage = Column(Integer, nullable=False)
    service_date = Column(Date, nullable=False)
    workshop = Column(String(150), nullable=True)
    cost = Column(Numeric(10, 2), nullable=False, default=0)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    vehicle = relationship("SwmVehicle", back_populates="service_records")
    service_order = relationship("SwmServiceOrder", back_populates="records")
    schedule = relationship("SwmMaintenanceSchedule", back_populates="service_records")


class SwmFuelRecord(Base):
    __tablename__ = "swm_fuel_records"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(
        Integer,
        ForeignKey("swm_vehicles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fuel_date = Column(Date, nullable=False, index=True)
    mileage = Column(Integer, nullable=False)
    amount = Column(Numeric(10, 2), nullable=False, default=0)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    vehicle = relationship("SwmVehicle", back_populates="fuel_records")


class SwmAiQuery(Base):
    __tablename__ = "swm_ai_queries"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(
        Integer,
        ForeignKey("swm_vehicles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    symptom = Column(Text, nullable=False)
    ai_response = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    vehicle = relationship("SwmVehicle", back_populates="ai_queries")

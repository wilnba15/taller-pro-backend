from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


# =========================
# VEHÍCULOS
# =========================

class SwmVehicleBase(BaseModel):
    owner_name: Optional[str] = Field(default=None, max_length=120)
    model: str = Field(..., max_length=50)
    year: int = Field(..., ge=1900, le=2100)
    engine: Optional[str] = Field(default=None, max_length=80)
    transmission: Optional[str] = Field(default=None, max_length=80)
    city: Optional[str] = Field(default=None, max_length=80)
    usage_type: Optional[str] = Field(default=None, max_length=80)
    current_mileage: int = Field(default=0, ge=0)

    plate: Optional[str] = Field(default=None, max_length=30)
    vin: Optional[str] = Field(default=None, max_length=80)
    color: Optional[str] = Field(default=None, max_length=50)
    fuel_type: Optional[str] = Field(default="Gasolina", max_length=50)
    purchase_date: Optional[date] = None
    nickname: Optional[str] = Field(default=None, max_length=80)


class SwmVehicleCreate(SwmVehicleBase):
    pass


class SwmVehicleUpdate(BaseModel):
    owner_name: Optional[str] = Field(default=None, max_length=120)
    model: Optional[str] = Field(default=None, max_length=50)
    year: Optional[int] = Field(default=None, ge=1900, le=2100)
    engine: Optional[str] = Field(default=None, max_length=80)
    transmission: Optional[str] = Field(default=None, max_length=80)
    city: Optional[str] = Field(default=None, max_length=80)
    usage_type: Optional[str] = Field(default=None, max_length=80)
    current_mileage: Optional[int] = Field(default=None, ge=0)

    plate: Optional[str] = Field(default=None, max_length=30)
    vin: Optional[str] = Field(default=None, max_length=80)
    color: Optional[str] = Field(default=None, max_length=50)
    fuel_type: Optional[str] = Field(default=None, max_length=50)
    purchase_date: Optional[date] = None
    nickname: Optional[str] = Field(default=None, max_length=80)


class SwmVehicleResponse(SwmVehicleBase):
    id: int
    user_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# =========================
# CALENDARIO
# =========================

class SwmMaintenanceScheduleResponse(BaseModel):
    id: int
    mileage: int
    item_code: str
    item_name: str
    category: Optional[str] = None
    description: Optional[str] = None
    is_required: bool

    class Config:
        from_attributes = True


# =========================
# ÓRDENES / HISTORIAL
# =========================

class SwmServiceOrderBase(BaseModel):
    vehicle_id: int = Field(..., gt=0)
    order_number: Optional[str] = Field(default=None, max_length=50)

    order_type: str = Field(default="maintenance", max_length=50)
    title: Optional[str] = Field(default=None, max_length=180)
    description: Optional[str] = None

    service_mileage: int = Field(..., ge=0)
    service_date: date
    workshop: Optional[str] = Field(default=None, max_length=150)
    mechanic_name: Optional[str] = Field(default=None, max_length=120)
    labor_cost: Decimal = Field(default=Decimal("0.00"), ge=0)
    parts_cost: Decimal = Field(default=Decimal("0.00"), ge=0)
    total_cost: Decimal = Field(default=Decimal("0.00"), ge=0)
    invoice_number: Optional[str] = Field(default=None, max_length=80)
    status: str = Field(default="realizado", max_length=50)
    notes: Optional[str] = None


class SwmServiceOrderCreate(SwmServiceOrderBase):
    pass


class SwmServiceOrderResponse(SwmServiceOrderBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class SwmServiceRecordCreate(BaseModel):
    vehicle_id: int = Field(..., gt=0)
    service_order_id: Optional[int] = Field(default=None, gt=0)
    schedule_id: Optional[int] = Field(default=None, gt=0)
    service_mileage: int = Field(..., ge=0)
    service_date: date
    workshop: Optional[str] = Field(default=None, max_length=150)
    cost: Decimal = Field(default=Decimal("0.00"), ge=0)
    notes: Optional[str] = None


class SwmServiceRecordResponse(SwmServiceRecordCreate):
    id: int
    created_at: datetime
    item_name: Optional[str] = None
    item_code: Optional[str] = None
    category: Optional[str] = None
    order_type: Optional[str] = None
    order_title: Optional[str] = None
    order_description: Optional[str] = None
    order_total_cost: Optional[Decimal] = None

    class Config:
        from_attributes = True


# =========================
# DASHBOARD / MANTENIMIENTO
# =========================

class SwmMaintenanceItemStatus(SwmMaintenanceScheduleResponse):
    status: str
    completed: bool


class SwmDashboardResponse(BaseModel):
    vehicle: SwmVehicleResponse
    next_maintenance_mileage: Optional[int] = None
    kilometers_remaining: Optional[int] = None
    pending_items: int
    completed_items: int
    total_items: int
    general_status: str


class SwmMaintenanceResponse(BaseModel):
    vehicle_id: int
    current_mileage: int
    overdue_mileages: list[int]
    current_maintenance_mileage: Optional[int] = None
    next_maintenance_mileage: Optional[int] = None
    items: list[SwmMaintenanceItemStatus]


# =========================
# SWM CARE IA
# =========================

class SwmAiQueryCreate(BaseModel):
    vehicle_id: Optional[int] = Field(default=None, gt=0)
    symptom: str = Field(..., min_length=3)


class SwmAiQueryResponse(BaseModel):
    id: int
    vehicle_id: Optional[int] = None
    symptom: str
    ai_response: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

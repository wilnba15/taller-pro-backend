from pydantic import BaseModel
from typing import Optional, Literal
from datetime import date, datetime
from decimal import Decimal


class WorkOrderBase(BaseModel):
    workshop_id: int
    client_id: int
    vehicle_id: int
    entry_date: date
    estimated_delivery_date: Optional[date] = None
    status: Literal["pendiente", "en_proceso", "finalizado", "entregado"] = "pendiente"
    issue_description: str
    diagnosis: Optional[str] = None
    work_performed: Optional[str] = None
    notes: Optional[str] = None
    labor_cost: Decimal = 0
    parts_cost: Decimal = 0


class WorkOrderCreate(WorkOrderBase):
    pass


class WorkOrderUpdate(WorkOrderBase):
    pass


class WorkOrderResponse(WorkOrderBase):
    id: int
    total: Decimal
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
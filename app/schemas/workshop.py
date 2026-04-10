from pydantic import BaseModel, EmailStr
from typing import Optional, Literal
from datetime import datetime


class WorkshopBase(BaseModel):
    name: str
    owner_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    status: Literal["activo", "inactivo"] = "activo"


class WorkshopCreate(WorkshopBase):
    pass


class WorkshopUpdate(WorkshopBase):
    pass


class WorkshopResponse(WorkshopBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True
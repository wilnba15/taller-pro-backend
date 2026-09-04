from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field


class WorkshopCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    business_name: Optional[str] = Field(default=None, max_length=180)
    ruc: Optional[str] = Field(default=None, max_length=20)
    owner_name: Optional[str] = Field(default=None, max_length=150)
    phone: Optional[str] = Field(default=None, max_length=20)
    email: Optional[EmailStr] = None
    address: Optional[str] = Field(default=None, max_length=200)
    logo_url: Optional[str] = Field(default=None, max_length=500)
    footer_text: Optional[str] = None
    inventory_enabled: bool = False
    billing_enabled: bool = False
    status: Literal["activo", "inactivo"] = "activo"


class WorkshopUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=150)
    business_name: Optional[str] = Field(default=None, max_length=180)
    ruc: Optional[str] = Field(default=None, max_length=20)
    owner_name: Optional[str] = Field(default=None, max_length=150)
    phone: Optional[str] = Field(default=None, max_length=20)
    email: Optional[EmailStr] = None
    address: Optional[str] = Field(default=None, max_length=200)
    logo_url: Optional[str] = Field(default=None, max_length=500)
    footer_text: Optional[str] = None
    inventory_enabled: Optional[bool] = None
    billing_enabled: Optional[bool] = None
    status: Optional[Literal["activo", "inactivo"]] = None


class WorkshopSetupUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=150)
    business_name: Optional[str] = Field(default=None, max_length=180)
    ruc: Optional[str] = Field(default=None, max_length=20)
    owner_name: Optional[str] = Field(default=None, max_length=150)
    phone: Optional[str] = Field(default=None, max_length=20)
    email: Optional[EmailStr] = None
    address: Optional[str] = Field(default=None, max_length=200)
    logo_url: Optional[str] = Field(default=None, max_length=500)
    footer_text: Optional[str] = None
    inventory_enabled: Optional[bool] = None
    billing_enabled: Optional[bool] = None


class WorkshopResponse(BaseModel):
    id: int
    name: str
    business_name: Optional[str] = None
    ruc: Optional[str] = None
    owner_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    address: Optional[str] = None
    logo_url: Optional[str] = None
    footer_text: Optional[str] = None
    inventory_enabled: bool = False
    billing_enabled: bool = False
    setup_completed: bool
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class WorkshopSetupStatus(BaseModel):
    setup_completed: bool
    missing_fields: list[str]

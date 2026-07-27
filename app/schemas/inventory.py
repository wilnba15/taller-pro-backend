from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field, field_validator

class InventoryProductBase(BaseModel):
    code: Optional[str] = Field(default=None, max_length=50)
    name: str = Field(min_length=2, max_length=180)
    category: Optional[str] = Field(default=None, max_length=100)
    brand: Optional[str] = Field(default=None, max_length=100)
    stock: Decimal = Field(default=0, ge=0)
    minimum_stock: Decimal = Field(default=0, ge=0)
    cost: Decimal = Field(default=0, ge=0)
    sale_price: Decimal = Field(default=0, ge=0)
    is_active: bool = True

    @field_validator("code", "category", "brand", mode="before")
    @classmethod
    def empty_to_none(cls, value):
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value):
        return value.strip() if isinstance(value, str) else value

class InventoryProductCreate(InventoryProductBase):
    pass

class InventoryProductUpdate(BaseModel):
    code: Optional[str] = Field(default=None, max_length=50)
    name: Optional[str] = Field(default=None, min_length=2, max_length=180)
    category: Optional[str] = Field(default=None, max_length=100)
    brand: Optional[str] = Field(default=None, max_length=100)
    stock: Optional[Decimal] = Field(default=None, ge=0)
    minimum_stock: Optional[Decimal] = Field(default=None, ge=0)
    cost: Optional[Decimal] = Field(default=None, ge=0)
    sale_price: Optional[Decimal] = Field(default=None, ge=0)
    is_active: Optional[bool] = None

class InventoryProductResponse(InventoryProductBase):
    id: int
    workshop_id: int
    created_at: datetime
    updated_at: datetime
    low_stock: bool

    class Config:
        from_attributes = True

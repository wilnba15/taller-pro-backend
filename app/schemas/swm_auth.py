from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class SwmUserCreate(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(..., min_length=6)
    phone: Optional[str] = Field(default=None, max_length=30)
    city: Optional[str] = Field(default=None, max_length=80)
    country: Optional[str] = Field(default="Ecuador", max_length=80)


class SwmUserLogin(BaseModel):
    email: EmailStr
    password: str


class SwmDirectResetPasswordRequest(BaseModel):
    email: EmailStr
    reset_code: str = Field(..., min_length=8, max_length=200)
    new_password: str = Field(..., min_length=6, max_length=128)


class SwmMessageResponse(BaseModel):
    message: str


class SwmUserResponse(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    phone: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class SwmTokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: SwmUserResponse

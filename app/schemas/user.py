from pydantic import BaseModel, EmailStr
from datetime import datetime


class UserCreate(BaseModel):
    workshop_id: int
    full_name: str
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    workshop_id: int
    full_name: str
    email: EmailStr
    role: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    workshop_id: int
    user_name: str
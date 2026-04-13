from pydantic import BaseModel
from datetime import datetime


class WorkOrderPhotoCreate(BaseModel):
    work_order_id: int
    image_url: str


class WorkOrderPhotoResponse(BaseModel):
    id: int
    work_order_id: int
    image_url: str
    created_at: datetime

    class Config:
        from_attributes = True
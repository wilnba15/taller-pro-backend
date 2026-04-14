from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.work_order import WorkOrder
from app.models.work_order_photo import WorkOrderPhoto
from app.schemas.work_order_photo import WorkOrderPhotoCreate, WorkOrderPhotoResponse

router = APIRouter(prefix="/work-order-photos", tags=["Work Order Photos"])


@router.post("/", response_model=WorkOrderPhotoResponse)
def create_work_order_photo(data: WorkOrderPhotoCreate, db: Session = Depends(get_db)):
    work_order = db.query(WorkOrder).filter(WorkOrder.id == data.work_order_id).first()
    if not work_order:
        raise HTTPException(status_code=404, detail="Orden de trabajo no encontrada")

    photo = WorkOrderPhoto(
        work_order_id=data.work_order_id,
        image_url=data.image_url
    )
    db.add(photo)
    db.commit()
    db.refresh(photo)
    return photo


@router.get("/work-order/{work_order_id}", response_model=list[WorkOrderPhotoResponse])
def list_work_order_photos(work_order_id: int, db: Session = Depends(get_db)):
    work_order = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not work_order:
        raise HTTPException(status_code=404, detail="Orden de trabajo no encontrada")

    photos = (
        db.query(WorkOrderPhoto)
        .filter(WorkOrderPhoto.work_order_id == work_order_id)
        .order_by(WorkOrderPhoto.id.desc())
        .all()
    )
    return photos

@router.delete("/{photo_id}")
def delete_work_order_photo(photo_id: int, db: Session = Depends(get_db)):
    photo = db.query(WorkOrderPhoto).filter(WorkOrderPhoto.id == photo_id).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Foto no encontrada")

    db.delete(photo)
    db.commit()
    return {"message": "Foto eliminada correctamente"}
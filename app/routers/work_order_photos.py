from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.work_order import WorkOrder
from app.models.work_order_photo import WorkOrderPhoto
from app.models.user import User
from app.core.security import get_current_user
from app.schemas.work_order_photo import WorkOrderPhotoCreate, WorkOrderPhotoResponse

router = APIRouter(prefix="/work-order-photos", tags=["Work Order Photos"])


def get_owned_work_order(work_order_id: int, db: Session, current_user: User) -> WorkOrder:
    work_order = (
        db.query(WorkOrder)
        .filter(
            WorkOrder.id == work_order_id,
            WorkOrder.workshop_id == current_user.workshop_id,
        )
        .first()
    )
    if not work_order:
        raise HTTPException(status_code=404, detail="Orden de trabajo no encontrada")
    return work_order


@router.post("/", response_model=WorkOrderPhotoResponse)
def create_work_order_photo(
    data: WorkOrderPhotoCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    work_order = get_owned_work_order(data.work_order_id, db, current_user)

    if work_order.status == "entregado":
        raise HTTPException(status_code=400, detail="No se pueden agregar fotos a una orden entregada")

    photo = WorkOrderPhoto(
        work_order_id=work_order.id,
        image_url=data.image_url,
    )
    db.add(photo)
    db.commit()
    db.refresh(photo)
    return photo


@router.get("/work-order/{work_order_id}", response_model=list[WorkOrderPhotoResponse])
def list_work_order_photos(
    work_order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_owned_work_order(work_order_id, db, current_user)
    return (
        db.query(WorkOrderPhoto)
        .filter(WorkOrderPhoto.work_order_id == work_order_id)
        .order_by(WorkOrderPhoto.id.desc())
        .all()
    )


@router.delete("/{photo_id}")
def delete_work_order_photo(
    photo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    photo = db.query(WorkOrderPhoto).filter(WorkOrderPhoto.id == photo_id).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Foto no encontrada")

    work_order = get_owned_work_order(photo.work_order_id, db, current_user)
    if work_order.status == "entregado":
        raise HTTPException(status_code=400, detail="No se pueden eliminar fotos de una orden entregada")

    db.delete(photo)
    db.commit()
    return {"message": "Foto eliminada correctamente"}

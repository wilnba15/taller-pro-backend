from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.work_order import WorkOrder
from app.models.client import Client
from app.models.vehicle import Vehicle
from app.models.workshop import Workshop
from app.schemas.work_order import WorkOrderCreate, WorkOrderUpdate, WorkOrderResponse

router = APIRouter(prefix="/work-orders", tags=["Work Orders"])


@router.post("/", response_model=WorkOrderResponse)
def create_work_order(work_order: WorkOrderCreate, db: Session = Depends(get_db)):
    workshop = db.query(Workshop).filter(Workshop.id == work_order.workshop_id).first()
    if not workshop:
        raise HTTPException(status_code=404, detail="Taller no encontrado")

    client = db.query(Client).filter(Client.id == work_order.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    vehicle = db.query(Vehicle).filter(Vehicle.id == work_order.vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehículo no encontrado")

    if client.workshop_id != work_order.workshop_id:
        raise HTTPException(status_code=400, detail="El cliente no pertenece al taller seleccionado")

    if vehicle.workshop_id != work_order.workshop_id:
        raise HTTPException(status_code=400, detail="El vehículo no pertenece al taller seleccionado")

    if vehicle.client_id != client.id:
        raise HTTPException(status_code=400, detail="El vehículo no pertenece al cliente seleccionado")

    total = Decimal(work_order.labor_cost) + Decimal(work_order.parts_cost)

    db_work_order = WorkOrder(
        **work_order.model_dump(),
        total=total
    )
    db.add(db_work_order)
    db.commit()
    db.refresh(db_work_order)
    return db_work_order


@router.get("/", response_model=list[WorkOrderResponse])
def list_work_orders(db: Session = Depends(get_db)):
    return db.query(WorkOrder).order_by(WorkOrder.id.desc()).all()


@router.get("/{work_order_id}", response_model=WorkOrderResponse)
def get_work_order(work_order_id: int, db: Session = Depends(get_db)):
    work_order = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not work_order:
        raise HTTPException(status_code=404, detail="Orden de trabajo no encontrada")
    return work_order


@router.put("/{work_order_id}", response_model=WorkOrderResponse)
def update_work_order(work_order_id: int, data: WorkOrderUpdate, db: Session = Depends(get_db)):
    work_order = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not work_order:
        raise HTTPException(status_code=404, detail="Orden de trabajo no encontrada")

    workshop = db.query(Workshop).filter(Workshop.id == data.workshop_id).first()
    if not workshop:
        raise HTTPException(status_code=404, detail="Taller no encontrado")

    client = db.query(Client).filter(Client.id == data.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    vehicle = db.query(Vehicle).filter(Vehicle.id == data.vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehículo no encontrado")

    if client.workshop_id != data.workshop_id:
        raise HTTPException(status_code=400, detail="El cliente no pertenece al taller seleccionado")

    if vehicle.workshop_id != data.workshop_id:
        raise HTTPException(status_code=400, detail="El vehículo no pertenece al taller seleccionado")

    if vehicle.client_id != client.id:
        raise HTTPException(status_code=400, detail="El vehículo no pertenece al cliente seleccionado")

    for key, value in data.model_dump().items():
        setattr(work_order, key, value)

    work_order.total = Decimal(data.labor_cost) + Decimal(data.parts_cost)

    db.commit()
    db.refresh(work_order)
    return work_order


@router.delete("/{work_order_id}")
def delete_work_order(work_order_id: int, db: Session = Depends(get_db)):
    work_order = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not work_order:
        raise HTTPException(status_code=404, detail="Orden de trabajo no encontrada")

    db.delete(work_order)
    db.commit()
    return {"message": "Orden de trabajo eliminada correctamente"}
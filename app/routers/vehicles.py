from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.vehicle import Vehicle
from app.models.client import Client
from app.models.workshop import Workshop
from app.models.user import User
from app.core.security import get_current_user
from app.schemas.vehicle import VehicleCreate, VehicleUpdate, VehicleResponse

router = APIRouter(prefix="/vehicles", tags=["Vehicles"])


@router.post("/", response_model=VehicleResponse)
def create_vehicle(vehicle: VehicleCreate, db: Session = Depends(get_db)):
    workshop = db.query(Workshop).filter(Workshop.id == vehicle.workshop_id).first()
    if not workshop:
        raise HTTPException(status_code=404, detail="Taller no encontrado")

    client = db.query(Client).filter(Client.id == vehicle.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    if client.workshop_id != vehicle.workshop_id:
        raise HTTPException(status_code=400, detail="El cliente no pertenece al taller seleccionado")

    existing_plate = db.query(Vehicle).filter(
        Vehicle.workshop_id == vehicle.workshop_id,
        Vehicle.plate == vehicle.plate
    ).first()
    if existing_plate:
        raise HTTPException(status_code=400, detail="La placa ya está registrada en este taller")

    db_vehicle = Vehicle(**vehicle.model_dump())
    db.add(db_vehicle)
    db.commit()
    db.refresh(db_vehicle)
    return db_vehicle


@router.get("/", response_model=list[VehicleResponse])
def list_vehicles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(Vehicle)
        .filter(Vehicle.workshop_id == current_user.workshop_id)
        .order_by(Vehicle.id.desc())
        .all()
    )


@router.get("/{vehicle_id}", response_model=VehicleResponse)
def get_vehicle(vehicle_id: int, db: Session = Depends(get_db)):
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehículo no encontrado")
    return vehicle


@router.put("/{vehicle_id}", response_model=VehicleResponse)
def update_vehicle(vehicle_id: int, data: VehicleUpdate, db: Session = Depends(get_db)):
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehículo no encontrado")

    workshop = db.query(Workshop).filter(Workshop.id == data.workshop_id).first()
    if not workshop:
        raise HTTPException(status_code=404, detail="Taller no encontrado")

    client = db.query(Client).filter(Client.id == data.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    if client.workshop_id != data.workshop_id:
        raise HTTPException(status_code=400, detail="El cliente no pertenece al taller seleccionado")

    existing_plate = db.query(Vehicle).filter(
        Vehicle.workshop_id == data.workshop_id,
        Vehicle.plate == data.plate,
        Vehicle.id != vehicle_id
    ).first()
    if existing_plate:
        raise HTTPException(status_code=400, detail="La placa ya está registrada en este taller")

    for key, value in data.model_dump().items():
        setattr(vehicle, key, value)

    db.commit()
    db.refresh(vehicle)
    return vehicle


@router.delete("/{vehicle_id}")
def delete_vehicle(vehicle_id: int, db: Session = Depends(get_db)):
    vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehículo no encontrado")

    db.delete(vehicle)
    db.commit()
    return {"message": "Vehículo eliminado correctamente"}
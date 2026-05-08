from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.vehicle import Vehicle
from app.models.client import Client
from app.models.user import User
from app.core.security import get_current_user
from app.schemas.vehicle import VehicleCreate, VehicleUpdate, VehicleResponse

router = APIRouter(prefix="/vehicles", tags=["Vehicles"])


def _normalize_plate(plate: str) -> str:
    return plate.strip().upper()


@router.post("/", response_model=VehicleResponse)
def create_vehicle(
    vehicle: VehicleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    workshop_id = current_user.workshop_id

    client = (
        db.query(Client)
        .filter(Client.id == vehicle.client_id, Client.workshop_id == workshop_id)
        .first()
    )
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado en este taller")

    plate = _normalize_plate(vehicle.plate)

    existing_plate = (
        db.query(Vehicle)
        .filter(Vehicle.workshop_id == workshop_id, Vehicle.plate == plate)
        .first()
    )
    if existing_plate:
        raise HTTPException(status_code=400, detail="La placa ya está registrada en este taller")

    data = vehicle.model_dump()
    data["plate"] = plate
    data["workshop_id"] = workshop_id

    db_vehicle = Vehicle(**data)
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
def get_vehicle(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    vehicle = (
        db.query(Vehicle)
        .filter(Vehicle.id == vehicle_id, Vehicle.workshop_id == current_user.workshop_id)
        .first()
    )
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehículo no encontrado en este taller")
    return vehicle


@router.put("/{vehicle_id}", response_model=VehicleResponse)
def update_vehicle(
    vehicle_id: int,
    data: VehicleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    workshop_id = current_user.workshop_id

    vehicle = (
        db.query(Vehicle)
        .filter(Vehicle.id == vehicle_id, Vehicle.workshop_id == workshop_id)
        .first()
    )
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehículo no encontrado en este taller")

    client = (
        db.query(Client)
        .filter(Client.id == data.client_id, Client.workshop_id == workshop_id)
        .first()
    )
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado en este taller")

    plate = _normalize_plate(data.plate)

    existing_plate = (
        db.query(Vehicle)
        .filter(
            Vehicle.workshop_id == workshop_id,
            Vehicle.plate == plate,
            Vehicle.id != vehicle_id,
        )
        .first()
    )
    if existing_plate:
        raise HTTPException(status_code=400, detail="La placa ya está registrada en este taller")

    update_data = data.model_dump()
    update_data["plate"] = plate
    update_data["workshop_id"] = workshop_id

    for key, value in update_data.items():
        setattr(vehicle, key, value)

    db.commit()
    db.refresh(vehicle)
    return vehicle


@router.delete("/{vehicle_id}")
def delete_vehicle(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    vehicle = (
        db.query(Vehicle)
        .filter(Vehicle.id == vehicle_id, Vehicle.workshop_id == current_user.workshop_id)
        .first()
    )
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehículo no encontrado en este taller")

    db.delete(vehicle)
    db.commit()
    return {"message": "Vehículo eliminado correctamente"}

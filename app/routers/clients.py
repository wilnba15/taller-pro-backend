from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database import get_db
from app.models.client import Client
from app.models.user import User
from app.schemas.client import ClientResponse

router = APIRouter(prefix="/clients", tags=["Clients"])


class ClientPayload(BaseModel):
    full_name: str
    identification: str
    phone: str
    email: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None


def clean_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    return value or None


@router.post("/", response_model=ClientResponse)
def create_client(
    data: ClientPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    workshop_id = current_user.workshop_id
    if not workshop_id:
        raise HTTPException(status_code=400, detail="El usuario no tiene taller asignado")

    identification = data.identification.strip()
    if not identification:
        raise HTTPException(status_code=400, detail="La identificación es obligatoria")

    existing = (
        db.query(Client)
        .filter(
            Client.workshop_id == workshop_id,
            Client.identification == identification,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail="La identificación ya está registrada en este taller",
        )

    db_client = Client(
        workshop_id=workshop_id,
        full_name=data.full_name.strip(),
        identification=identification,
        phone=data.phone.strip(),
        email=clean_text(data.email),
        address=clean_text(data.address),
        notes=clean_text(data.notes),
    )

    db.add(db_client)
    db.commit()
    db.refresh(db_client)
    return db_client


@router.get("/", response_model=list[ClientResponse])
def list_clients(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(Client)
        .filter(Client.workshop_id == current_user.workshop_id)
        .order_by(Client.id.desc())
        .all()
    )


@router.get("/{client_id}", response_model=ClientResponse)
def get_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    client = (
        db.query(Client)
        .filter(
            Client.id == client_id,
            Client.workshop_id == current_user.workshop_id,
        )
        .first()
    )
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return client


@router.put("/{client_id}", response_model=ClientResponse)
def update_client(
    client_id: int,
    data: ClientPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    workshop_id = current_user.workshop_id
    if not workshop_id:
        raise HTTPException(status_code=400, detail="El usuario no tiene taller asignado")

    client = (
        db.query(Client)
        .filter(
            Client.id == client_id,
            Client.workshop_id == workshop_id,
        )
        .first()
    )
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    identification = data.identification.strip()
    if not identification:
        raise HTTPException(status_code=400, detail="La identificación es obligatoria")

    existing = (
        db.query(Client)
        .filter(
            Client.workshop_id == workshop_id,
            Client.identification == identification,
            Client.id != client_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail="La identificación ya está registrada en este taller",
        )

    client.full_name = data.full_name.strip()
    client.identification = identification
    client.phone = data.phone.strip()
    client.email = clean_text(data.email)
    client.address = clean_text(data.address)
    client.notes = clean_text(data.notes)

    db.commit()
    db.refresh(client)
    return client


@router.delete("/{client_id}")
def delete_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    client = (
        db.query(Client)
        .filter(
            Client.id == client_id,
            Client.workshop_id == current_user.workshop_id,
        )
        .first()
    )
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    db.delete(client)
    db.commit()
    return {"message": "Cliente eliminado correctamente"}

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database import get_db
from app.models.user import User
from app.models.workshop import Workshop
from app.schemas.workshop import (
    WorkshopCreate,
    WorkshopResponse,
    WorkshopSetupStatus,
    WorkshopSetupUpdate,
    WorkshopUpdate,
)

router = APIRouter(prefix="/workshops", tags=["Workshops"])


def _clean_optional_text(value):
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def _get_current_workshop(db: Session, current_user: User) -> Workshop:
    workshop = (
        db.query(Workshop)
        .filter(Workshop.id == current_user.workshop_id)
        .first()
    )
    if not workshop:
        raise HTTPException(status_code=404, detail="Taller no encontrado")
    return workshop


def _missing_setup_fields(workshop: Workshop) -> list[str]:
    required_fields = {
        "name": workshop.name,
        "phone": workshop.phone,
        "email": workshop.email,
        "address": workshop.address,
        "logo_url": workshop.logo_url,
    }
    return [
        field_name
        for field_name, value in required_fields.items()
        if value is None or (isinstance(value, str) and not value.strip())
    ]


# =========================================================
# PERFIL DEL TALLER AUTENTICADO
# Estas rutas deben permanecer antes de /{workshop_id}
# =========================================================

@router.get("/me", response_model=WorkshopResponse)
def get_my_workshop(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _get_current_workshop(db, current_user)


@router.put("/me", response_model=WorkshopResponse)
def update_my_workshop(
    data: WorkshopSetupUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    workshop = _get_current_workshop(db, current_user)
    update_data = data.model_dump(exclude_unset=True)

    if "name" in update_data and update_data["name"]:
        normalized_name = update_data["name"].strip()
        existing = (
            db.query(Workshop)
            .filter(
                Workshop.name == normalized_name,
                Workshop.id != workshop.id,
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=400,
                detail="Ya existe otro taller con ese nombre",
            )
        update_data["name"] = normalized_name

    for key, value in update_data.items():
        setattr(workshop, key, _clean_optional_text(value))

    # Si se modifica el perfil, se vuelve a calcular su estado.
    workshop.setup_completed = len(_missing_setup_fields(workshop)) == 0

    db.commit()
    db.refresh(workshop)
    return workshop


@router.get("/me/setup-status", response_model=WorkshopSetupStatus)
def get_my_setup_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    workshop = _get_current_workshop(db, current_user)
    missing_fields = _missing_setup_fields(workshop)

    return {
        "setup_completed": len(missing_fields) == 0,
        "missing_fields": missing_fields,
    }


@router.post("/me/complete-setup", response_model=WorkshopResponse)
def complete_my_setup(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    workshop = _get_current_workshop(db, current_user)
    missing_fields = _missing_setup_fields(workshop)

    if missing_fields:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "La configuración inicial está incompleta",
                "missing_fields": missing_fields,
            },
        )

    workshop.setup_completed = True
    db.commit()
    db.refresh(workshop)
    return workshop


# =========================================================
# CRUD EXISTENTE
# Se conserva para no romper el flujo actual de administración.
# Más adelante puede restringirse a un superadministrador.
# =========================================================

@router.post("/", response_model=WorkshopResponse)
def create_workshop(
    workshop: WorkshopCreate,
    db: Session = Depends(get_db),
):
    name = workshop.name.strip()
    existing = db.query(Workshop).filter(Workshop.name == name).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Ya existe un taller con ese nombre",
        )

    data = workshop.model_dump()
    data["name"] = name

    db_workshop = Workshop(**data)
    db.add(db_workshop)
    db.commit()
    db.refresh(db_workshop)
    return db_workshop


@router.get("/", response_model=list[WorkshopResponse])
def list_workshops(db: Session = Depends(get_db)):
    return db.query(Workshop).order_by(Workshop.id.desc()).all()


@router.get("/{workshop_id}", response_model=WorkshopResponse)
def get_workshop(workshop_id: int, db: Session = Depends(get_db)):
    workshop = db.query(Workshop).filter(Workshop.id == workshop_id).first()
    if not workshop:
        raise HTTPException(status_code=404, detail="Taller no encontrado")
    return workshop


@router.put("/{workshop_id}", response_model=WorkshopResponse)
def update_workshop(
    workshop_id: int,
    data: WorkshopUpdate,
    db: Session = Depends(get_db),
):
    workshop = db.query(Workshop).filter(Workshop.id == workshop_id).first()
    if not workshop:
        raise HTTPException(status_code=404, detail="Taller no encontrado")

    update_data = data.model_dump(exclude_unset=True)

    if "name" in update_data and update_data["name"]:
        normalized_name = update_data["name"].strip()
        existing = (
            db.query(Workshop)
            .filter(
                Workshop.name == normalized_name,
                Workshop.id != workshop_id,
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=400,
                detail="Ya existe otro taller con ese nombre",
            )
        update_data["name"] = normalized_name

    for key, value in update_data.items():
        setattr(workshop, key, _clean_optional_text(value))

    workshop.setup_completed = len(_missing_setup_fields(workshop)) == 0

    db.commit()
    db.refresh(workshop)
    return workshop


@router.delete("/{workshop_id}")
def delete_workshop(workshop_id: int, db: Session = Depends(get_db)):
    workshop = db.query(Workshop).filter(Workshop.id == workshop_id).first()
    if not workshop:
        raise HTTPException(status_code=404, detail="Taller no encontrado")

    db.delete(workshop)
    db.commit()
    return {"message": "Taller eliminado correctamente"}

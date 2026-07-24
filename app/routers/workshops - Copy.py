from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.workshop import Workshop
from app.schemas.workshop import WorkshopCreate, WorkshopUpdate, WorkshopResponse

router = APIRouter(prefix="/workshops", tags=["Workshops"])


@router.post("/", response_model=WorkshopResponse)
def create_workshop(workshop: WorkshopCreate, db: Session = Depends(get_db)):
    existing = db.query(Workshop).filter(Workshop.name == workshop.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Ya existe un taller con ese nombre")

    db_workshop = Workshop(**workshop.model_dump())
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
def update_workshop(workshop_id: int, data: WorkshopUpdate, db: Session = Depends(get_db)):
    workshop = db.query(Workshop).filter(Workshop.id == workshop_id).first()
    if not workshop:
        raise HTTPException(status_code=404, detail="Taller no encontrado")

    existing = db.query(Workshop).filter(
        Workshop.name == data.name,
        Workshop.id != workshop_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Ya existe otro taller con ese nombre")

    for key, value in data.model_dump().items():
        setattr(workshop, key, value)

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
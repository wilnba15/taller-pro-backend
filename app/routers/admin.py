from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database import get_db
from app.models.user import User
from app.models.workshop import Workshop
from app.routers.auth import hash_password

router = APIRouter(prefix="/admin", tags=["SIADAUTO Admin"])


class AdminWorkshopCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    owner_name: str = Field(min_length=2, max_length=150)
    phone: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=150)
    address: str | None = Field(default=None, max_length=200)
    admin_name: str = Field(min_length=2, max_length=150)
    admin_email: str = Field(min_length=5, max_length=150)
    admin_password: str = Field(min_length=6, max_length=72)


class AdminWorkshopUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    owner_name: str | None = Field(default=None, max_length=150)
    phone: str | None = Field(default=None, max_length=20)
    email: str | None = Field(default=None, max_length=150)
    address: str | None = Field(default=None, max_length=200)
    admin_name: str | None = Field(default=None, max_length=150)
    admin_email: str | None = Field(default=None, max_length=150)
    admin_password: str | None = Field(default=None, max_length=72)


class AdminWorkshopStatusUpdate(BaseModel):
    status: str


def require_superadmin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "superadmin":
        raise HTTPException(
            status_code=403,
            detail="Acceso exclusivo para el administrador de SIADAUTO",
        )
    return current_user



@router.get("/workshops")
def list_admin_workshops(
    db: Session = Depends(get_db),
    _: User = Depends(require_superadmin),
):
    workshops = db.query(Workshop).order_by(Workshop.id.desc()).all()

    result = []
    for workshop in workshops:
        admin_user = (
            db.query(User)
            .filter(User.workshop_id == workshop.id, User.role.in_(["admin", "superadmin"]))
            .order_by(User.id.asc())
            .first()
        )
        result.append(
            {
                "id": workshop.id,
                "name": workshop.name,
                "owner_name": workshop.owner_name,
                "phone": workshop.phone,
                "email": workshop.email,
                "address": workshop.address,
                "status": workshop.status,
                "setup_completed": workshop.setup_completed,
                "created_at": workshop.created_at,
                "admin_name": admin_user.full_name if admin_user else None,
                "admin_email": admin_user.email if admin_user else None,
            }
        )

    return result


@router.post("/workshops", status_code=201)
def create_admin_workshop(
    data: AdminWorkshopCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_superadmin),
):
    workshop_name = data.name.strip()
    admin_email = str(data.admin_email).strip().lower()

    if db.query(Workshop).filter(Workshop.name == workshop_name).first():
        raise HTTPException(status_code=400, detail="Ya existe un taller con ese nombre")

    if db.query(User).filter(User.email == admin_email).first():
        raise HTTPException(status_code=400, detail="Ya existe un usuario con ese correo")

    workshop = Workshop(
        name=workshop_name,
        owner_name=data.owner_name.strip(),
        phone=data.phone.strip() if data.phone else None,
        email=str(data.email).strip().lower() if data.email else None,
        address=data.address.strip() if data.address else None,
        status="activo",
        setup_completed=False,
    )

    db.add(workshop)
    db.flush()

    admin_user = User(
        workshop_id=workshop.id,
        full_name=data.admin_name.strip(),
        email=admin_email,
        password_hash=hash_password(data.admin_password),
        role="admin",
        status="active",
    )

    db.add(admin_user)
    db.commit()
    db.refresh(workshop)

    return {
        "message": "Taller y usuario administrador creados correctamente",
        "workshop_id": workshop.id,
    }


@router.put("/workshops/{workshop_id}")
def update_admin_workshop(
    workshop_id: int,
    data: AdminWorkshopUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_superadmin),
):
    workshop = db.query(Workshop).filter(Workshop.id == workshop_id).first()
    if not workshop:
        raise HTTPException(status_code=404, detail="Taller no encontrado")

    admin_user = (
        db.query(User)
        .filter(User.workshop_id == workshop_id, User.role.in_(["admin", "superadmin"]))
        .order_by(User.id.asc())
        .first()
    )

    update_data = data.model_dump(exclude_unset=True)

    # Los campos admin_* pertenecen a la tabla users, no a workshops.
    admin_name = update_data.pop("admin_name", None)
    admin_email = update_data.pop("admin_email", None)
    admin_password = update_data.pop("admin_password", None)

    if "name" in update_data and update_data["name"]:
        normalized_name = update_data["name"].strip()
        duplicated = (
            db.query(Workshop)
            .filter(Workshop.name == normalized_name, Workshop.id != workshop_id)
            .first()
        )
        if duplicated:
            raise HTTPException(
                status_code=400,
                detail="Ya existe otro taller con ese nombre",
            )
        update_data["name"] = normalized_name

    if "email" in update_data and update_data["email"]:
        update_data["email"] = update_data["email"].strip().lower()

    for field, value in update_data.items():
        if isinstance(value, str):
            value = value.strip() or None
        setattr(workshop, field, value)

    user_fields_received = any(
        field is not None for field in (admin_name, admin_email, admin_password)
    )

    if user_fields_received and not admin_user:
        raise HTTPException(
            status_code=404,
            detail="El taller no tiene un usuario administrador asociado",
        )

    if admin_user:
        if admin_name is not None:
            normalized_admin_name = admin_name.strip()
            if len(normalized_admin_name) < 2:
                raise HTTPException(
                    status_code=400,
                    detail="El nombre del usuario debe tener al menos 2 caracteres",
                )
            admin_user.full_name = normalized_admin_name

        if admin_email is not None:
            normalized_admin_email = admin_email.strip().lower()
            if len(normalized_admin_email) < 5:
                raise HTTPException(
                    status_code=400,
                    detail="El correo del usuario no es válido",
                )

            duplicated_user = (
                db.query(User)
                .filter(
                    User.email == normalized_admin_email,
                    User.id != admin_user.id,
                )
                .first()
            )
            if duplicated_user:
                raise HTTPException(
                    status_code=400,
                    detail="Ya existe otro usuario con ese correo",
                )

            admin_user.email = normalized_admin_email

        if admin_password is not None:
            normalized_password = admin_password.strip()
            if normalized_password:
                if len(normalized_password) < 6:
                    raise HTTPException(
                        status_code=400,
                        detail="La contraseña debe tener al menos 6 caracteres",
                    )
                admin_user.password_hash = hash_password(normalized_password)

    db.commit()
    db.refresh(workshop)

    return {
        "message": "Taller y usuario administrador actualizados correctamente",
        "workshop_id": workshop.id,
    }


@router.patch("/workshops/{workshop_id}/status")
def change_admin_workshop_status(
    workshop_id: int,
    data: AdminWorkshopStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin),
):
    if data.status not in {"activo", "suspendido"}:
        raise HTTPException(status_code=400, detail="Estado no válido")

    workshop = db.query(Workshop).filter(Workshop.id == workshop_id).first()
    if not workshop:
        raise HTTPException(status_code=404, detail="Taller no encontrado")

    if workshop.id == current_user.workshop_id and data.status == "suspendido":
        raise HTTPException(status_code=400, detail="No puedes suspender tu propio taller")

    workshop.status = data.status

    users = db.query(User).filter(User.workshop_id == workshop_id).all()
    for user in users:
        if user.role != "superadmin":
            user.status = "active" if data.status == "activo" else "inactive"

    db.commit()
    return {"message": f"Taller {data.status} correctamente"}

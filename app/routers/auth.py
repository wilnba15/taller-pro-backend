import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from jose import jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.workshop import Workshop
from app.schemas.user import (
    UserCreate,
    UserLogin,
    TokenResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])

SECRET_KEY = os.getenv("SECRET_KEY", "change_this_secret")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 12

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str):
    return pwd_context.hash(password)


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict):
    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + timedelta(
        hours=ACCESS_TOKEN_EXPIRE_HOURS
    )

    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm=ALGORITHM
    )

    return encoded_jwt


# =========================================
# CREAR PRIMER USUARIO
# =========================================

@router.post("/setup-first-user")
def setup_first_user(
    user: UserCreate,
    db: Session = Depends(get_db)
):
    existing = db.query(User).filter(
        User.email == user.email
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail="El usuario ya existe"
        )

    workshop = db.query(Workshop).filter(
        Workshop.id == user.workshop_id
    ).first()

    if not workshop:
        raise HTTPException(
            status_code=404,
            detail="Taller no encontrado"
        )

    db_user = User(
        workshop_id=user.workshop_id,
        full_name=user.full_name,
        email=user.email,
        password_hash=hash_password(user.password),
        role="admin",
        status="active"
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return {
        "message": "Usuario creado correctamente"
    }


# =========================================
# LOGIN
# =========================================

@router.post(
    "/login",
    response_model=TokenResponse
)
def login(
    credentials: UserLogin,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(
        User.email == credentials.email
    ).first()

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Credenciales incorrectas"
        )

    if user.status != "active":
        raise HTTPException(
            status_code=403,
            detail="Usuario inactivo"
        )

    if not verify_password(
        credentials.password,
        user.password_hash
    ):
        raise HTTPException(
            status_code=401,
            detail="Credenciales incorrectas"
        )

    access_token = create_access_token({
        "sub": str(user.id),
        "workshop_id": user.workshop_id,
        "email": user.email,
        "role": user.role
    })

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "workshop_id": user.workshop_id,
        "user_name": user.full_name
    }
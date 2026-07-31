import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.swm_user import SwmUser
from app.schemas.swm_auth import (
    SwmDirectResetPasswordRequest,
    SwmMessageResponse,
    SwmTokenResponse,
    SwmUserCreate,
    SwmUserLogin,
    SwmUserResponse,
)

router = APIRouter(prefix="/swm-auth", tags=["SWM Care Auth"])

SECRET_KEY = os.getenv("SWM_SECRET_KEY", os.getenv("SECRET_KEY", "change_this_secret"))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24 * 7

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_swm_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire, "scope": "swm"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_swm_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> SwmUser:
    token = credentials.credentials

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        scope = payload.get("scope")
        user_id = payload.get("sub")
        if scope != "swm" or user_id is None:
            raise HTTPException(status_code=401, detail="Token SWM inválido")
    except JWTError:
        raise HTTPException(status_code=401, detail="Token SWM inválido")

    user = db.query(SwmUser).filter(SwmUser.id == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=401, detail="Usuario SWM no encontrado")
    if user.status != "active":
        raise HTTPException(status_code=403, detail="Usuario SWM inactivo")
    return user


@router.post("/register", response_model=SwmTokenResponse, status_code=201)
def register_swm_user(payload: SwmUserCreate, db: Session = Depends(get_db)):
    email = payload.email.lower()
    existing_user = db.query(SwmUser).filter(SwmUser.email == email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="El correo ya está registrado")

    user = SwmUser(
        full_name=payload.full_name,
        email=email,
        password_hash=hash_password(payload.password),
        phone=payload.phone,
        city=payload.city,
        country=payload.country,
        status="active",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    access_token = create_swm_access_token(
        {"sub": str(user.id), "email": user.email, "full_name": user.full_name}
    )
    return {"access_token": access_token, "token_type": "bearer", "user": user}


@router.post("/login", response_model=SwmTokenResponse)
def login_swm_user(payload: SwmUserLogin, db: Session = Depends(get_db)):
    user = db.query(SwmUser).filter(SwmUser.email == payload.email.lower()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    if user.status != "active":
        raise HTTPException(status_code=403, detail="Usuario SWM inactivo")

    access_token = create_swm_access_token(
        {"sub": str(user.id), "email": user.email, "full_name": user.full_name}
    )
    return {"access_token": access_token, "token_type": "bearer", "user": user}


@router.post("/direct-reset-password", response_model=SwmMessageResponse)
def direct_reset_password(
    payload: SwmDirectResetPasswordRequest,
    db: Session = Depends(get_db),
):
    configured_code = os.getenv("SWM_PASSWORD_RESET_CODE", "").strip()

    if not configured_code:
        raise HTTPException(
            status_code=503,
            detail="El reseteo de contraseña no está configurado.",
        )

    if not secrets.compare_digest(payload.authorization_code.strip(), configured_code):
        raise HTTPException(status_code=403, detail="Código de autorización incorrecto.")

    user = db.query(SwmUser).filter(SwmUser.email == payload.email.lower()).first()
    if not user:
        raise HTTPException(status_code=404, detail="No existe una cuenta con ese correo.")
    if user.status != "active":
        raise HTTPException(status_code=403, detail="El usuario está inactivo.")

    user.password_hash = hash_password(payload.new_password)

    # Limpia campos antiguos de recuperación si todavía existen en el modelo/BD.
    if hasattr(user, "reset_token_hash"):
        user.reset_token_hash = None
    if hasattr(user, "reset_token_expires_at"):
        user.reset_token_expires_at = None

    db.commit()

    return {"message": "Tu contraseña fue actualizada correctamente."}


@router.get("/me", response_model=SwmUserResponse)
def get_me(current_user: SwmUser = Depends(get_current_swm_user)):
    return current_user

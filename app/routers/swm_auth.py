import hashlib
import os
import secrets
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.swm_user import SwmUser
from app.schemas.swm_auth import (
    SwmForgotPasswordRequest,
    SwmMessageResponse,
    SwmResetPasswordRequest,
    SwmTokenResponse,
    SwmUserCreate,
    SwmUserLogin,
    SwmUserResponse,
)

router = APIRouter(prefix="/swm-auth", tags=["SWM Care Auth"])

SECRET_KEY = os.getenv("SWM_SECRET_KEY", os.getenv("SECRET_KEY", "change_this_secret"))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24 * 7
RESET_TOKEN_EXPIRE_MINUTES = 30

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


def hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def send_password_reset_email(recipient: str, reset_url: str) -> None:
    host = os.getenv("SMTP_HOST", "").strip()
    port = int(os.getenv("SMTP_PORT", "587"))
    username = os.getenv("SMTP_USERNAME", "").strip()
    password = os.getenv("SMTP_PASSWORD", "")
    from_email = os.getenv("SMTP_FROM_EMAIL", username).strip()
    from_name = os.getenv("SMTP_FROM_NAME", "SWM Care").strip()
    use_tls = os.getenv("SMTP_USE_TLS", "true").lower() in {"1", "true", "yes"}

    if not host or not from_email:
        raise RuntimeError("El servicio de correo no está configurado.")

    message = EmailMessage()
    message["Subject"] = "Recupera tu contraseña de SWM Care"
    message["From"] = f"{from_name} <{from_email}>"
    message["To"] = recipient
    message.set_content(
        "Recibimos una solicitud para cambiar tu contraseña de SWM Care.\n\n"
        f"Abre este enlace durante los próximos {RESET_TOKEN_EXPIRE_MINUTES} minutos:\n"
        f"{reset_url}\n\n"
        "Si no solicitaste este cambio, puedes ignorar este mensaje."
    )

    with smtplib.SMTP(host, port, timeout=20) as smtp:
        if use_tls:
            smtp.starttls()
        if username:
            smtp.login(username, password)
        smtp.send_message(message)


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


@router.post("/forgot-password", response_model=SwmMessageResponse)
def forgot_password(payload: SwmForgotPasswordRequest, db: Session = Depends(get_db)):
    generic_message = (
        "Si el correo está registrado, recibirás un enlace para cambiar tu contraseña."
    )
    user = db.query(SwmUser).filter(SwmUser.email == payload.email.lower()).first()

    # No revelamos si un correo existe o no.
    if not user or user.status != "active":
        return {"message": generic_message}

    raw_token = secrets.token_urlsafe(32)
    user.reset_token_hash = hash_reset_token(raw_token)
    user.reset_token_expires_at = datetime.utcnow() + timedelta(
        minutes=RESET_TOKEN_EXPIRE_MINUTES
    )
    db.commit()

    frontend_url = os.getenv(
        "SWM_FRONTEND_URL", "https://swm-care-mobile.vercel.app"
    ).rstrip("/")
    reset_url = f"{frontend_url}/reset-password?token={raw_token}"

    try:
        send_password_reset_email(user.email, reset_url)
except Exception as exc:
    print("===================================")
    print("SMTP ERROR:")
    print(exc)
    print("===================================")

    user.reset_token_hash = None
    user.reset_token_expires_at = None
    db.commit()

    raise HTTPException(
        status_code=503,
        detail=f"SMTP ERROR: {str(exc)}"
    ) from exc

    return {"message": generic_message}


@router.post("/reset-password", response_model=SwmMessageResponse)
def reset_password(payload: SwmResetPasswordRequest, db: Session = Depends(get_db)):
    token_hash = hash_reset_token(payload.token)
    user = db.query(SwmUser).filter(SwmUser.reset_token_hash == token_hash).first()

    if (
        not user
        or not user.reset_token_expires_at
        or user.reset_token_expires_at < datetime.utcnow()
    ):
        raise HTTPException(
            status_code=400,
            detail="El enlace no es válido o ya venció. Solicita uno nuevo.",
        )

    user.password_hash = hash_password(payload.new_password)
    user.reset_token_hash = None
    user.reset_token_expires_at = None
    db.commit()

    return {"message": "Tu contraseña fue actualizada correctamente."}


@router.get("/me", response_model=SwmUserResponse)
def get_me(current_user: SwmUser = Depends(get_current_swm_user)):
    return current_user

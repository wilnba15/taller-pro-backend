from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database import get_db
from app.models.sri_setting import SriSetting
from app.models.user import User


router = APIRouter(
    prefix="/sri-settings",
    tags=["SRI Settings"],
)


# =========================================================
# SCHEMAS
# =========================================================

class SriSettingUpdate(BaseModel):
    environment: str = Field(default="pruebas")
    establishment_code: str = Field(min_length=3, max_length=3)
    emission_point_code: str = Field(min_length=3, max_length=3)
    default_tax_rate: Decimal = Field(ge=0, le=100)
    accounting_required: bool = False
    special_taxpayer_code: str | None = None
    rimpe_type: str | None = None


# =========================================================
# HELPERS
# =========================================================

def serialize_setting(setting: SriSetting) -> dict:
    return {
        "id": setting.id,
        "workshop_id": setting.workshop_id,
        "environment": setting.environment,
        "establishment_code": setting.establishment_code,
        "emission_point_code": setting.emission_point_code,
        "invoice_sequence": setting.invoice_sequence,
        "default_tax_rate": float(setting.default_tax_rate),
        "accounting_required": setting.accounting_required,
        "special_taxpayer_code": setting.special_taxpayer_code,
        "rimpe_type": setting.rimpe_type,
        "created_at": setting.created_at,
        "updated_at": setting.updated_at,
    }


def normalize_code(value: str, field_name: str) -> str:
    value = value.strip()

    if not value.isdigit():
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} debe contener únicamente números",
        )

    if len(value) != 3:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} debe tener exactamente 3 dígitos",
        )

    return value


# =========================================================
# GET - CONFIGURACIÓN DEL TALLER AUTENTICADO
# =========================================================

@router.get("/me")
def get_my_sri_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    setting = (
        db.query(SriSetting)
        .filter(SriSetting.workshop_id == current_user.workshop_id)
        .first()
    )

    if not setting:
        raise HTTPException(
            status_code=404,
            detail="El taller todavía no tiene configuración SRI",
        )

    return serialize_setting(setting)


# =========================================================
# PUT - ACTUALIZAR CONFIGURACIÓN DEL TALLER AUTENTICADO
# =========================================================

@router.put("/me")
def update_my_sri_settings(
    payload: SriSettingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    setting = (
        db.query(SriSetting)
        .filter(SriSetting.workshop_id == current_user.workshop_id)
        .first()
    )

    if not setting:
        raise HTTPException(
            status_code=404,
            detail="El taller todavía no tiene configuración SRI",
        )

    environment = payload.environment.strip().lower()

    if environment not in ("pruebas", "produccion"):
        raise HTTPException(
            status_code=400,
            detail="El ambiente debe ser 'pruebas' o 'produccion'",
        )

    # Seguridad Sprint 3A:
    # todavía NO permitimos activar producción desde la pantalla.
    if environment == "produccion":
        raise HTTPException(
            status_code=400,
            detail="El ambiente de producción todavía está bloqueado",
        )

    establishment_code = normalize_code(
        payload.establishment_code,
        "El código de establecimiento",
    )

    emission_point_code = normalize_code(
        payload.emission_point_code,
        "El punto de emisión",
    )

    setting.environment = environment
    setting.establishment_code = establishment_code
    setting.emission_point_code = emission_point_code
    setting.default_tax_rate = payload.default_tax_rate
    setting.accounting_required = payload.accounting_required

    setting.special_taxpayer_code = (
        payload.special_taxpayer_code.strip()
        if payload.special_taxpayer_code
        else None
    )

    setting.rimpe_type = (
        payload.rimpe_type.strip()
        if payload.rimpe_type
        else None
    )

    try:
        db.commit()
        db.refresh(setting)

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="No se pudo guardar la configuración SRI",
        )

    return serialize_setting(setting)
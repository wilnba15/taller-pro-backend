import hashlib

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database import get_db
from app.models.sri_certificate import SriCertificate
from app.models.user import User
from app.services.sri.certificate_vault import encrypt_bytes, encrypt_text
from app.services.sri.signer import (
    certificate_metadata,
    load_pkcs12_certificate_from_bytes,
)


router = APIRouter(
    prefix="/sri-certificates",
    tags=["SRI Certificates"],
)

MAX_P12_SIZE = 2 * 1024 * 1024


def serialize_certificate(certificate: SriCertificate | None) -> dict:
    if not certificate:
        return {
            "configured": False,
        }

    return {
        "configured": True,
        "id": certificate.id,
        "workshop_id": certificate.workshop_id,
        "filename": certificate.filename,
        "certificate_subject": certificate.certificate_subject,
        "certificate_issuer": certificate.certificate_issuer,
        "certificate_serial": certificate.certificate_serial,
        "valid_from": certificate.valid_from,
        "valid_to": certificate.valid_to,
        "sha256": certificate.sha256,
        "status": certificate.status,
        "created_at": certificate.created_at,
        "updated_at": certificate.updated_at,
    }


@router.get("/me")
def get_my_certificate(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    certificate = (
        db.query(SriCertificate)
        .filter(
            SriCertificate.workshop_id == current_user.workshop_id,
        )
        .first()
    )

    return serialize_certificate(certificate)


@router.post("/me")
async def upload_my_certificate(
    certificate: UploadFile = File(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    filename = (certificate.filename or "").strip()

    if not filename.lower().endswith(".p12"):
        raise HTTPException(
            status_code=400,
            detail="Seleccione un certificado con extensión .p12",
        )

    if not password:
        raise HTTPException(
            status_code=400,
            detail="Ingrese la contraseña del certificado",
        )

    content = await certificate.read()

    if not content:
        raise HTTPException(
            status_code=400,
            detail="El archivo .p12 está vacío",
        )

    if len(content) > MAX_P12_SIZE:
        raise HTTPException(
            status_code=400,
            detail="El certificado .p12 no puede superar los 2 MB",
        )

    try:
        _, parsed_certificate, _ = load_pkcs12_certificate_from_bytes(
            content,
            password,
        )
        metadata = certificate_metadata(parsed_certificate)

        encrypted_p12 = encrypt_bytes(content)
        encrypted_password = encrypt_text(password)

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    sha256 = hashlib.sha256(content).hexdigest().upper()

    db_certificate = (
        db.query(SriCertificate)
        .filter(
            SriCertificate.workshop_id == current_user.workshop_id,
        )
        .first()
    )

    if not db_certificate:
        db_certificate = SriCertificate(
            workshop_id=current_user.workshop_id,
            filename=filename,
            encrypted_p12=encrypted_p12,
            encrypted_password=encrypted_password,
            certificate_subject=metadata["subject"],
            certificate_issuer=metadata["issuer"],
            certificate_serial=metadata["serial"],
            valid_from=metadata["valid_from"],
            valid_to=metadata["valid_to"],
            sha256=sha256,
            status="configurado",
        )
        db.add(db_certificate)

    else:
        db_certificate.filename = filename
        db_certificate.encrypted_p12 = encrypted_p12
        db_certificate.encrypted_password = encrypted_password
        db_certificate.certificate_subject = metadata["subject"]
        db_certificate.certificate_issuer = metadata["issuer"]
        db_certificate.certificate_serial = metadata["serial"]
        db_certificate.valid_from = metadata["valid_from"]
        db_certificate.valid_to = metadata["valid_to"]
        db_certificate.sha256 = sha256
        db_certificate.status = "configurado"

    try:
        db.commit()
        db.refresh(db_certificate)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="No se pudo guardar el certificado electrónico",
        )

    return serialize_certificate(db_certificate)


@router.delete("/me")
def delete_my_certificate(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    certificate = (
        db.query(SriCertificate)
        .filter(
            SriCertificate.workshop_id == current_user.workshop_id,
        )
        .first()
    )

    if not certificate:
        return {
            "message": "No existe certificado configurado",
        }

    db.delete(certificate)
    db.commit()

    return {
        "message": "Certificado eliminado correctamente",
    }

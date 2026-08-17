import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database import get_db
from app.models.electronic_document import ElectronicDocument
from app.models.electronic_signature import ElectronicSignature
from app.models.invoice import Invoice
from app.models.sri_setting import SriSetting
from app.models.sri_submission import SriSubmission
from app.models.user import User

from app.services.sri.sri_client import (
    query_authorization,
    send_to_reception,
)


router = APIRouter(
    prefix="/sri-submissions",
    tags=["SRI Submissions"],
)


def get_owned_invoice(
    invoice_id: int,
    db: Session,
    current_user: User,
) -> Invoice:
    invoice = (
        db.query(Invoice)
        .filter(
            Invoice.id == invoice_id,
            Invoice.workshop_id == current_user.workshop_id,
        )
        .first()
    )

    if not invoice:
        raise HTTPException(
            status_code=404,
            detail="Factura no encontrada",
        )

    return invoice


def get_signature(
    invoice_id: int,
    db: Session,
    current_user: User,
) -> ElectronicSignature:
    signature = (
        db.query(ElectronicSignature)
        .filter(
            ElectronicSignature.invoice_id == invoice_id,
            ElectronicSignature.workshop_id == current_user.workshop_id,
        )
        .first()
    )

    if not signature:
        raise HTTPException(
            status_code=400,
            detail="Primero debe firmar el XML",
        )

    return signature


def get_document(
    invoice_id: int,
    db: Session,
    current_user: User,
) -> ElectronicDocument:
    document = (
        db.query(ElectronicDocument)
        .filter(
            ElectronicDocument.invoice_id == invoice_id,
            ElectronicDocument.workshop_id == current_user.workshop_id,
        )
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=400,
            detail="No existe documento electrónico para esta factura",
        )

    return document


def get_settings(
    db: Session,
    current_user: User,
) -> SriSetting:
    settings = (
        db.query(SriSetting)
        .filter(
            SriSetting.workshop_id == current_user.workshop_id,
        )
        .first()
    )

    if not settings:
        raise HTTPException(
            status_code=400,
            detail="No existe configuración SRI del taller",
        )

    return settings


def ensure_test_environment(
    settings: SriSetting,
):
    environment = (
        settings.environment
        or "pruebas"
    ).strip().lower()

    if environment not in {
        "pruebas",
        "prueba",
        "test",
        "certificacion",
        "certificación",
        "1",
    }:
        raise HTTPException(
            status_code=400,
            detail=(
                "Sprint 2C está bloqueado para PRODUCCIÓN. "
                "Cambie el ambiente a PRUEBAS."
            ),
        )


def serialize_submission(
    submission: SriSubmission,
) -> dict:
    def load_messages(value):
        if not value:
            return []

        try:
            return json.loads(value)
        except Exception:
            return []

    return {
        "id": submission.id,
        "workshop_id": submission.workshop_id,
        "invoice_id": submission.invoice_id,
        "electronic_signature_id": submission.electronic_signature_id,
        "access_key": submission.access_key,
        "environment": submission.environment,
        "reception_status": submission.reception_status,
        "reception_messages": load_messages(
            submission.reception_messages
        ),
        "received_at": submission.received_at,
        "authorization_status": submission.authorization_status,
        "authorization_number": submission.authorization_number,
        "authorization_date": submission.authorization_date,
        "authorization_environment": submission.authorization_environment,
        "authorization_messages": load_messages(
            submission.authorization_messages
        ),
        "authorized_at": submission.authorized_at,
        "status": submission.status,
        "created_at": submission.created_at,
        "updated_at": submission.updated_at,
    }


@router.post("/invoice/{invoice_id}/send")
def send_invoice_to_sri(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    invoice = get_owned_invoice(
        invoice_id,
        db,
        current_user,
    )

    signature = get_signature(
        invoice_id,
        db,
        current_user,
    )

    document = get_document(
        invoice_id,
        db,
        current_user,
    )

    settings = get_settings(
        db,
        current_user,
    )

    ensure_test_environment(
        settings
    )

    submission = (
        db.query(SriSubmission)
        .filter(
            SriSubmission.invoice_id == invoice.id,
            SriSubmission.workshop_id == current_user.workshop_id,
        )
        .first()
    )

    if not submission:
        submission = SriSubmission(
            workshop_id=current_user.workshop_id,
            invoice_id=invoice.id,
            electronic_signature_id=signature.id,
            access_key=document.access_key,
            environment="pruebas",
            status="enviando",
        )
        db.add(submission)
        db.flush()

    # Si ya fue recibida, no reenviar innecesariamente.
    if submission.reception_status == "RECIBIDA":
        db.commit()
        db.refresh(submission)
        return serialize_submission(
            submission
        )

    try:
        result = send_to_reception(
            signed_xml=signature.signed_xml,
            environment=settings.environment,
        )
    except ValueError as exc:
        submission.status = "error_recepcion"
        db.commit()
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    submission.reception_status = (
        result.get("estado")
        or "SIN_RESPUESTA"
    )

    submission.reception_messages = json.dumps(
        result.get("mensajes", []),
        ensure_ascii=False,
    )

    submission.reception_raw = (
        result.get("raw")
    )

    if submission.reception_status == "RECIBIDA":
        submission.status = "recibida"
        submission.received_at = datetime.now(
            timezone.utc
        )
    else:
        submission.status = "devuelta"

    db.commit()
    db.refresh(submission)

    return serialize_submission(
        submission
    )


@router.post("/invoice/{invoice_id}/authorize")
def authorize_invoice_sri(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    invoice = get_owned_invoice(
        invoice_id,
        db,
        current_user,
    )

    settings = get_settings(
        db,
        current_user,
    )

    ensure_test_environment(
        settings
    )

    submission = (
        db.query(SriSubmission)
        .filter(
            SriSubmission.invoice_id == invoice.id,
            SriSubmission.workshop_id == current_user.workshop_id,
        )
        .first()
    )

    if not submission:
        raise HTTPException(
            status_code=400,
            detail="Primero debe enviar el XML al SRI",
        )

    if submission.reception_status != "RECIBIDA":
        raise HTTPException(
            status_code=400,
            detail=(
                "El comprobante todavía no tiene estado RECIBIDA. "
                "Revise los mensajes de recepción."
            ),
        )

    try:
        result = query_authorization(
            access_key=submission.access_key,
            environment=settings.environment,
        )
    except ValueError as exc:
        submission.status = "error_autorizacion"
        db.commit()
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    state = (
        result.get("estado")
        or "PPR"
    )

    submission.authorization_status = state
    submission.authorization_number = (
        result.get("numero_autorizacion")
    )
    submission.authorization_date = (
        result.get("fecha_autorizacion")
    )
    submission.authorization_environment = (
        result.get("ambiente")
    )
    submission.authorization_messages = json.dumps(
        result.get("mensajes", []),
        ensure_ascii=False,
    )
    submission.authorization_raw = (
        result.get("raw")
    )
    submission.authorized_xml = (
        result.get("comprobante")
    )

    normalized = state.strip().upper()

    if normalized in {
        "AUTORIZADO",
        "AUT",
    }:
        submission.status = "autorizada"
        submission.authorized_at = datetime.now(
            timezone.utc
        )

    elif normalized in {
        "NO AUTORIZADO",
        "NO_AUTORIZADO",
        "RECHAZADO",
        "NAT",
    }:
        submission.status = "no_autorizada"

    else:
        submission.status = "procesando"

    db.commit()
    db.refresh(submission)

    return serialize_submission(
        submission
    )


@router.get("/invoice/{invoice_id}")
def get_submission(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    invoice = get_owned_invoice(
        invoice_id,
        db,
        current_user,
    )

    submission = (
        db.query(SriSubmission)
        .filter(
            SriSubmission.invoice_id == invoice.id,
            SriSubmission.workshop_id == current_user.workshop_id,
        )
        .first()
    )

    if not submission:
        raise HTTPException(
            status_code=404,
            detail="Esta factura todavía no ha sido enviada al SRI",
        )

    return serialize_submission(
        submission
    )

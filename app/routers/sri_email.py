from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.security import get_current_user
from app.database import get_db
from app.models.invoice import Invoice
from app.models.sri_setting import SriSetting
from app.models.sri_submission import SriSubmission
from app.models.user import User
from app.models.workshop import Workshop
from app.services.email.invoice_email import (
    send_authorized_invoice_email,
)
from app.services.sri.ride_generator import (
    build_invoice_ride_pdf,
)


router = APIRouter(
    prefix="/sri-email",
    tags=["SRI Email"],
)


def _get_email_context(
    invoice_id: int,
    db: Session,
    current_user: User,
):
    invoice = (
        db.query(Invoice)
        .options(
            joinedload(Invoice.items)
        )
        .filter(
            Invoice.id == invoice_id,
            Invoice.workshop_id
            == current_user.workshop_id,
        )
        .first()
    )

    if not invoice:
        raise HTTPException(
            status_code=404,
            detail="Factura no encontrada",
        )

    workshop = (
        db.query(Workshop)
        .filter(
            Workshop.id
            == current_user.workshop_id,
        )
        .first()
    )

    if not workshop:
        raise HTTPException(
            status_code=404,
            detail="Taller no encontrado",
        )

    settings = (
        db.query(SriSetting)
        .filter(
            SriSetting.workshop_id
            == current_user.workshop_id,
        )
        .first()
    )

    if not settings:
        raise HTTPException(
            status_code=400,
            detail="No existe configuración SRI del taller",
        )

    submission = (
        db.query(SriSubmission)
        .filter(
            SriSubmission.invoice_id
            == invoice.id,
            SriSubmission.workshop_id
            == current_user.workshop_id,
        )
        .first()
    )

    if not submission:
        raise HTTPException(
            status_code=400,
            detail="La factura todavía no ha sido enviada al SRI",
        )

    return (
        invoice,
        workshop,
        settings,
        submission,
    )


@router.post(
    "/invoice/{invoice_id}/send"
)
def send_invoice_email(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
):
    """
    Sprint 3D.1.

    Envía o reenvía manualmente una factura ya AUTORIZADA.
    Este endpoint se usa primero para validar Resend de forma segura,
    antes de automatizar el correo dentro del flujo de emisión.
    """

    (
        invoice,
        workshop,
        settings,
        submission,
    ) = _get_email_context(
        invoice_id,
        db,
        current_user,
    )

    if not (
        invoice.client_email
        and invoice.client_email.strip()
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "La factura no tiene correo "
                "electrónico del cliente"
            ),
        )

    status = (
        submission.authorization_status
        or ""
    ).strip().upper()

    if status not in {
        "AUTORIZADO",
        "AUT",
    }:
        raise HTTPException(
            status_code=400,
            detail=(
                "Solo puede enviarse una factura "
                "autorizada por el SRI"
            ),
        )

    try:
        ride_pdf = build_invoice_ride_pdf(
            invoice=invoice,
            workshop=workshop,
            settings=settings,
            submission=submission,
        )

        result = send_authorized_invoice_email(
            invoice=invoice,
            workshop=workshop,
            submission=submission,
            ride_pdf=ride_pdf,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    return {
        "ok": True,
        "message": (
            "Factura enviada por correo "
            "correctamente"
        ),
        **result,
    }

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session, joinedload

from app.core.security import get_current_user
from app.database import get_db
from app.models.invoice import Invoice
from app.models.sri_setting import SriSetting
from app.models.sri_submission import SriSubmission
from app.models.user import User
from app.models.workshop import Workshop
from app.services.sri.ride_generator import build_invoice_ride_pdf


router = APIRouter(
    prefix="/sri-delivery",
    tags=["SRI Delivery"],
)


def _get_context(
    invoice_id: int,
    db: Session,
    current_user: User,
):
    invoice = (
        db.query(Invoice)
        .options(joinedload(Invoice.items))
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

    workshop = (
        db.query(Workshop)
        .filter(
            Workshop.id == current_user.workshop_id,
        )
        .first()
    )

    settings = (
        db.query(SriSetting)
        .filter(
            SriSetting.workshop_id == current_user.workshop_id,
        )
        .first()
    )

    submission = (
        db.query(SriSubmission)
        .filter(
            SriSubmission.invoice_id == invoice.id,
            SriSubmission.workshop_id == current_user.workshop_id,
        )
        .first()
    )

    if not workshop:
        raise HTTPException(
            status_code=404,
            detail="Taller no encontrado",
        )

    if not settings:
        raise HTTPException(
            status_code=400,
            detail="No existe configuración SRI del taller",
        )

    if not submission:
        raise HTTPException(
            status_code=400,
            detail="La factura todavía no ha sido enviada al SRI",
        )

    return invoice, workshop, settings, submission


@router.get("/invoice/{invoice_id}/ride")
def get_invoice_ride(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    invoice, workshop, settings, submission = _get_context(
        invoice_id,
        db,
        current_user,
    )

    try:
        pdf = build_invoice_ride_pdf(
            invoice=invoice,
            workshop=workshop,
            settings=settings,
            submission=submission,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    filename = f"RIDE_factura_{invoice.invoice_number}.pdf"

    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
        },
    )


@router.get("/invoice/{invoice_id}/authorized-xml")
def get_authorized_xml(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    invoice, _, _, submission = _get_context(
        invoice_id,
        db,
        current_user,
    )

    status = (
        submission.authorization_status
        or ""
    ).strip().upper()

    if status not in {"AUTORIZADO", "AUT"}:
        raise HTTPException(
            status_code=400,
            detail="La factura todavía no está autorizada por el SRI",
        )

    if not submission.authorized_xml:
        raise HTTPException(
            status_code=404,
            detail="El SRI no devolvió el XML autorizado",
        )

    filename = (
        f"factura_autorizada_"
        f"{invoice.invoice_number}_"
        f"{submission.authorization_number or submission.access_key}.xml"
    )

    return Response(
        content=submission.authorized_xml,
        media_type="application/xml",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
        },
    )

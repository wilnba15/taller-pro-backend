from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database import get_db
from app.models.user import User

from app.routers.sri_documents import (
    generate_invoice_electronic_document,
)
from app.routers.sri_signatures import (
    sign_invoice_xml,
)
from app.routers.sri_submissions import (
    authorize_invoice_sri,
    send_invoice_to_sri,
)


router = APIRouter(
    prefix="/sri-flow",
    tags=["SRI Flow"],
)


@router.post("/invoice/{invoice_id}/emit")
def emit_invoice_electronically(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Sprint 3C.

    Ejecuta el flujo técnico completo de una factura electrónica:
    1. Generar XML.
    2. Firmar XML con el certificado del taller.
    3. Enviar a recepción SRI.
    4. Consultar autorización.

    Los endpoints técnicos originales continúan disponibles para soporte
    y diagnóstico, pero el frontend comercial usa este único endpoint.
    """

    document = generate_invoice_electronic_document(
        invoice_id=invoice_id,
        db=db,
        current_user=current_user,
    )

    signature = sign_invoice_xml(
        invoice_id=invoice_id,
        db=db,
        current_user=current_user,
    )

    reception = send_invoice_to_sri(
        invoice_id=invoice_id,
        db=db,
        current_user=current_user,
    )

    if reception.get("reception_status") != "RECIBIDA":
        return {
            "ok": False,
            "stage": "recepcion",
            "status": "devuelta",
            "message": "El SRI devolvió el comprobante en recepción.",
            "document": document,
            "signature": signature,
            "submission": reception,
        }

    authorization = authorize_invoice_sri(
        invoice_id=invoice_id,
        db=db,
        current_user=current_user,
    )

    normalized = (
        authorization.get("authorization_status")
        or ""
    ).strip().upper()

    if normalized in {"AUTORIZADO", "AUT"}:
        return {
            "ok": True,
            "stage": "autorizacion",
            "status": "autorizada",
            "message": "Factura autorizada por el SRI.",
            "document": document,
            "signature": signature,
            "submission": authorization,
        }

    if normalized in {
        "NO AUTORIZADO",
        "NO_AUTORIZADO",
        "RECHAZADO",
        "NAT",
    }:
        return {
            "ok": False,
            "stage": "autorizacion",
            "status": "no_autorizada",
            "message": "El SRI no autorizó el comprobante.",
            "document": document,
            "signature": signature,
            "submission": authorization,
        }

    return {
        "ok": False,
        "stage": "autorizacion",
        "status": "procesando",
        "message": (
            "El comprobante fue recibido por el SRI y todavía "
            "se encuentra procesando."
        ),
        "document": document,
        "signature": signature,
        "submission": authorization,
    }

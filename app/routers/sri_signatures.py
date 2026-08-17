from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database import get_db
from app.models.electronic_document import ElectronicDocument
from app.models.electronic_signature import ElectronicSignature
from app.models.invoice import Invoice
from app.models.sri_certificate import SriCertificate
from app.models.user import User
from app.services.sri.certificate_vault import decrypt_bytes, decrypt_text
from app.services.sri.signer import (
    certificate_metadata,
    load_pkcs12_certificate,
    load_pkcs12_certificate_from_bytes,
    sign_xml_xades_bes,
)


router = APIRouter(
    prefix="/sri-signatures",
    tags=["SRI Signatures"],
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


def get_electronic_document(
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
            status_code=404,
            detail="Primero debe generar el XML SRI de la factura",
        )

    return document


def get_workshop_certificate(
    db: Session,
    current_user: User,
):
    stored = (
        db.query(SriCertificate)
        .filter(
            SriCertificate.workshop_id == current_user.workshop_id,
        )
        .first()
    )

    if stored:
        try:
            p12_bytes = decrypt_bytes(stored.encrypted_p12)
            password = decrypt_text(stored.encrypted_password)
        except ValueError as exc:
            raise HTTPException(
                status_code=500,
                detail=str(exc),
            ) from exc

        return {
            "source": "workshop",
            "stored": stored,
            "p12_bytes": p12_bytes,
            "password": password,
        }

    # Compatibilidad temporal con Sprint 2B:
    # mientras el taller todavía no haya cargado su propio certificado.
    return {
        "source": "legacy",
        "stored": None,
        "p12_bytes": None,
        "password": None,
    }


def serialize_signature(
    signature: ElectronicSignature,
) -> dict:
    return {
        "id": signature.id,
        "workshop_id": signature.workshop_id,
        "invoice_id": signature.invoice_id,
        "electronic_document_id": signature.electronic_document_id,
        "certificate_subject": signature.certificate_subject,
        "certificate_issuer": signature.certificate_issuer,
        "certificate_serial": signature.certificate_serial,
        "valid_from": signature.valid_from,
        "valid_to": signature.valid_to,
        "signature_algorithm": signature.signature_algorithm,
        "status": signature.status,
        "created_at": signature.created_at,
        "updated_at": signature.updated_at,
    }


@router.get("/certificate")
def get_certificate_info(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    certificate_source = get_workshop_certificate(
        db,
        current_user,
    )

    try:
        if certificate_source["source"] == "workshop":
            _, certificate, _ = load_pkcs12_certificate_from_bytes(
                certificate_source["p12_bytes"],
                certificate_source["password"],
            )
        else:
            _, certificate, _ = load_pkcs12_certificate()

        metadata = certificate_metadata(
            certificate
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return {
        "workshop_id": current_user.workshop_id,
        "configured": True,
        "source": certificate_source["source"],
        **metadata,
    }


@router.post("/invoice/{invoice_id}/sign")
def sign_invoice_xml(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    invoice = get_owned_invoice(
        invoice_id,
        db,
        current_user,
    )

    document = get_electronic_document(
        invoice_id,
        db,
        current_user,
    )

    existing = (
        db.query(ElectronicSignature)
        .filter(
            ElectronicSignature.invoice_id == invoice.id,
            ElectronicSignature.workshop_id == current_user.workshop_id,
        )
        .first()
    )

    if existing:
        return serialize_signature(
            existing
        )

    certificate_source = get_workshop_certificate(
        db,
        current_user,
    )

    try:
        if certificate_source["source"] == "workshop":
            signed_xml, metadata = sign_xml_xades_bes(
                document.xml_content,
                p12_bytes=certificate_source["p12_bytes"],
                p12_password=certificate_source["password"],
            )
        else:
            signed_xml, metadata = sign_xml_xades_bes(
                document.xml_content
            )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    signature = ElectronicSignature(
        workshop_id=current_user.workshop_id,
        invoice_id=invoice.id,
        electronic_document_id=document.id,
        certificate_subject=metadata["subject"],
        certificate_issuer=metadata["issuer"],
        certificate_serial=metadata["serial"],
        valid_from=metadata["valid_from"],
        valid_to=metadata["valid_to"],
        signature_algorithm=metadata["signature_algorithm"],
        signed_xml=signed_xml,
        status="firmado",
    )

    db.add(signature)
    document.status = "firmado"

    try:
        db.commit()
        db.refresh(signature)
    except Exception:
        db.rollback()
        raise

    return serialize_signature(
        signature
    )


@router.get("/invoice/{invoice_id}")
def get_invoice_signature(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_owned_invoice(
        invoice_id,
        db,
        current_user,
    )

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
            status_code=404,
            detail="El XML todavía no ha sido firmado",
        )

    return serialize_signature(
        signature
    )


@router.get("/invoice/{invoice_id}/xml")
def get_signed_invoice_xml(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    invoice = get_owned_invoice(
        invoice_id,
        db,
        current_user,
    )

    signature = (
        db.query(ElectronicSignature)
        .filter(
            ElectronicSignature.invoice_id == invoice.id,
            ElectronicSignature.workshop_id == current_user.workshop_id,
        )
        .first()
    )

    if not signature:
        raise HTTPException(
            status_code=404,
            detail="El XML todavía no ha sido firmado",
        )

    return Response(
        content=signature.signed_xml,
        media_type="application/xml",
        headers={
            "Content-Disposition": (
                f'inline; filename="factura_firmada_'
                f'{invoice.invoice_number}.xml"'
            )
        },
    )

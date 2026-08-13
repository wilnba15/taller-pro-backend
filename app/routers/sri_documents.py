from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session, joinedload

from app.core.security import get_current_user
from app.database import get_db
from app.models.electronic_document import ElectronicDocument
from app.models.invoice import Invoice
from app.models.sri_setting import SriSetting
from app.models.user import User
from app.models.workshop import Workshop
from app.services.sri.access_key import build_access_key, build_numeric_code
from app.services.sri.xml_generator import build_invoice_xml

router = APIRouter(prefix="/sri-documents", tags=["SRI Documents"])


def get_owned_invoice(invoice_id: int, db: Session, current_user: User) -> Invoice:
    invoice = (
        db.query(Invoice)
        .options(joinedload(Invoice.items))
        .filter(Invoice.id == invoice_id, Invoice.workshop_id == current_user.workshop_id)
        .first()
    )
    if not invoice:
        raise HTTPException(status_code=404, detail="Factura no encontrada")
    return invoice


def get_settings(db: Session, workshop_id: int) -> SriSetting:
    settings = db.query(SriSetting).filter(SriSetting.workshop_id == workshop_id).first()
    if not settings:
        raise HTTPException(
            status_code=400,
            detail="No existe configuración de facturación. Abra primero la configuración de facturación del taller.",
        )
    return settings


def serialize_document(document: ElectronicDocument) -> dict:
    return {
        "id": document.id,
        "workshop_id": document.workshop_id,
        "invoice_id": document.invoice_id,
        "document_type": document.document_type,
        "xml_version": document.xml_version,
        "environment": document.environment,
        "numeric_code": document.numeric_code,
        "access_key": document.access_key,
        "status": document.status,
        "created_at": document.created_at,
        "updated_at": document.updated_at,
    }


@router.post("/invoice/{invoice_id}/generate")
def generate_invoice_electronic_document(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    invoice = get_owned_invoice(invoice_id, db, current_user)

    existing = (
        db.query(ElectronicDocument)
        .filter(
            ElectronicDocument.workshop_id == current_user.workshop_id,
            ElectronicDocument.invoice_id == invoice.id,
        )
        .first()
    )
    if existing:
        return serialize_document(existing)

    workshop = db.query(Workshop).filter(Workshop.id == current_user.workshop_id).first()
    if not workshop:
        raise HTTPException(status_code=404, detail="Taller no encontrado")
    if not workshop.ruc:
        raise HTTPException(status_code=400, detail="El taller debe tener RUC registrado")

    settings = get_settings(db, current_user.workshop_id)
    numeric_code = build_numeric_code(
        ruc=workshop.ruc,
        invoice_number=invoice.invoice_number,
        issue_date=invoice.issue_date,
    )

    try:
        access_key = build_access_key(
            issue_date=invoice.issue_date,
            ruc=workshop.ruc,
            environment=settings.environment,
            establishment_code=invoice.establishment_code,
            emission_point_code=invoice.emission_point_code,
            sequential=invoice.sequential,
            numeric_code=numeric_code,
        )
        xml_content = build_invoice_xml(
            invoice=invoice,
            workshop=workshop,
            settings=settings,
            access_key=access_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    document = ElectronicDocument(
        workshop_id=current_user.workshop_id,
        invoice_id=invoice.id,
        document_type="01",
        xml_version="2.1.0",
        environment=settings.environment,
        numeric_code=numeric_code,
        access_key=access_key,
        xml_content=xml_content,
        status="generado",
    )
    db.add(document)

    try:
        db.commit()
        db.refresh(document)
    except Exception:
        db.rollback()
        raise

    return serialize_document(document)


@router.get("/invoice/{invoice_id}")
def get_invoice_electronic_document(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_owned_invoice(invoice_id, db, current_user)
    document = (
        db.query(ElectronicDocument)
        .filter(
            ElectronicDocument.workshop_id == current_user.workshop_id,
            ElectronicDocument.invoice_id == invoice_id,
        )
        .first()
    )
    if not document:
        raise HTTPException(status_code=404, detail="Documento electrónico todavía no generado")
    return serialize_document(document)


@router.get("/invoice/{invoice_id}/xml")
def download_invoice_xml(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    invoice = get_owned_invoice(invoice_id, db, current_user)
    document = (
        db.query(ElectronicDocument)
        .filter(
            ElectronicDocument.workshop_id == current_user.workshop_id,
            ElectronicDocument.invoice_id == invoice.id,
        )
        .first()
    )
    if not document:
        raise HTTPException(status_code=404, detail="Documento electrónico todavía no generado")

    filename = f"factura_{invoice.invoice_number}_{document.access_key}.xml"
    return Response(
        content=document.xml_content,
        media_type="application/xml",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )

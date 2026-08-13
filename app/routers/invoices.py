from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session, joinedload

from app.core.security import get_current_user
from app.database import get_db

from app.models.client import Client
from app.models.invoice import Invoice
from app.models.invoice_item import InvoiceItem
from app.models.sri_setting import SriSetting
from app.models.user import User
from app.models.work_order import WorkOrder
from app.models.work_order_item import WorkOrderItem
from app.models.workshop import Workshop

from app.schemas.invoice import (
    InvoiceResponse,
    SriSettingResponse,
)

from app.services.billing.calculations import (
    calculate_invoice_item,
    money,
)


router = APIRouter(
    prefix="/invoices",
    tags=["Invoices"],
)


def get_owned_work_order(
    work_order_id: int,
    db: Session,
    current_user: User,
) -> WorkOrder:
    work_order = (
        db.query(WorkOrder)
        .filter(
            WorkOrder.id == work_order_id,
            WorkOrder.workshop_id == current_user.workshop_id,
        )
        .first()
    )

    if not work_order:
        raise HTTPException(
            status_code=404,
            detail="Orden de trabajo no encontrada",
        )

    return work_order


def get_or_create_sri_settings(
    db: Session,
    workshop_id: int,
) -> SriSetting:
    settings = (
        db.query(SriSetting)
        .filter(
            SriSetting.workshop_id == workshop_id,
        )
        .first()
    )

    if settings:
        return settings

    settings = SriSetting(
        workshop_id=workshop_id,
        environment="pruebas",
        establishment_code="001",
        emission_point_code="001",
        invoice_sequence=1,
        default_tax_rate=Decimal("15.00"),
        accounting_required=False,
    )

    db.add(settings)
    db.flush()

    return settings


def serialize_invoice(invoice: Invoice) -> dict:
    return {
        "id": invoice.id,
        "workshop_id": invoice.workshop_id,
        "work_order_id": invoice.work_order_id,
        "client_id": invoice.client_id,

        "establishment_code": invoice.establishment_code,
        "emission_point_code": invoice.emission_point_code,
        "sequential": invoice.sequential,

        "invoice_number": invoice.invoice_number,
        "issue_date": invoice.issue_date,

        "client_name": invoice.client_name,
        "client_identification": invoice.client_identification,
        "client_email": invoice.client_email,
        "client_address": invoice.client_address,

        "subtotal_0": invoice.subtotal_0,
        "subtotal_taxed": invoice.subtotal_taxed,
        "tax_amount": invoice.tax_amount,
        "discount": invoice.discount,
        "total": invoice.total,

        "status": invoice.status,

        "created_at": invoice.created_at,
        "updated_at": invoice.updated_at,

        "items": invoice.items,
    }


@router.get(
    "/settings",
    response_model=SriSettingResponse,
)
def get_billing_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    settings = get_or_create_sri_settings(
        db,
        current_user.workshop_id,
    )

    db.commit()
    db.refresh(settings)

    return settings


@router.put(
    "/settings",
    response_model=SriSettingResponse,
)
def update_billing_settings(
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    settings = get_or_create_sri_settings(
        db,
        current_user.workshop_id,
    )

    establishment_code = str(
        data.get(
            "establishment_code",
            settings.establishment_code,
        )
    ).zfill(3)

    emission_point_code = str(
        data.get(
            "emission_point_code",
            settings.emission_point_code,
        )
    ).zfill(3)

    if len(establishment_code) != 3:
        raise HTTPException(
            status_code=400,
            detail="El código de establecimiento debe tener 3 dígitos",
        )

    if len(emission_point_code) != 3:
        raise HTTPException(
            status_code=400,
            detail="El punto de emisión debe tener 3 dígitos",
        )

    settings.establishment_code = establishment_code
    settings.emission_point_code = emission_point_code

    if "default_tax_rate" in data:
        settings.default_tax_rate = Decimal(
            str(data["default_tax_rate"])
        )

    if "accounting_required" in data:
        settings.accounting_required = bool(
            data["accounting_required"]
        )

    if "special_taxpayer_code" in data:
        settings.special_taxpayer_code = (
            data["special_taxpayer_code"] or None
        )

    if "rimpe_type" in data:
        settings.rimpe_type = (
            data["rimpe_type"] or None
        )

    db.commit()
    db.refresh(settings)

    return settings


@router.post(
    "/from-work-order/{work_order_id}",
    response_model=InvoiceResponse,
    status_code=201,
)
def create_invoice_from_work_order(
    work_order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    work_order = get_owned_work_order(
        work_order_id,
        db,
        current_user,
    )

    existing_invoice = (
        db.query(Invoice)
        .options(joinedload(Invoice.items))
        .filter(
            Invoice.workshop_id == current_user.workshop_id,
            Invoice.work_order_id == work_order.id,
        )
        .first()
    )

    if existing_invoice:
        return existing_invoice

    workshop = (
        db.query(Workshop)
        .filter(
            Workshop.id == current_user.workshop_id,
        )
        .first()
    )

    if not workshop:
        raise HTTPException(
            status_code=404,
            detail="Taller no encontrado",
        )

    if not workshop.ruc:
        raise HTTPException(
            status_code=400,
            detail="El taller debe tener RUC registrado antes de facturar",
        )

    client = (
        db.query(Client)
        .filter(
            Client.id == work_order.client_id,
            Client.workshop_id == current_user.workshop_id,
        )
        .first()
    )

    if not client:
        raise HTTPException(
            status_code=404,
            detail="Cliente no encontrado",
        )

    if not client.identification:
        raise HTTPException(
            status_code=400,
            detail="El cliente debe tener identificación registrada",
        )

    work_order_items = (
        db.query(WorkOrderItem)
        .filter(
            WorkOrderItem.work_order_id == work_order.id,
        )
        .order_by(
            WorkOrderItem.id.asc(),
        )
        .all()
    )

    if not work_order_items:
        raise HTTPException(
            status_code=400,
            detail="La orden no tiene ítems para facturar",
        )

    # Bloqueo por taller para evitar números repetidos.
    db.execute(
        text(
            "SELECT pg_advisory_xact_lock(:workshop_id)"
        ),
        {
            "workshop_id": current_user.workshop_id,
        },
    )

    settings = get_or_create_sri_settings(
        db,
        current_user.workshop_id,
    )

    sequential = int(
        settings.invoice_sequence or 1
    )

    establishment = str(
        settings.establishment_code
    ).zfill(3)

    emission_point = str(
        settings.emission_point_code
    ).zfill(3)

    sequential_text = str(
        sequential
    ).zfill(9)

    invoice_number = (
        f"{establishment}-"
        f"{emission_point}-"
        f"{sequential_text}"
    )

    invoice = Invoice(
        workshop_id=current_user.workshop_id,
        work_order_id=work_order.id,
        client_id=client.id,

        establishment_code=establishment,
        emission_point_code=emission_point,
        sequential=sequential,

        invoice_number=invoice_number,
        issue_date=date.today(),

        client_name=client.full_name,
        client_identification=client.identification,
        client_email=client.email,
        client_address=client.address,

        subtotal_0=Decimal("0.00"),
        subtotal_taxed=Decimal("0.00"),
        tax_amount=Decimal("0.00"),
        discount=Decimal("0.00"),
        total=Decimal("0.00"),

        status="borrador",
    )

    db.add(invoice)
    db.flush()

    subtotal_taxed = Decimal("0.00")
    subtotal_zero = Decimal("0.00")
    total_tax = Decimal("0.00")
    total_discount = Decimal("0.00")
    grand_total = Decimal("0.00")

    tax_rate = Decimal(
        str(settings.default_tax_rate or 0)
    )

    for work_item in work_order_items:
        calculation = calculate_invoice_item(
            quantity=work_item.quantity,
            unit_price=work_item.unit_price,
            tax_rate=tax_rate,
            discount=0,
        )

        invoice_item = InvoiceItem(
            invoice_id=invoice.id,
            item_type=work_item.item_type,
            description=work_item.description,
            quantity=calculation["quantity"],
            unit_price=calculation["unit_price"],
            discount=calculation["discount"],
            subtotal=calculation["subtotal"],
            tax_rate=calculation["tax_rate"],
            tax_amount=calculation["tax_amount"],
            total=calculation["total"],
        )

        db.add(invoice_item)

        if tax_rate > 0:
            subtotal_taxed += calculation["subtotal"]
        else:
            subtotal_zero += calculation["subtotal"]

        total_tax += calculation["tax_amount"]
        total_discount += calculation["discount"]
        grand_total += calculation["total"]

    invoice.subtotal_0 = money(
        subtotal_zero
    )

    invoice.subtotal_taxed = money(
        subtotal_taxed
    )

    invoice.tax_amount = money(
        total_tax
    )

    invoice.discount = money(
        total_discount
    )

    invoice.total = money(
        grand_total
    )

    # El siguiente número queda preparado.
    settings.invoice_sequence = sequential + 1

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    invoice = (
        db.query(Invoice)
        .options(joinedload(Invoice.items))
        .filter(
            Invoice.id == invoice.id,
        )
        .first()
    )

    return invoice


@router.get(
    "/",
    response_model=list[InvoiceResponse],
)
def list_invoices(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    invoices = (
        db.query(Invoice)
        .options(joinedload(Invoice.items))
        .filter(
            Invoice.workshop_id == current_user.workshop_id,
        )
        .order_by(
            Invoice.id.desc(),
        )
        .all()
    )

    return invoices


@router.get(
    "/{invoice_id}",
    response_model=InvoiceResponse,
)
def get_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
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

    return invoice
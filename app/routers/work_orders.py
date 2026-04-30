from decimal import Decimal
from io import BytesIO
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from app.database import get_db
from app.models.work_order import WorkOrder
from app.models.client import Client
from app.models.vehicle import Vehicle
from app.models.workshop import Workshop
from app.models.work_order_item import WorkOrderItem
from app.schemas.work_order import WorkOrderCreate, WorkOrderUpdate, WorkOrderResponse

router = APIRouter(prefix="/work-orders", tags=["Work Orders"])


def money(value) -> str:
    try:
        return f"${Decimal(value or 0):.2f}"
    except Exception:
        return "$0.00"


def safe(value, fallback="-") -> str:
    return str(value) if value not in [None, ""] else fallback


@router.post("/", response_model=WorkOrderResponse)
def create_work_order(work_order: WorkOrderCreate, db: Session = Depends(get_db)):
    workshop = db.query(Workshop).filter(Workshop.id == work_order.workshop_id).first()
    if not workshop:
        raise HTTPException(status_code=404, detail="Taller no encontrado")

    client = db.query(Client).filter(Client.id == work_order.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    vehicle = db.query(Vehicle).filter(Vehicle.id == work_order.vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehículo no encontrado")

    if client.workshop_id != work_order.workshop_id:
        raise HTTPException(status_code=400, detail="El cliente no pertenece al taller seleccionado")

    if vehicle.workshop_id != work_order.workshop_id:
        raise HTTPException(status_code=400, detail="El vehículo no pertenece al taller seleccionado")

    if vehicle.client_id != client.id:
        raise HTTPException(status_code=400, detail="El vehículo no pertenece al cliente seleccionado")

    total = Decimal(work_order.labor_cost) + Decimal(work_order.parts_cost)

    db_work_order = WorkOrder(
        **work_order.model_dump(),
        total=total
    )
    db.add(db_work_order)
    db.commit()
    db.refresh(db_work_order)
    return db_work_order


@router.get("/", response_model=list[WorkOrderResponse])
def list_work_orders(db: Session = Depends(get_db)):
    return db.query(WorkOrder).order_by(WorkOrder.id.desc()).all()


@router.get("/{work_order_id}/invoice-pdf")
def generate_invoice_pdf(work_order_id: int, db: Session = Depends(get_db)):
    work_order = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not work_order:
        raise HTTPException(status_code=404, detail="Orden de trabajo no encontrada")

    client = db.query(Client).filter(Client.id == work_order.client_id).first()
    vehicle = db.query(Vehicle).filter(Vehicle.id == work_order.vehicle_id).first()
    workshop = db.query(Workshop).filter(Workshop.id == work_order.workshop_id).first()
    items = (
        db.query(WorkOrderItem)
        .filter(WorkOrderItem.work_order_id == work_order_id)
        .order_by(WorkOrderItem.id.asc())
        .all()
    )

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )

    styles = getSampleStyleSheet()
    title_style = styles["Title"]
    normal = styles["Normal"]
    heading = styles["Heading2"]

    story = []

    workshop_name = safe(getattr(workshop, "name", None), "SIADAUTO / Taller PRO")
    story.append(Paragraph(workshop_name, title_style))
    story.append(Paragraph("Factura / Orden de Trabajo", heading))
    story.append(Spacer(1, 0.25 * cm))

    header_data = [
        ["Factura / OT No.", f"#{work_order.id}", "Fecha emisión", datetime.now().strftime("%Y-%m-%d %H:%M")],
        ["Fecha ingreso", safe(work_order.entry_date), "Estado", safe(work_order.status).replace("_", " ").title()],
    ]

    header_table = Table(header_data, colWidths=[3.2 * cm, 5 * cm, 3.2 * cm, 5 * cm])
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F3F4F6")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 0.35 * cm))

    client_data = [
        ["Cliente", safe(getattr(client, "full_name", None)), "Teléfono", safe(getattr(client, "phone", None))],
        ["Identificación", safe(getattr(client, "identification", None)), "Email", safe(getattr(client, "email", None))],
        [
            "Vehículo",
            f"{safe(getattr(vehicle, 'brand', None), '')} {safe(getattr(vehicle, 'model', None), '')}".strip() or "-",
            "Placa",
            safe(getattr(vehicle, "plate", None)),
        ],
        ["Año", safe(getattr(vehicle, "year", None)), "Kilometraje", safe(getattr(vehicle, "mileage", None))],
    ]

    client_table = Table(client_data, colWidths=[3.2 * cm, 5 * cm, 3.2 * cm, 5 * cm])
    client_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(client_table)
    story.append(Spacer(1, 0.45 * cm))

    story.append(Paragraph("Detalle de repuestos y mano de obra", heading))

    item_rows = [["Tipo", "Descripción", "Cant.", "V. Unitario", "Subtotal"]]
    for item in items:
        item_type = "Mano de obra" if item.item_type == "mano_obra" else "Repuesto"
        item_rows.append([
            item_type,
            safe(item.description),
            f"{Decimal(item.quantity or 0):.2f}",
            money(item.unit_price),
            money(item.subtotal),
        ])

    if len(item_rows) == 1:
        item_rows.append(["-", "Sin ítems registrados", "0", "$0.00", "$0.00"])

    items_table = Table(item_rows, colWidths=[3.2 * cm, 6.5 * cm, 2 * cm, 3 * cm, 3 * cm])
    items_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING", (0, 0), (-1, -1), 7),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 0.35 * cm))

    totals_data = [
        ["Mano de obra", money(work_order.labor_cost)],
        ["Repuestos", money(work_order.parts_cost)],
        ["TOTAL", money(work_order.total)],
    ]
    totals_table = Table(totals_data, colWidths=[5 * cm, 4 * cm], hAlign="RIGHT")
    totals_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"),
        ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#DBEAFE")),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(totals_table)
    story.append(Spacer(1, 0.45 * cm))

    if work_order.issue_description:
        story.append(Paragraph("Problema reportado", heading))
        story.append(Paragraph(safe(work_order.issue_description), normal))
        story.append(Spacer(1, 0.25 * cm))

    if work_order.diagnosis:
        story.append(Paragraph("Diagnóstico", heading))
        story.append(Paragraph(safe(work_order.diagnosis), normal))
        story.append(Spacer(1, 0.25 * cm))

    if work_order.work_performed:
        story.append(Paragraph("Trabajo realizado", heading))
        story.append(Paragraph(safe(work_order.work_performed), normal))
        story.append(Spacer(1, 0.25 * cm))

    if work_order.notes:
        story.append(Paragraph("Notas", heading))
        story.append(Paragraph(safe(work_order.notes), normal))
        story.append(Spacer(1, 0.25 * cm))

    story.append(Spacer(1, 1 * cm))
    signatures = Table(
        [
            ["____________________________", "____________________________"],
            ["Firma taller", "Firma cliente"],
        ],
        colWidths=[8 * cm, 8 * cm],
    )
    signatures.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(signatures)

    doc.build(story)
    buffer.seek(0)

    filename = f"factura_orden_{work_order.id}.pdf"
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.get("/{work_order_id}", response_model=WorkOrderResponse)
def get_work_order(work_order_id: int, db: Session = Depends(get_db)):
    work_order = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not work_order:
        raise HTTPException(status_code=404, detail="Orden de trabajo no encontrada")
    return work_order


@router.put("/{work_order_id}", response_model=WorkOrderResponse)
def update_work_order(work_order_id: int, data: WorkOrderUpdate, db: Session = Depends(get_db)):
    work_order = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not work_order:
        raise HTTPException(status_code=404, detail="Orden de trabajo no encontrada")

    workshop = db.query(Workshop).filter(Workshop.id == data.workshop_id).first()
    if not workshop:
        raise HTTPException(status_code=404, detail="Taller no encontrado")

    client = db.query(Client).filter(Client.id == data.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    vehicle = db.query(Vehicle).filter(Vehicle.id == data.vehicle_id).first()
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehículo no encontrado")

    if client.workshop_id != data.workshop_id:
        raise HTTPException(status_code=400, detail="El cliente no pertenece al taller seleccionado")

    if vehicle.workshop_id != data.workshop_id:
        raise HTTPException(status_code=400, detail="El vehículo no pertenece al taller seleccionado")

    if vehicle.client_id != client.id:
        raise HTTPException(status_code=400, detail="El vehículo no pertenece al cliente seleccionado")

    for key, value in data.model_dump().items():
        setattr(work_order, key, value)

    work_order.total = Decimal(data.labor_cost) + Decimal(data.parts_cost)

    db.commit()
    db.refresh(work_order)
    return work_order


@router.delete("/{work_order_id}")
def delete_work_order(work_order_id: int, db: Session = Depends(get_db)):
    work_order = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not work_order:
        raise HTTPException(status_code=404, detail="Orden de trabajo no encontrada")

    db.delete(work_order)
    db.commit()
    return {"message": "Orden de trabajo eliminada correctamente"}

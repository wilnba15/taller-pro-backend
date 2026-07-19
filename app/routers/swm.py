from typing import Optional
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Response
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.swm import (
    SwmAiQuery,
    SwmFuelRecord,
    SwmMaintenanceSchedule,
    SwmServiceOrder,
    SwmServiceRecord,
    SwmVehicle,
)
from app.models.swm_user import SwmUser
from app.routers.swm_auth import get_current_swm_user
from app.schemas.swm import (
    SwmAiQueryCreate,
    SwmAiQueryResponse,
    SwmDashboardResponse,
    SwmFuelRecordCreate,
    SwmFuelRecordResponse,
    SwmFuelRecordUpdate,
    SwmMaintenanceResponse,
    SwmServiceOrderCreate,
    SwmServiceOrderResponse,
    SwmServiceRecordCreate,
    SwmServiceRecordResponse,
    SwmVehicleCreate,
    SwmVehicleResponse,
    SwmVehicleUpdate,
)

router = APIRouter(prefix="/swm", tags=["SWM Care"])


def apply_swm_defaults(payload: SwmVehicleCreate) -> dict:
    data = payload.model_dump()
    model = (data.get("model") or "").strip().upper()

    if model == "G01":
        data["model"] = "G01"
        data["engine"] = data.get("engine") or "1.5 Turbo"
        data["transmission"] = data.get("transmission") or "Manual"
        data["fuel_type"] = data.get("fuel_type") or "Gasolina"
    elif model == "G03":
        data["model"] = "G03"
        data["engine"] = data.get("engine") or "1.5 Turbo"
        data["transmission"] = data.get("transmission") or "Manual"
        data["fuel_type"] = data.get("fuel_type") or "Gasolina"
    elif model == "G05":
        data["model"] = "G05"
        data["engine"] = data.get("engine") or "1.5 Turbo"
        data["transmission"] = data.get("transmission") or "Automática"
        data["fuel_type"] = data.get("fuel_type") or "Gasolina"

    return data


def user_owns_vehicle_or_404(
    vehicle_id: int,
    current_user: SwmUser,
    db: Session,
) -> SwmVehicle:
    vehicle = (
        db.query(SwmVehicle)
        .filter(
            SwmVehicle.id == vehicle_id,
            or_(
                SwmVehicle.user_id == current_user.id,
                SwmVehicle.user_id.is_(None),
            ),
        )
        .first()
    )

    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehículo no encontrado.")

    if vehicle.user_id is None:
        vehicle.user_id = current_user.id
        db.commit()
        db.refresh(vehicle)

    return vehicle



def fuel_record_or_404(
    fuel_record_id: int,
    current_user: SwmUser,
    db: Session,
) -> SwmFuelRecord:
    fuel_record = (
        db.query(SwmFuelRecord)
        .join(SwmVehicle, SwmFuelRecord.vehicle_id == SwmVehicle.id)
        .filter(
            SwmFuelRecord.id == fuel_record_id,
            SwmVehicle.user_id == current_user.id,
        )
        .first()
    )

    if not fuel_record:
        raise HTTPException(
            status_code=404,
            detail="Registro de combustible no encontrado.",
        )

    return fuel_record

def get_next_maintenance_mileage(current_mileage: int, db: Session) -> Optional[int]:
    next_schedule = (
        db.query(SwmMaintenanceSchedule.mileage)
        .filter(SwmMaintenanceSchedule.mileage >= current_mileage)
        .order_by(SwmMaintenanceSchedule.mileage.asc())
        .first()
    )
    return next_schedule[0] if next_schedule else None


def get_current_maintenance_mileage(current_mileage: int, db: Session) -> Optional[int]:
    current_schedule = (
        db.query(SwmMaintenanceSchedule.mileage)
        .filter(SwmMaintenanceSchedule.mileage <= current_mileage)
        .order_by(SwmMaintenanceSchedule.mileage.desc())
        .first()
    )
    return current_schedule[0] if current_schedule else None


def get_target_maintenance_mileage(
    vehicle_id: int,
    current_mileage: int,
    db: Session,
) -> Optional[int]:
    next_maintenance = get_next_maintenance_mileage(current_mileage, db)

    if next_maintenance is not None:
        return next_maintenance

    return get_current_maintenance_mileage(current_mileage, db)


def get_schedule_items(mileage: int, db: Session) -> list[SwmMaintenanceSchedule]:
    return (
        db.query(SwmMaintenanceSchedule)
        .filter(SwmMaintenanceSchedule.mileage == mileage)
        .order_by(
            SwmMaintenanceSchedule.category.asc(),
            SwmMaintenanceSchedule.item_name.asc(),
        )
        .all()
    )


def get_completed_schedule_ids(vehicle_id: int, mileage: int, db: Session) -> set[int]:
    return {
        record.schedule_id
        for record in db.query(SwmServiceRecord)
        .filter(
            SwmServiceRecord.vehicle_id == vehicle_id,
            SwmServiceRecord.service_mileage == mileage,
        )
        .all()
        if record.schedule_id is not None
    }


def get_maintenance_summary(
    vehicle_id: int,
    mileage: int,
    db: Session,
) -> tuple[list[SwmMaintenanceSchedule], set[int], int, int, int]:
    schedule_items = get_schedule_items(mileage, db)
    completed_schedule_ids = get_completed_schedule_ids(vehicle_id, mileage, db)

    completed_items = sum(
        1 for item in schedule_items if item.id in completed_schedule_ids
    )
    total_items = len(schedule_items)
    pending_items = max(0, total_items - completed_items)

    return (
        schedule_items,
        completed_schedule_ids,
        completed_items,
        total_items,
        pending_items,
    )


def format_money(value) -> str:
    try:
        return f"$ {float(value):,.2f}"
    except Exception:
        return "$ 0.00"


def build_maintenance_pdf(
    vehicle: SwmVehicle,
    mileage: int,
    records: list[SwmServiceRecord],
) -> bytes:
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    margin_x = 1.8 * cm
    y = height - 1.8 * cm

    total_cost = sum(float(record.cost or 0) for record in records)
    workshops = sorted({record.workshop for record in records if record.workshop})
    service_date = records[0].service_date if records else ""

    pdf.setFillColor(colors.HexColor("#0f172a"))
    pdf.rect(0, height - 4.4 * cm, width, 4.4 * cm, fill=1, stroke=0)

    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 24)
    pdf.drawString(margin_x, y, "SWM Care")
    pdf.setFont("Helvetica", 11)
    pdf.drawString(margin_x, y - 0.7 * cm, "Expediente tecnico tipo concesionario")
    pdf.drawString(margin_x, y - 1.25 * cm, "Reporte integral de mantenimiento")

    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawRightString(width - margin_x, y, f"MTTO {mileage:,} km".replace(",", "."))
    pdf.setFont("Helvetica", 9)
    pdf.drawRightString(width - margin_x, y - 0.65 * cm, "Historial en linea")
    pdf.setStrokeColor(colors.white)
    pdf.rect(width - margin_x - 2.2 * cm, y - 3.0 * cm, 2.2 * cm, 2.2 * cm, stroke=1, fill=0)
    pdf.setFont("Helvetica", 7)
    pdf.drawCentredString(width - margin_x - 1.1 * cm, y - 1.95 * cm, "QR")
    pdf.drawCentredString(width - margin_x - 1.1 * cm, y - 2.25 * cm, "Proximamente")

    y = height - 5.2 * cm

    pdf.setFillColor(colors.HexColor("#111827"))
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(margin_x, y, "Datos del vehiculo")
    y -= 0.65 * cm

    pdf.setFillColor(colors.black)
    vehicle_rows = [
        ("Vehiculo", f"SWM {vehicle.model} {vehicle.engine or ''}".strip()),
        ("Año", str(vehicle.year)),
        ("Placa", vehicle.plate or "Sin placa"),
        ("VIN / Chasis", vehicle.vin or "Sin dato"),
        ("Color", vehicle.color or "Sin dato"),
        ("Kilometraje actual", f"{vehicle.current_mileage:,} km".replace(",", ".")),
    ]

    for label, value in vehicle_rows:
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawString(margin_x, y, f"{label}:")
        pdf.setFont("Helvetica", 9)
        pdf.drawString(margin_x + 3.8 * cm, y, value)
        y -= 0.45 * cm

    y -= 0.25 * cm
    pdf.setFillColor(colors.HexColor("#111827"))
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(margin_x, y, "Resumen del mantenimiento")
    y -= 0.65 * cm

    summary_rows = [
        ("Mantenimiento", f"{mileage:,} km".replace(",", ".")),
        ("Fecha", str(service_date) if service_date else "Sin fecha"),
        ("Taller(es)", ", ".join(workshops) if workshops else "Sin taller registrado"),
        ("Items realizados", str(len(records))),
        ("Costo total", format_money(total_cost)),
    ]

    pdf.setFillColor(colors.black)
    for label, value in summary_rows:
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawString(margin_x, y, f"{label}:")
        pdf.setFont("Helvetica", 9)
        pdf.drawString(margin_x + 4.2 * cm, y, value[:80])
        y -= 0.45 * cm

    y -= 0.25 * cm
    pdf.setFillColor(colors.HexColor("#111827"))
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(margin_x, y, "Checklist de trabajos realizados")
    y -= 0.65 * cm

    pdf.setFillColor(colors.HexColor("#e5e7eb"))
    pdf.rect(margin_x, y - 0.2 * cm, width - 3.6 * cm, 0.62 * cm, fill=1, stroke=0)
    pdf.setFillColor(colors.black)
    pdf.setFont("Helvetica-Bold", 8.5)
    pdf.drawString(margin_x + 0.2 * cm, y, "Item")
    pdf.drawString(margin_x + 7.6 * cm, y, "Categoria")
    pdf.drawString(margin_x + 11.2 * cm, y, "Taller")
    pdf.drawString(margin_x + 15.0 * cm, y, "Costo")
    y -= 0.62 * cm

    pdf.setFont("Helvetica", 8.2)

    if not records:
        pdf.drawString(margin_x + 0.2 * cm, y, "No hay items registrados para este mantenimiento.")
        y -= 0.48 * cm

    for record in records:
        if y < 3.6 * cm:
            pdf.showPage()
            y = height - 2 * cm

        item_name = record.schedule.item_name if record.schedule else "Servicio registrado"
        category = record.schedule.category if record.schedule else "General"
        workshop = record.workshop or "Sin taller"

        pdf.drawString(margin_x + 0.2 * cm, y, item_name[:42])
        pdf.drawString(margin_x + 7.6 * cm, y, (category or "General")[:20])
        pdf.drawString(margin_x + 11.2 * cm, y, workshop[:22])
        pdf.drawString(margin_x + 15.0 * cm, y, format_money(record.cost))
        y -= 0.45 * cm

    y -= 0.35 * cm
    pdf.setStrokeColor(colors.HexColor("#94a3b8"))
    pdf.line(margin_x, y, width - margin_x, y)
    y -= 0.6 * cm

    pdf.setFillColor(colors.HexColor("#111827"))
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(margin_x, y, "Observaciones generales")
    y -= 0.5 * cm

    pdf.setFillColor(colors.black)
    pdf.setFont("Helvetica", 8.5)
    notes = " | ".join([record.notes for record in records if record.notes]) or "Sin observaciones registradas."

    for line in [notes[i:i+105] for i in range(0, min(len(notes), 420), 105)]:
        pdf.drawString(margin_x, y, line)
        y -= 0.4 * cm

    pdf.setFillColor(colors.HexColor("#64748b"))
    pdf.setFont("Helvetica", 8)
    pdf.drawString(margin_x, 1.2 * cm, "Generado automaticamente por SWM Care.")
    pdf.drawRightString(width - margin_x, 1.2 * cm, "Expediente tecnico del vehiculo")

    pdf.save()
    buffer.seek(0)
    return buffer.getvalue()


@router.get("/vehicles", response_model=list[SwmVehicleResponse])
def list_vehicles(
    db: Session = Depends(get_db),
    current_user: SwmUser = Depends(get_current_swm_user),
):
    return (
        db.query(SwmVehicle)
        .filter(SwmVehicle.user_id == current_user.id)
        .order_by(SwmVehicle.id.desc())
        .all()
    )


@router.get("/vehicles/{vehicle_id}", response_model=SwmVehicleResponse)
def get_vehicle(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: SwmUser = Depends(get_current_swm_user),
):
    return user_owns_vehicle_or_404(vehicle_id, current_user, db)


@router.post("/vehicles", response_model=SwmVehicleResponse, status_code=201)
def create_vehicle(
    payload: SwmVehicleCreate,
    db: Session = Depends(get_db),
    current_user: SwmUser = Depends(get_current_swm_user),
):
    vehicle_data = apply_swm_defaults(payload)
    vehicle = SwmVehicle(**vehicle_data, user_id=current_user.id)
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return vehicle


@router.put("/vehicles/{vehicle_id}", response_model=SwmVehicleResponse)
def update_vehicle(
    vehicle_id: int,
    payload: SwmVehicleUpdate,
    db: Session = Depends(get_db),
    current_user: SwmUser = Depends(get_current_swm_user),
):
    vehicle = user_owns_vehicle_or_404(vehicle_id, current_user, db)
    update_data = payload.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(vehicle, field, value)

    db.commit()
    db.refresh(vehicle)
    return vehicle


@router.get("/vehicles/{vehicle_id}/dashboard", response_model=SwmDashboardResponse)
def get_dashboard(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: SwmUser = Depends(get_current_swm_user),
):
    vehicle = user_owns_vehicle_or_404(vehicle_id, current_user, db)

    target_mileage = get_target_maintenance_mileage(vehicle_id, vehicle.current_mileage, db)

    if target_mileage is None:
        return {
            "vehicle": vehicle,
            "next_maintenance_mileage": None,
            "kilometers_remaining": None,
            "pending_items": 0,
            "completed_items": 0,
            "total_items": 0,
            "general_status": "Sin calendario registrado",
        }

    (
        _schedule_items,
        _completed_schedule_ids,
        completed_items,
        total_items,
        pending_items,
    ) = get_maintenance_summary(vehicle_id, target_mileage, db)

    kilometers_remaining = target_mileage - vehicle.current_mileage

    if pending_items == 0 and total_items > 0:
        general_status = "Al día"
    elif kilometers_remaining <= 0:
        general_status = "Mantenimiento vencido"
    elif kilometers_remaining <= 1000:
        general_status = "Mantenimiento cercano"
    else:
        general_status = "En control"

    return {
        "vehicle": vehicle,
        "next_maintenance_mileage": target_mileage,
        "kilometers_remaining": kilometers_remaining,
        "pending_items": pending_items,
        "completed_items": completed_items,
        "total_items": total_items,
        "general_status": general_status,
    }


@router.get("/vehicles/{vehicle_id}/maintenance", response_model=SwmMaintenanceResponse)
def get_maintenance(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: SwmUser = Depends(get_current_swm_user),
):
    vehicle = user_owns_vehicle_or_404(vehicle_id, current_user, db)
    current_mileage = vehicle.current_mileage

    target_mileage = get_target_maintenance_mileage(vehicle_id, current_mileage, db)

    overdue_mileages = [
        row[0]
        for row in (
            db.query(SwmMaintenanceSchedule.mileage)
            .filter(SwmMaintenanceSchedule.mileage < current_mileage)
            .distinct()
            .order_by(SwmMaintenanceSchedule.mileage.asc())
            .all()
        )
    ]

    if target_mileage is None:
        return {
            "vehicle_id": vehicle_id,
            "current_mileage": current_mileage,
            "overdue_mileages": overdue_mileages,
            "current_maintenance_mileage": None,
            "next_maintenance_mileage": None,
            "items": [],
        }

    schedule_items = get_schedule_items(target_mileage, db)
    completed_schedule_ids = get_completed_schedule_ids(vehicle_id, target_mileage, db)

    items = []

    for item in schedule_items:
        completed = item.id in completed_schedule_ids

        if completed:
            status = "realizado"
        elif target_mileage < current_mileage:
            status = "vencido"
        elif target_mileage == current_mileage:
            status = "ahora"
        else:
            status = "próximo"

        items.append(
            {
                "id": item.id,
                "mileage": item.mileage,
                "item_code": item.item_code,
                "item_name": item.item_name,
                "category": item.category,
                "description": item.description,
                "is_required": item.is_required,
                "status": status,
                "completed": completed,
            }
        )

    return {
        "vehicle_id": vehicle_id,
        "current_mileage": current_mileage,
        "overdue_mileages": overdue_mileages,
        "current_maintenance_mileage": target_mileage,
        "next_maintenance_mileage": target_mileage,
        "items": items,
    }


@router.post("/service-orders", response_model=SwmServiceOrderResponse, status_code=201)
def create_service_order(
    payload: SwmServiceOrderCreate,
    db: Session = Depends(get_db),
    current_user: SwmUser = Depends(get_current_swm_user),
):
    user_owns_vehicle_or_404(payload.vehicle_id, current_user, db)

    service_order = SwmServiceOrder(**payload.model_dump())
    db.add(service_order)
    db.commit()
    db.refresh(service_order)

    if not service_order.order_number:
        service_order.order_number = f"SWM-{service_order.id:06d}"
        db.commit()
        db.refresh(service_order)

    return service_order


@router.get(
    "/vehicles/{vehicle_id}/service-orders",
    response_model=list[SwmServiceOrderResponse],
)
def get_vehicle_service_orders(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: SwmUser = Depends(get_current_swm_user),
):
    user_owns_vehicle_or_404(vehicle_id, current_user, db)

    return (
        db.query(SwmServiceOrder)
        .filter(SwmServiceOrder.vehicle_id == vehicle_id)
        .order_by(SwmServiceOrder.service_date.desc(), SwmServiceOrder.id.desc())
        .all()
    )


@router.post("/services", response_model=SwmServiceRecordResponse, status_code=201)
def create_service_record(
    payload: SwmServiceRecordCreate,
    db: Session = Depends(get_db),
    current_user: SwmUser = Depends(get_current_swm_user),
):
    user_owns_vehicle_or_404(payload.vehicle_id, current_user, db)

    schedule_item = None

    if payload.schedule_id is not None:
        schedule_item = (
            db.query(SwmMaintenanceSchedule)
            .filter(SwmMaintenanceSchedule.id == payload.schedule_id)
            .first()
        )

        if not schedule_item:
            raise HTTPException(
                status_code=404,
                detail="Ítem de mantenimiento no encontrado.",
            )

    if payload.service_order_id is not None:
        service_order = (
            db.query(SwmServiceOrder)
            .filter(
                SwmServiceOrder.id == payload.service_order_id,
                SwmServiceOrder.vehicle_id == payload.vehicle_id,
            )
            .first()
        )

        if not service_order:
            raise HTTPException(status_code=404, detail="Orden de servicio no encontrada.")

    service_record = SwmServiceRecord(**payload.model_dump())

    db.add(service_record)
    db.commit()
    db.refresh(service_record)

    return {
        "id": service_record.id,
        "vehicle_id": service_record.vehicle_id,
        "service_order_id": service_record.service_order_id,
        "schedule_id": service_record.schedule_id,
        "service_mileage": service_record.service_mileage,
        "service_date": service_record.service_date,
        "workshop": service_record.workshop,
        "cost": service_record.cost,
        "notes": service_record.notes,
        "created_at": service_record.created_at,
        "item_name": schedule_item.item_name if schedule_item else None,
        "item_code": schedule_item.item_code if schedule_item else None,
        "category": schedule_item.category if schedule_item else None,
    }


@router.get("/vehicles/{vehicle_id}/history", response_model=list[SwmServiceRecordResponse])
def get_vehicle_history(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: SwmUser = Depends(get_current_swm_user),
):
    user_owns_vehicle_or_404(vehicle_id, current_user, db)

    records = (
        db.query(SwmServiceRecord)
        .options(joinedload(SwmServiceRecord.schedule), joinedload(SwmServiceRecord.service_order))
        .filter(SwmServiceRecord.vehicle_id == vehicle_id)
        .order_by(
            SwmServiceRecord.service_date.desc(),
            SwmServiceRecord.id.desc(),
        )
        .all()
    )

    return [
        {
            "id": record.id,
            "vehicle_id": record.vehicle_id,
            "service_order_id": record.service_order_id,
            "schedule_id": record.schedule_id,
            "service_mileage": record.service_mileage,
            "service_date": record.service_date,
            "workshop": record.workshop,
            "cost": record.cost,
            "notes": record.notes,
            "created_at": record.created_at,
            "item_name": record.schedule.item_name if record.schedule else None,
            "item_code": record.schedule.item_code if record.schedule else None,
            "category": record.schedule.category if record.schedule else None,
            "order_type": record.service_order.order_type if record.service_order else None,
            "order_title": record.service_order.title if record.service_order else None,
            "order_description": record.service_order.description if record.service_order else None,
            "order_total_cost": record.service_order.total_cost if record.service_order else None,
        }
        for record in records
    ]


@router.get("/vehicles/{vehicle_id}/maintenance/{mileage}/pdf")
def download_maintenance_pdf(
    vehicle_id: int,
    mileage: int,
    db: Session = Depends(get_db),
    current_user: SwmUser = Depends(get_current_swm_user),
):
    vehicle = user_owns_vehicle_or_404(vehicle_id, current_user, db)

    records = (
        db.query(SwmServiceRecord)
        .options(joinedload(SwmServiceRecord.schedule), joinedload(SwmServiceRecord.service_order))
        .filter(
            SwmServiceRecord.vehicle_id == vehicle.id,
            SwmServiceRecord.service_mileage == mileage,
        )
        .order_by(SwmServiceRecord.id.asc())
        .all()
    )

    pdf_bytes = build_maintenance_pdf(vehicle, mileage, records)
    filename = f"SWM-Care-Mantenimiento-{mileage}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )




@router.post("/events", response_model=SwmServiceOrderResponse, status_code=201)
def create_unscheduled_event(
    payload: SwmServiceOrderCreate,
    db: Session = Depends(get_db),
    current_user: SwmUser = Depends(get_current_swm_user),
):
    user_owns_vehicle_or_404(payload.vehicle_id, current_user, db)

    event_data = payload.model_dump()
    if event_data.get("order_type") == "maintenance":
        event_data["order_type"] = "repair"

    service_order = SwmServiceOrder(**event_data)
    db.add(service_order)
    db.commit()
    db.refresh(service_order)

    if not service_order.order_number:
        service_order.order_number = f"EVT-{service_order.id:06d}"
        db.commit()
        db.refresh(service_order)

    service_record = SwmServiceRecord(
        vehicle_id=service_order.vehicle_id,
        service_order_id=service_order.id,
        schedule_id=None,
        service_mileage=service_order.service_mileage,
        service_date=service_order.service_date,
        workshop=service_order.workshop,
        cost=service_order.total_cost,
        notes=service_order.description or service_order.notes or service_order.title,
    )

    db.add(service_record)
    db.commit()

    return service_order



# =========================
# COMBUSTIBLE
# =========================

@router.post(
    "/fuel",
    response_model=SwmFuelRecordResponse,
    status_code=201,
)
def create_fuel_record(
    payload: SwmFuelRecordCreate,
    db: Session = Depends(get_db),
    current_user: SwmUser = Depends(get_current_swm_user),
):
    vehicle = user_owns_vehicle_or_404(payload.vehicle_id, current_user, db)

    fuel_record = SwmFuelRecord(**payload.model_dump())
    db.add(fuel_record)

    if payload.mileage > vehicle.current_mileage:
        vehicle.current_mileage = payload.mileage

    db.commit()
    db.refresh(fuel_record)
    return fuel_record


@router.get(
    "/vehicles/{vehicle_id}/fuel",
    response_model=list[SwmFuelRecordResponse],
)
def get_vehicle_fuel_records(
    vehicle_id: int,
    db: Session = Depends(get_db),
    current_user: SwmUser = Depends(get_current_swm_user),
):
    user_owns_vehicle_or_404(vehicle_id, current_user, db)

    return (
        db.query(SwmFuelRecord)
        .filter(SwmFuelRecord.vehicle_id == vehicle_id)
        .order_by(
            SwmFuelRecord.fuel_date.desc(),
            SwmFuelRecord.id.desc(),
        )
        .all()
    )


@router.put(
    "/fuel/{fuel_record_id}",
    response_model=SwmFuelRecordResponse,
)
def update_fuel_record(
    fuel_record_id: int,
    payload: SwmFuelRecordUpdate,
    db: Session = Depends(get_db),
    current_user: SwmUser = Depends(get_current_swm_user),
):
    fuel_record = fuel_record_or_404(fuel_record_id, current_user, db)
    update_data = payload.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(fuel_record, field, value)

    vehicle = user_owns_vehicle_or_404(
        fuel_record.vehicle_id,
        current_user,
        db,
    )

    if (
        payload.mileage is not None
        and payload.mileage > vehicle.current_mileage
    ):
        vehicle.current_mileage = payload.mileage

    db.commit()
    db.refresh(fuel_record)
    return fuel_record


@router.delete("/fuel/{fuel_record_id}", status_code=204)
def delete_fuel_record(
    fuel_record_id: int,
    db: Session = Depends(get_db),
    current_user: SwmUser = Depends(get_current_swm_user),
):
    fuel_record = fuel_record_or_404(fuel_record_id, current_user, db)
    db.delete(fuel_record)
    db.commit()
    return Response(status_code=204)



@router.post("/ai/query", response_model=SwmAiQueryResponse, status_code=201)
def create_ai_query(
    payload: SwmAiQueryCreate,
    db: Session = Depends(get_db),
    current_user: SwmUser = Depends(get_current_swm_user),
):
    if payload.vehicle_id is not None:
        user_owns_vehicle_or_404(payload.vehicle_id, current_user, db)

    symptom_lower = payload.symptom.lower()

    if "aceite" in symptom_lower:
        response = (
            "Revisa el nivel de aceite, posibles fugas y el historial de cambios. "
            "Si se enciende un testigo o el nivel baja rápido, agenda una revisión."
        )
    elif "temperatura" in symptom_lower or "refrigerante" in symptom_lower:
        response = (
            "Revisa nivel de refrigerante, mangueras y posibles fugas. "
            "No continúes conduciendo si la temperatura sube de forma anormal."
        )
    elif "freno" in symptom_lower:
        response = (
            "Conviene revisar pastillas, discos, líquido de frenos y posibles ruidos. "
            "Si el pedal se siente diferente, prioriza una inspección profesional."
        )
    elif "turbo" in symptom_lower:
        response = (
            "Revisa pérdida de potencia, ruidos inusuales, mangueras y consumo de aceite. "
            "Una inspección especializada puede descartar problemas en turbo o admisión."
        )
    else:
        response = (
            "La recomendación inicial es revisar el historial de mantenimiento, "
            "anotar cuándo aparece el síntoma y solicitar una inspección si persiste."
        )

    ai_query = SwmAiQuery(
        vehicle_id=payload.vehicle_id,
        symptom=payload.symptom,
        ai_response=response,
    )

    db.add(ai_query)
    db.commit()
    db.refresh(ai_query)

    return ai_query

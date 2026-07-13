from datetime import date, datetime
from typing import Literal, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database import get_db
from app.models.user import User

router = APIRouter(prefix="/reminders", tags=["Maintenance Reminders"])
ReminderStatus = Literal["programado", "proximo", "urgente", "hoy", "vencido", "enviado"]


def calculate_status(next_service_date: date, reminder_sent: bool) -> tuple[str, int]:
    days_remaining = (next_service_date - date.today()).days
    if reminder_sent:
        return "enviado", days_remaining
    if days_remaining < 0:
        return "vencido", days_remaining
    if days_remaining == 0:
        return "hoy", days_remaining
    if days_remaining <= 15:
        return "urgente", days_remaining
    if days_remaining <= 30:
        return "proximo", days_remaining
    return "programado", days_remaining


def format_date_es(value: date) -> str:
    months = [
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
    ]
    return f"{value.day} de {months[value.month - 1]} de {value.year}"


def normalize_title(value: str) -> str:
    return " ".join((value or "").lower().strip().split())


def build_whatsapp_message(client_name: str, workshop_name: str, vehicle_name: str,
                           plate: str, service_description: str,
                           next_service_date: date) -> str:
    first_name = (client_name or "cliente").strip().split(" ")[0]
    vehicle_text = vehicle_name.strip() if vehicle_name.strip() else "tu vehículo"
    plate_text = f" de placa {plate}" if plate else ""
    service_text = service_description.strip().lower()
    return (
        f"Hola {first_name} 👋\n\n"
        f"Te saludamos de {workshop_name}.\n\n"
        f"Según el historial de mantenimiento de {vehicle_text}{plate_text}, "
        f"tu próximo {service_text} está estimado para el "
        f"{format_date_es(next_service_date)}.\n\n"
        "Te recomendamos agendar una revisión para mantener tu vehículo en "
        "óptimas condiciones.\n\n"
        "¿Deseas reservar una cita?"
    )


def choose_main_item(items: list[dict]) -> dict:
    labor = [i for i in items if str(i.get("item_type") or "").lower() == "mano_obra"]
    return labor[0] if labor else items[0]


@router.get("/")
def list_reminders(
    status: Optional[ReminderStatus] = Query(default=None),
    include_programmed: bool = Query(default=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = text("""
        SELECT
            woi.id AS item_id,
            woi.work_order_id,
            woi.item_type,
            woi.description,
            woi.next_service_date,
            COALESCE(woi.reminder_enabled, TRUE) AS reminder_enabled,
            COALESCE(woi.reminder_sent, FALSE) AS reminder_sent,
            wo.id AS work_order_number,
            wo.entry_date AS last_service_date,
            wo.client_id,
            wo.vehicle_id,
            c.full_name AS client_name,
            c.phone AS client_phone,
            v.plate,
            v.brand,
            v.model,
            v.year,
            ws.name AS workshop_name
        FROM work_order_items woi
        INNER JOIN work_orders wo ON wo.id = woi.work_order_id
        INNER JOIN clients c ON c.id = wo.client_id
        INNER JOIN vehicles v ON v.id = wo.vehicle_id
        INNER JOIN workshops ws ON ws.id = wo.workshop_id
        WHERE wo.workshop_id = :workshop_id
          AND woi.next_service_date IS NOT NULL
          AND COALESCE(woi.reminder_enabled, TRUE) = TRUE
        ORDER BY
            woi.next_service_date ASC,
            wo.id ASC,
            CASE WHEN woi.item_type = 'mano_obra' THEN 0 ELSE 1 END,
            woi.id ASC
    """)
    rows = db.execute(query, {"workshop_id": current_user.workshop_id}).mappings().all()

    # Una OT + vehículo + fecha estimada = un único recordatorio.
    raw_groups: dict[tuple[int, int, date], list[dict]] = {}
    for row in rows:
        item = dict(row)
        key = (item["work_order_id"], item["vehicle_id"], item["next_service_date"])
        raw_groups.setdefault(key, []).append(item)

    groups = []
    for items in raw_groups.values():
        main = choose_main_item(items)
        groups.append({
            "main": main,
            "items": items,
            "sent": all(bool(i["reminder_sent"]) for i in items),
        })

    # Para el mismo vehículo y servicio principal, conservar la programación más reciente.
    latest: dict[tuple[int, str], dict] = {}
    for group in groups:
        main = group["main"]
        key = (main["vehicle_id"], normalize_title(main["description"]))
        previous = latest.get(key)
        if previous is None:
            latest[key] = group
            continue
        prev_main = previous["main"]
        current_order = (main["next_service_date"], main["work_order_id"], main["item_id"])
        previous_order = (prev_main["next_service_date"], prev_main["work_order_id"], prev_main["item_id"])
        if current_order > previous_order:
            latest[key] = group

    selected = sorted(latest.values(), key=lambda g: (g["main"]["next_service_date"], g["main"]["item_id"]))

    summary = {"vencido": 0, "hoy": 0, "urgente": 0, "proximo": 0,
               "programado": 0, "enviado": 0, "total": 0}
    reminders = []

    for group in selected:
        row = group["main"]
        next_date = row["next_service_date"]
        reminder_status, days_remaining = calculate_status(next_date, group["sent"])
        summary[reminder_status] += 1
        summary["total"] += 1

        if status and reminder_status != status:
            continue
        if not include_programmed and reminder_status == "programado":
            continue

        vehicle_name = " ".join(str(v).strip() for v in [row["brand"], row["model"]] if v not in [None, ""])
        message = build_whatsapp_message(
            row["client_name"] or "cliente",
            row["workshop_name"] or "SIADAUTO",
            vehicle_name,
            row["plate"] or "",
            row["description"],
            next_date,
        )
        phone = "".join(c for c in str(row["client_phone"] or "") if c.isdigit())

        reminders.append({
            "item_id": row["item_id"],
            "group_item_ids": [i["item_id"] for i in group["items"]],
            "work_order_id": row["work_order_id"],
            "work_order_number": row["work_order_number"],
            "client_id": row["client_id"],
            "client_name": row["client_name"],
            "client_phone": row["client_phone"],
            "vehicle_id": row["vehicle_id"],
            "vehicle": vehicle_name,
            "plate": row["plate"],
            "year": row["year"],
            "service_description": row["description"],
            "included_items": [
                {"item_id": i["item_id"], "item_type": i["item_type"], "description": i["description"]}
                for i in group["items"]
            ],
            "last_service_date": row["last_service_date"],
            "next_service_date": next_date,
            "days_remaining": days_remaining,
            "status": reminder_status,
            "reminder_enabled": True,
            "reminder_sent": group["sent"],
            "whatsapp_message": message,
            "whatsapp_url": f"https://wa.me/{phone}?text={quote(message)}" if phone else None,
        })

    return {"generated_at": datetime.now().isoformat(), "summary": summary, "reminders": reminders}


@router.get("/summary")
def reminders_summary(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return list_reminders(None, True, db, current_user)["summary"]


def get_group_source(item_id: int, db: Session, current_user: User):
    source = db.execute(text("""
        SELECT woi.work_order_id, woi.next_service_date
        FROM work_order_items woi
        INNER JOIN work_orders wo ON wo.id = woi.work_order_id
        WHERE woi.id = :item_id
          AND wo.workshop_id = :workshop_id
          AND woi.next_service_date IS NOT NULL
    """), {"item_id": item_id, "workshop_id": current_user.workshop_id}).mappings().first()
    if not source:
        raise HTTPException(status_code=404, detail="Recordatorio no encontrado para este taller")
    return source


def update_group_status(item_id: int, sent: bool, db: Session, current_user: User):
    source = get_group_source(item_id, db, current_user)
    updated = db.execute(text("""
        UPDATE work_order_items
        SET reminder_sent = :sent
        WHERE work_order_id = :work_order_id
          AND next_service_date = :next_service_date
          AND COALESCE(reminder_enabled, TRUE) = TRUE
        RETURNING id
    """), {
        "sent": sent,
        "work_order_id": source["work_order_id"],
        "next_service_date": source["next_service_date"],
    }).mappings().all()
    db.commit()
    return {
        "ok": True,
        "item_id": item_id,
        "work_order_id": source["work_order_id"],
        "next_service_date": source["next_service_date"],
        "updated_item_ids": [r["id"] for r in updated],
        "reminder_sent": sent,
    }


@router.post("/{item_id}/mark-sent")
def mark_reminder_sent(item_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = update_group_status(item_id, True, db, current_user)
    result["message"] = "Recordatorio agrupado marcado como enviado"
    return result


@router.post("/{item_id}/mark-pending")
def mark_reminder_pending(item_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = update_group_status(item_id, False, db, current_user)
    result["message"] = "Recordatorio agrupado devuelto a pendiente"
    return result

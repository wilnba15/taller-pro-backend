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
    """
    Calcula el estado únicamente por fecha.

    Reglas:
    - enviado: el taller ya registró el envío del recordatorio
    - vencido: la fecha ya pasó
    - hoy: corresponde a la fecha actual
    - urgente: faltan entre 1 y 15 días
    - próximo: faltan entre 16 y 30 días
    - programado: faltan más de 30 días
    """
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


def build_whatsapp_message(
    client_name: str,
    workshop_name: str,
    vehicle_name: str,
    plate: str,
    service_description: str,
    next_service_date: date,
) -> str:
    first_name = (client_name or "cliente").strip().split(" ")[0]
    vehicle_text = vehicle_name.strip() if vehicle_name.strip() else "tu vehículo"
    plate_text = f" de placa {plate}" if plate else ""

    return (
        f"Hola {first_name} 👋\n\n"
        f"Te saludamos de {workshop_name}.\n\n"
        f"Según el historial de mantenimiento de {vehicle_text}{plate_text}, "
        f"se aproxima el servicio de {service_description}, estimado para el "
        f"{format_date_es(next_service_date)}.\n\n"
        "Te recomendamos agendar una revisión para mantener tu vehículo en "
        "óptimas condiciones.\n\n"
        "¿Deseas reservar una cita?"
    )


@router.get("/")
def list_reminders(
    status: Optional[ReminderStatus] = Query(default=None),
    include_programmed: bool = Query(
        default=True,
        description="Incluye recordatorios con más de 30 días de anticipación.",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Lista los próximos mantenimientos del taller autenticado.

    Para evitar recordatorios antiguos duplicados, conserva únicamente el
    registro más reciente de cada servicio por vehículo.
    """
    query = text("""
        WITH ranked_reminders AS (
            SELECT
                woi.id AS item_id,
                woi.work_order_id,
                woi.description AS service_description,
                woi.next_service_date,
                COALESCE(woi.reminder_enabled, TRUE) AS reminder_enabled,
                COALESCE(woi.reminder_sent, FALSE) AS reminder_sent,
                COALESCE(wo.order_number, wo.id) AS work_order_number,
                wo.entry_date AS last_service_date,
                wo.client_id,
                wo.vehicle_id,
                c.full_name AS client_name,
                c.phone AS client_phone,
                v.plate,
                v.brand,
                v.model,
                v.year,
                ws.name AS workshop_name,
                ROW_NUMBER() OVER (
                    PARTITION BY
                        wo.vehicle_id,
                        LOWER(TRIM(woi.description))
                    ORDER BY
                        woi.next_service_date DESC,
                        woi.id DESC
                ) AS row_number
            FROM work_order_items woi
            INNER JOIN work_orders wo
                ON wo.id = woi.work_order_id
            INNER JOIN clients c
                ON c.id = wo.client_id
            INNER JOIN vehicles v
                ON v.id = wo.vehicle_id
            INNER JOIN workshops ws
                ON ws.id = wo.workshop_id
            WHERE wo.workshop_id = :workshop_id
              AND woi.next_service_date IS NOT NULL
              AND COALESCE(woi.reminder_enabled, TRUE) = TRUE
        )
        SELECT *
        FROM ranked_reminders
        WHERE row_number = 1
        ORDER BY next_service_date ASC, item_id ASC
    """)

    rows = db.execute(
        query,
        {"workshop_id": current_user.workshop_id},
    ).mappings().all()

    reminders = []
    summary = {
        "vencido": 0,
        "hoy": 0,
        "urgente": 0,
        "proximo": 0,
        "programado": 0,
        "enviado": 0,
        "total": 0,
    }

    for row in rows:
        next_date = row["next_service_date"]
        reminder_status, days_remaining = calculate_status(
            next_date,
            bool(row["reminder_sent"]),
        )

        summary[reminder_status] += 1
        summary["total"] += 1

        if status and reminder_status != status:
            continue
        if not include_programmed and reminder_status == "programado":
            continue

        vehicle_name = " ".join(
            str(value).strip()
            for value in [row["brand"], row["model"]]
            if value not in [None, ""]
        )

        message = build_whatsapp_message(
            client_name=row["client_name"] or "cliente",
            workshop_name=row["workshop_name"] or "SIADAUTO",
            vehicle_name=vehicle_name,
            plate=row["plate"] or "",
            service_description=row["service_description"],
            next_service_date=next_date,
        )

        phone = "".join(
            character
            for character in str(row["client_phone"] or "")
            if character.isdigit()
        )

        reminders.append(
            {
                "item_id": row["item_id"],
                "work_order_id": row["work_order_id"],
                "work_order_number": row["work_order_number"],
                "client_id": row["client_id"],
                "client_name": row["client_name"],
                "client_phone": row["client_phone"],
                "vehicle_id": row["vehicle_id"],
                "vehicle": vehicle_name,
                "plate": row["plate"],
                "year": row["year"],
                "service_description": row["service_description"],
                "last_service_date": row["last_service_date"],
                "next_service_date": next_date,
                "days_remaining": days_remaining,
                "status": reminder_status,
                "reminder_enabled": bool(row["reminder_enabled"]),
                "reminder_sent": bool(row["reminder_sent"]),
                "whatsapp_message": message,
                "whatsapp_url": (
                    f"https://wa.me/{phone}?text={quote(message)}"
                    if phone
                    else None
                ),
            }
        )

    return {
        "generated_at": datetime.now().isoformat(),
        "summary": summary,
        "reminders": reminders,
    }


@router.get("/summary")
def reminders_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Devuelve únicamente los contadores para las tarjetas del dashboard.
    """
    result = list_reminders(
        status=None,
        include_programmed=True,
        db=db,
        current_user=current_user,
    )
    return result["summary"]


@router.post("/{item_id}/mark-sent")
def mark_reminder_sent(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Marca el recordatorio como enviado después de que el usuario pulse
    el botón de WhatsApp.
    """
    query = text("""
        UPDATE work_order_items AS woi
        SET reminder_sent = TRUE
        FROM work_orders AS wo
        WHERE woi.id = :item_id
          AND wo.id = woi.work_order_id
          AND wo.workshop_id = :workshop_id
          AND woi.next_service_date IS NOT NULL
        RETURNING
            woi.id,
            woi.work_order_id,
            woi.reminder_sent,
            woi.next_service_date
    """)

    row = db.execute(
        query,
        {
            "item_id": item_id,
            "workshop_id": current_user.workshop_id,
        },
    ).mappings().first()

    if not row:
        db.rollback()
        raise HTTPException(
            status_code=404,
            detail="Recordatorio no encontrado para este taller",
        )

    db.commit()

    return {
        "ok": True,
        "message": "Recordatorio marcado como enviado",
        "item_id": row["id"],
        "work_order_id": row["work_order_id"],
        "reminder_sent": bool(row["reminder_sent"]),
        "next_service_date": row["next_service_date"],
    }


@router.post("/{item_id}/mark-pending")
def mark_reminder_pending(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Permite corregir un clic accidental y devolver el recordatorio a pendiente.
    """
    query = text("""
        UPDATE work_order_items AS woi
        SET reminder_sent = FALSE
        FROM work_orders AS wo
        WHERE woi.id = :item_id
          AND wo.id = woi.work_order_id
          AND wo.workshop_id = :workshop_id
        RETURNING woi.id, woi.work_order_id, woi.reminder_sent
    """)

    row = db.execute(
        query,
        {
            "item_id": item_id,
            "workshop_id": current_user.workshop_id,
        },
    ).mappings().first()

    if not row:
        db.rollback()
        raise HTTPException(
            status_code=404,
            detail="Recordatorio no encontrado para este taller",
        )

    db.commit()

    return {
        "ok": True,
        "message": "Recordatorio devuelto a pendiente",
        "item_id": row["id"],
        "work_order_id": row["work_order_id"],
        "reminder_sent": bool(row["reminder_sent"]),
    }

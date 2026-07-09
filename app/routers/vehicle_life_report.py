from datetime import date, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db

router = APIRouter(
    prefix="/api/vehicle-life",
    tags=["SIADAUTO - Vida del Auto"],
)


def row_to_dict(row):
    return dict(row._mapping)


@router.get("/vehicle/{vehicle_id}")
def get_vehicle_life(vehicle_id: int, db: Session = Depends(get_db)):
    """
    Reporte Vida del Auto.
    Lee directamente work_orders + work_order_items.
    No duplica historial.
    Compatible con SQLAlchemy SessionLocal.
    """

    query = text("""
        SELECT
            wo.id AS work_order_id,
            wo.created_at AS work_order_date,
            wo.current_km,
            wo.status,

            woi.id AS item_id,
            woi.item_type,
            woi.description,
            woi.quantity,
            woi.unit_price,
            woi.subtotal,
            woi.next_service_km,
            woi.next_service_date,
            woi.reminder_enabled,
            woi.reminder_sent

        FROM work_orders wo
        INNER JOIN work_order_items woi
            ON woi.work_order_id = wo.id
        WHERE wo.vehicle_id = :vehicle_id
        ORDER BY
            wo.current_km DESC NULLS LAST,
            wo.created_at DESC,
            woi.id ASC
    """)

    rows = [row_to_dict(row) for row in db.execute(query, {"vehicle_id": vehicle_id}).fetchall()]

    total_invested = sum(float(row.get("subtotal") or 0) for row in rows)

    next_services = []
    for row in rows:
        if row.get("next_service_km") or row.get("next_service_date"):
            next_services.append({
                "work_order_id": row.get("work_order_id"),
                "item_id": row.get("item_id"),
                "description": row.get("description"),
                "item_type": row.get("item_type"),
                "current_km": row.get("current_km"),
                "next_service_km": row.get("next_service_km"),
                "next_service_date": row.get("next_service_date"),
                "reminder_enabled": row.get("reminder_enabled"),
                "reminder_sent": row.get("reminder_sent"),
            })

    return {
        "vehicle_id": vehicle_id,
        "total_events": len(rows),
        "total_invested": total_invested,
        "last_km": rows[0].get("current_km") if rows else None,
        "items": rows,
        "next_services": next_services,
    }


@router.get("/reminders/pending")
def get_pending_vehicle_life_reminders(
    days_ahead: int = Query(default=15, ge=1, le=90),
    db: Session = Depends(get_db),
):
    """
    Recordatorios pendientes por fecha.
    """

    today = date.today()
    limit_date = today + timedelta(days=days_ahead)

    query = text("""
        SELECT
            wo.id AS work_order_id,
            wo.vehicle_id,
            wo.current_km,
            wo.created_at AS work_order_date,

            v.plate,
            v.brand,
            v.model,

            c.full_name AS client_name,
            c.phone AS client_phone,

            woi.id AS item_id,
            woi.item_type,
            woi.description,
            woi.next_service_km,
            woi.next_service_date,
            woi.reminder_enabled,
            woi.reminder_sent

        FROM work_order_items woi
        INNER JOIN work_orders wo
            ON wo.id = woi.work_order_id
        LEFT JOIN vehicles v
            ON v.id = wo.vehicle_id
        LEFT JOIN clients c
            ON c.id = wo.client_id
        WHERE woi.reminder_enabled = TRUE
          AND woi.reminder_sent = FALSE
          AND woi.next_service_date IS NOT NULL
          AND woi.next_service_date BETWEEN :today AND :limit_date
        ORDER BY woi.next_service_date ASC
    """)

    rows = [
        row_to_dict(row)
        for row in db.execute(query, {"today": today, "limit_date": limit_date}).fetchall()
    ]

    reminders = []

    for row in rows:
        vehicle_name = " ".join(
            str(x) for x in [row.get("brand"), row.get("model")] if x
        ).strip()

        next_km = row.get("next_service_km")
        next_date = row.get("next_service_date")

        message = (
            f"Hola 👋, te saluda GARAGE SIADAUTO.\n\n"
            f"Tu {vehicle_name or 'vehículo'}"
            f"{' placa ' + row.get('plate') if row.get('plate') else ''} "
            f"está próximo a: {row.get('description')}.\n\n"
            f"Según nuestro historial, corresponde aproximadamente "
            f"{'a los ' + str(next_km) + ' km' if next_km else ''}"
            f"{' o ' if next_km and next_date else ''}"
            f"{'para el ' + str(next_date) if next_date else ''}.\n\n"
            f"¿Deseas agendar una revisión?"
        )

        reminders.append({
            "work_order_id": row.get("work_order_id"),
            "item_id": row.get("item_id"),
            "vehicle_id": row.get("vehicle_id"),
            "client_name": row.get("client_name"),
            "client_phone": row.get("client_phone"),
            "plate": row.get("plate"),
            "description": row.get("description"),
            "next_service_km": next_km,
            "next_service_date": next_date,
            "whatsapp_message": message,
        })

    return reminders

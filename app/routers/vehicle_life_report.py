from datetime import date, timedelta
from typing import Optional, List, Any
from fastapi import APIRouter, Query
from pydantic import BaseModel

# Ajusta este import si tu backend usa otro archivo para la conexión.
# En muchos proyectos queda así:
from app.database import database

router = APIRouter(
    prefix="/api/vehicle-life",
    tags=["SIADAUTO - Vida del Auto"],
)


class VehicleLifeItem(BaseModel):
    work_order_id: int
    work_order_date: Optional[Any] = None
    current_km: Optional[int] = None
    status: Optional[str] = None

    item_id: int
    item_type: Optional[str] = None
    description: Optional[str] = None
    quantity: Optional[float] = None
    unit_price: Optional[float] = None
    subtotal: Optional[float] = None

    next_service_km: Optional[int] = None
    next_service_date: Optional[Any] = None
    reminder_enabled: Optional[bool] = True
    reminder_sent: Optional[bool] = False


@router.get("/vehicle/{vehicle_id}")
async def get_vehicle_life(vehicle_id: int):
    """
    Reporte Vida del Auto.
    Lee directamente work_orders + work_order_items.
    No duplica historial.
    """

    query = """
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
    """

    rows = await database.fetch_all(query=query, values={"vehicle_id": vehicle_id})

    total_invested = sum(float(row["subtotal"] or 0) for row in rows)

    next_services = []
    for row in rows:
        if row["next_service_km"] or row["next_service_date"]:
            next_services.append({
                "work_order_id": row["work_order_id"],
                "item_id": row["item_id"],
                "description": row["description"],
                "item_type": row["item_type"],
                "current_km": row["current_km"],
                "next_service_km": row["next_service_km"],
                "next_service_date": row["next_service_date"],
                "reminder_enabled": row["reminder_enabled"],
                "reminder_sent": row["reminder_sent"],
            })

    return {
        "vehicle_id": vehicle_id,
        "total_events": len(rows),
        "total_invested": total_invested,
        "last_km": rows[0]["current_km"] if rows else None,
        "items": rows,
        "next_services": next_services,
    }


@router.get("/reminders/pending")
async def get_pending_vehicle_life_reminders(
    days_ahead: int = Query(default=15, ge=1, le=90)
):
    """
    Recordatorios pendientes por fecha.
    Luego se puede sumar regla por kilometraje cuando exista km actual del vehículo.
    """

    today = date.today()
    limit_date = today + timedelta(days=days_ahead)

    query = """
    SELECT
        wo.id AS work_order_id,
        wo.vehicle_id,
        wo.current_km,
        wo.created_at AS work_order_date,

        v.plate,
        v.brand,
        v.model,
        v.year,

        c.name AS client_name,
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
    """

    rows = await database.fetch_all(
        query=query,
        values={"today": today, "limit_date": limit_date},
    )

    reminders = []

    for row in rows:
        vehicle_name = " ".join(
            str(x) for x in [row["brand"], row["model"], row["year"]] if x
        ).strip()

        message = (
            f"Hola 👋, te saluda GARAGE SIADAUTO.\n\n"
            f"Tu {vehicle_name or 'vehículo'}"
            f"{' placa ' + row['plate'] if row['plate'] else ''} "
            f"está próximo a: {row['description']}.\n\n"
            f"Según nuestro historial, corresponde aproximadamente "
            f"{'a los ' + str(row['next_service_km']) + ' km' if row['next_service_km'] else ''}"
            f"{' o ' if row['next_service_km'] and row['next_service_date'] else ''}"
            f"{'para el ' + str(row['next_service_date']) if row['next_service_date'] else ''}.\n\n"
            f"¿Deseas agendar una revisión?"
        )

        reminders.append({
            "work_order_id": row["work_order_id"],
            "item_id": row["item_id"],
            "vehicle_id": row["vehicle_id"],
            "client_name": row["client_name"],
            "client_phone": row["client_phone"],
            "plate": row["plate"],
            "description": row["description"],
            "next_service_km": row["next_service_km"],
            "next_service_date": row["next_service_date"],
            "whatsapp_message": message,
        })

    return reminders

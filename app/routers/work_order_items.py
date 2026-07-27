from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database import get_db
from app.models.work_order import WorkOrder
from app.models.work_order_item import WorkOrderItem
from app.models.inventory_product import InventoryProduct
from app.models.workshop import Workshop
from app.models.user import User
from app.core.security import get_current_user

router = APIRouter(prefix="/work-order-items", tags=["Work Order Items"])


def get_owned_work_order(order_id: int, db: Session, current_user: User) -> WorkOrder:
    work_order = (
        db.query(WorkOrder)
        .filter(
            WorkOrder.id == order_id,
            WorkOrder.workshop_id == current_user.workshop_id,
        )
        .first()
    )
    if not work_order:
        raise HTTPException(status_code=404, detail="Orden de trabajo no encontrada")
    return work_order


def recalculate_order_totals(work_order: WorkOrder, db: Session) -> None:
    items = db.query(WorkOrderItem).filter(WorkOrderItem.work_order_id == work_order.id).all()
    labor = sum(Decimal(item.subtotal or 0) for item in items if item.item_type == "mano_obra")
    parts = sum(Decimal(item.subtotal or 0) for item in items if item.item_type == "repuesto")
    work_order.labor_cost = labor
    work_order.parts_cost = parts
    work_order.total = labor + parts


@router.post("/")
def create_item(
    item: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    work_order_id = item.get("work_order_id")
    if not work_order_id:
        raise HTTPException(status_code=400, detail="work_order_id es obligatorio")

    work_order = get_owned_work_order(int(work_order_id), db, current_user)

    item_type = item.get("item_type")
    inventory_product_id = item.get("inventory_product_id")

    if item_type not in {"repuesto", "mano_obra"}:
        raise HTTPException(status_code=400, detail="Tipo de ítem no válido")

    if item_type == "mano_obra":
        inventory_product_id = None

    inventory_product = None
    if inventory_product_id not in [None, ""]:
        workshop = (
            db.query(Workshop)
            .filter(Workshop.id == current_user.workshop_id)
            .first()
        )

        if not workshop or not workshop.inventory_enabled:
            raise HTTPException(
                status_code=403,
                detail="El módulo de inventario no está habilitado para este taller",
            )

        inventory_product = (
            db.query(InventoryProduct)
            .filter(
                InventoryProduct.id == int(inventory_product_id),
                InventoryProduct.workshop_id == current_user.workshop_id,
                InventoryProduct.is_active.is_(True),
            )
            .first()
        )

        if not inventory_product:
            raise HTTPException(
                status_code=404,
                detail="Producto de inventario no encontrado para este taller",
            )

    quantity = Decimal(str(item.get("quantity") or 0))
    unit_price = Decimal(str(item.get("unit_price") or 0))
    subtotal = Decimal(str(item.get("subtotal") or (quantity * unit_price)))

    if quantity <= 0:
        raise HTTPException(status_code=400, detail="La cantidad debe ser mayor que cero")

    if inventory_product and quantity > Decimal(inventory_product.stock or 0):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Stock insuficiente para {inventory_product.name}. "
                f"Disponible: {inventory_product.stock}"
            ),
        )

    next_service_km = item.get("next_service_km")
    next_service_date = item.get("next_service_date")
    reminder_enabled = item.get("reminder_enabled")
    if reminder_enabled is None:
        reminder_enabled = True

    insert_query = text("""
        INSERT INTO work_order_items (
            work_order_id,
            inventory_product_id,
            item_type,
            description,
            quantity,
            unit_price,
            subtotal,
            next_service_km,
            next_service_date,
            reminder_enabled
        )
        VALUES (
            :work_order_id,
            :inventory_product_id,
            :item_type,
            :description,
            :quantity,
            :unit_price,
            :subtotal,
            :next_service_km,
            :next_service_date,
            :reminder_enabled
        )
        RETURNING
            id,
            work_order_id,
            inventory_product_id,
            item_type,
            description,
            quantity,
            unit_price,
            subtotal,
            next_service_km,
            next_service_date,
            reminder_enabled,
            reminder_sent,
            created_at
    """)

    db_item = db.execute(
        insert_query,
        {
            "work_order_id": work_order.id,
            "inventory_product_id": (
                int(inventory_product_id)
                if inventory_product_id not in [None, ""]
                else None
            ),
            "item_type": item_type,
            "description": item.get("description"),
            "quantity": quantity,
            "unit_price": unit_price,
            "subtotal": subtotal,
            "next_service_km": int(next_service_km) if next_service_km not in [None, ""] else None,
            "next_service_date": next_service_date or None,
            "reminder_enabled": reminder_enabled,
        },
    ).mappings().first()

    recalculate_order_totals(work_order, db)
    db.commit()

    return dict(db_item)


@router.get("/work-order/{order_id}")
def get_items(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_owned_work_order(order_id, db, current_user)

    query = text("""
        SELECT
            id,
            work_order_id,
            inventory_product_id,
            item_type,
            description,
            quantity,
            unit_price,
            subtotal,
            next_service_km,
            next_service_date,
            reminder_enabled,
            reminder_sent,
            created_at
        FROM work_order_items
        WHERE work_order_id = :order_id
        ORDER BY id ASC
    """)

    rows = db.execute(query, {"order_id": order_id}).mappings().all()
    return [dict(row) for row in rows]


@router.delete("/{item_id}")
def delete_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = db.query(WorkOrderItem).filter(WorkOrderItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Ítem no encontrado")

    work_order = get_owned_work_order(item.work_order_id, db, current_user)

    db.delete(item)
    db.flush()
    recalculate_order_totals(work_order, db)
    db.commit()
    return {"ok": True}

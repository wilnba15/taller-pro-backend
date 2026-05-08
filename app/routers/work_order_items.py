from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.work_order import WorkOrder
from app.models.work_order_item import WorkOrderItem
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

    quantity = Decimal(str(item.get("quantity") or 0))
    unit_price = Decimal(str(item.get("unit_price") or 0))
    subtotal = Decimal(str(item.get("subtotal") or (quantity * unit_price)))

    db_item = WorkOrderItem(
        work_order_id=work_order.id,
        item_type=item.get("item_type"),
        description=item.get("description"),
        quantity=quantity,
        unit_price=unit_price,
        subtotal=subtotal,
    )
    db.add(db_item)
    recalculate_order_totals(work_order, db)
    db.commit()
    db.refresh(db_item)
    return db_item


@router.get("/work-order/{order_id}")
def get_items(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_owned_work_order(order_id, db, current_user)
    return (
        db.query(WorkOrderItem)
        .filter(WorkOrderItem.work_order_id == order_id)
        .order_by(WorkOrderItem.id.asc())
        .all()
    )


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

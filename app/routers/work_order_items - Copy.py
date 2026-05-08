from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.work_order_item import WorkOrderItem

router = APIRouter(prefix="/work-order-items", tags=["Work Order Items"])


# ✅ CREAR ITEM
@router.post("/")
def create_item(item: dict, db: Session = Depends(get_db)):
    db_item = WorkOrderItem(**item)
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


# ✅ OBTENER ITEMS POR ORDEN
@router.get("/work-order/{order_id}")
def get_items(order_id: int, db: Session = Depends(get_db)):
    return db.query(WorkOrderItem).filter(
        WorkOrderItem.work_order_id == order_id
    ).all()


# ✅ ELIMINAR ITEM
@router.delete("/{item_id}")
def delete_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(WorkOrderItem).get(item_id)

    if not item:
        raise HTTPException(status_code=404, detail="Item no encontrado")

    db.delete(item)
    db.commit()
    return {"ok": True}
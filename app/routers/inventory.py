from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database import get_db
from app.models.inventory_product import InventoryProduct
from app.models.user import User
from app.models.workshop import Workshop
from app.schemas.inventory import InventoryProductCreate, InventoryProductResponse, InventoryProductUpdate

router = APIRouter(prefix="/inventory", tags=["Inventory"])

def require_inventory_enabled(db: Session, current_user: User) -> Workshop:
    workshop = db.query(Workshop).filter(Workshop.id == current_user.workshop_id).first()
    if not workshop:
        raise HTTPException(status_code=404, detail="Taller no encontrado")
    if not workshop.inventory_enabled:
        raise HTTPException(status_code=403, detail="El módulo de inventario no está habilitado para este taller")
    return workshop

def serialize_product(product: InventoryProduct) -> dict:
    stock = Decimal(product.stock or 0)
    minimum_stock = Decimal(product.minimum_stock or 0)
    return {
        "id": product.id, "workshop_id": product.workshop_id, "code": product.code,
        "name": product.name, "category": product.category, "brand": product.brand,
        "stock": stock, "minimum_stock": minimum_stock,
        "cost": Decimal(product.cost or 0), "sale_price": Decimal(product.sale_price or 0),
        "is_active": product.is_active, "created_at": product.created_at,
        "updated_at": product.updated_at, "low_stock": stock <= minimum_stock,
    }

@router.get("/", response_model=list[InventoryProductResponse])
def list_products(
    search: str | None = Query(default=None, max_length=120),
    low_stock: bool = False,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_inventory_enabled(db, current_user)
    query = db.query(InventoryProduct).filter(InventoryProduct.workshop_id == current_user.workshop_id)
    if not include_inactive:
        query = query.filter(InventoryProduct.is_active.is_(True))
    if search:
        term = f"%{search.strip()}%"
        query = query.filter(or_(
            InventoryProduct.name.ilike(term), InventoryProduct.code.ilike(term),
            InventoryProduct.category.ilike(term), InventoryProduct.brand.ilike(term),
        ))
    result = [serialize_product(p) for p in query.order_by(InventoryProduct.name.asc()).all()]
    return [p for p in result if p["low_stock"]] if low_stock else result

@router.post("/", response_model=InventoryProductResponse, status_code=201)
def create_product(
    data: InventoryProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_inventory_enabled(db, current_user)
    if data.code:
        duplicated = db.query(InventoryProduct).filter(
            InventoryProduct.workshop_id == current_user.workshop_id,
            InventoryProduct.code == data.code,
        ).first()
        if duplicated:
            raise HTTPException(status_code=400, detail="Ya existe un producto con ese código en este taller")
    product = InventoryProduct(workshop_id=current_user.workshop_id, **data.model_dump())
    db.add(product); db.commit(); db.refresh(product)
    return serialize_product(product)

@router.put("/{product_id}", response_model=InventoryProductResponse)
def update_product(
    product_id: int,
    data: InventoryProductUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_inventory_enabled(db, current_user)
    product = db.query(InventoryProduct).filter(
        InventoryProduct.id == product_id,
        InventoryProduct.workshop_id == current_user.workshop_id,
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    update_data = data.model_dump(exclude_unset=True)
    new_code = update_data.get("code")
    if new_code:
        duplicated = db.query(InventoryProduct).filter(
            InventoryProduct.workshop_id == current_user.workshop_id,
            InventoryProduct.code == new_code,
            InventoryProduct.id != product_id,
        ).first()
        if duplicated:
            raise HTTPException(status_code=400, detail="Ya existe otro producto con ese código en este taller")
    for field, value in update_data.items():
        setattr(product, field, value)
    db.commit(); db.refresh(product)
    return serialize_product(product)

@router.delete("/{product_id}")
def deactivate_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_inventory_enabled(db, current_user)
    product = db.query(InventoryProduct).filter(
        InventoryProduct.id == product_id,
        InventoryProduct.workshop_id == current_user.workshop_id,
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    product.is_active = False
    db.commit()
    return {"message": "Producto desactivado correctamente"}

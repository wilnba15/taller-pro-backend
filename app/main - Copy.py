from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine

# =========================
# MODELOS
# =========================

from app.models.workshop import Workshop  # noqa: F401
from app.models.client import Client  # noqa: F401
from app.models.vehicle import Vehicle  # noqa: F401
from app.models.work_order import WorkOrder  # noqa: F401
from app.models.work_order_photo import WorkOrderPhoto  # noqa: F401
from app.models.work_order_item import WorkOrderItem  # noqa: F401
from app.models.inventory_product import InventoryProduct  # noqa: F401
from app.models.user import User  # noqa: F401

# Facturación
from app.models.sri_setting import SriSetting  # noqa: F401
from app.models.invoice import Invoice  # noqa: F401
from app.models.invoice_item import InvoiceItem  # noqa: F401

# SWM Care
from app.models.swm_user import SwmUser  # noqa: F401
from app.models.swm import (
    SwmAiQuery,
    SwmFuelRecord,
    SwmMaintenanceSchedule,
    SwmServiceOrder,
    SwmServiceRecord,
    SwmVehicle,
)  # noqa: F401


# =========================
# ROUTERS
# =========================

from app.routers.workshops import router as workshops_router
from app.routers.clients import router as clients_router
from app.routers.vehicles import router as vehicles_router
from app.routers.work_orders import router as work_orders_router
from app.routers.work_order_photos import router as work_order_photos_router
from app.routers.work_order_items import router as work_order_items_router
from app.routers.auth import router as auth_router
from app.routers.ai_mechanic import router as ai_mechanic_router

from app.routers.swm import router as swm_router
from app.routers.swm_auth import router as swm_auth_router
from app.routers.swm_ai import router as swm_ai_router

from app.routers.vehicle_life_report import router as vehicle_life_router
from app.routers.reminders import router as reminders_router
from app.routers.admin import router as admin_router
from app.routers.inventory import router as inventory_router

# Facturación
from app.routers.invoices import router as invoices_router


# =========================
# CREAR TABLAS
# =========================

Base.metadata.create_all(bind=engine)


# =========================
# FASTAPI
# =========================

app = FastAPI(
    title="Taller PRO API + SWM Care",
    version="1.4.0",
)


# =========================
# CORS
# =========================

origins = [
    "http://localhost:3000",
    "https://taller-pro-frontend.vercel.app",
    "https://swm-care.vercel.app",
    "https://swm-care-mobile.vercel.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================
# REGISTRAR ROUTERS
# =========================

app.include_router(workshops_router)
app.include_router(clients_router)
app.include_router(vehicles_router)
app.include_router(work_orders_router)
app.include_router(work_order_photos_router)
app.include_router(work_order_items_router)
app.include_router(auth_router)
app.include_router(ai_mechanic_router)

app.include_router(swm_auth_router)
app.include_router(swm_ai_router)
app.include_router(swm_router)

app.include_router(vehicle_life_router)
app.include_router(reminders_router)
app.include_router(admin_router)
app.include_router(inventory_router)

# Facturación
app.include_router(invoices_router)


# =========================
# ROOT
# =========================

@app.get("/")
def root():
    return {
        "message": "Taller PRO API y SWM Care funcionando",
        "docs": "/docs",
    }
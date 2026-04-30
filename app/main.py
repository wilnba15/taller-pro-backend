from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine

from app.models.workshop import Workshop  # noqa: F401
from app.models.client import Client  # noqa: F401
from app.models.vehicle import Vehicle  # noqa: F401
from app.models.work_order import WorkOrder  # noqa: F401
from app.models.work_order_photo import WorkOrderPhoto
from app.models.work_order_item import WorkOrderItem  # noqa: F401

from app.routers.workshops import router as workshops_router
from app.routers.clients import router as clients_router
from app.routers.vehicles import router as vehicles_router
from app.routers.work_orders import router as work_orders_router
from app.routers.work_order_photos import router as work_order_photos_router
from app.routers.work_order_items import router as work_order_items_router

# 🔥 NUEVO IMPORT IA
from app.routers.ai_mechanic import router as ai_mechanic_router

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Taller PRO API",
    version="1.0.0",
)

origins = [
    "http://localhost:3000",
    "https://tallerpro-frontend.vercel.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(workshops_router)
app.include_router(clients_router)
app.include_router(vehicles_router)
app.include_router(work_orders_router)
app.include_router(work_order_photos_router)
app.include_router(work_order_items_router)

# 🔥 NUEVO ROUTER IA
app.include_router(ai_mechanic_router)

@app.get("/")
def root():
    return {"message": "Taller PRO API funcionando"}

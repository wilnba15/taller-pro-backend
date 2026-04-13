from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine

# Importar los modelos UNA sola vez
from app.models.workshop import Workshop  # noqa: F401
from app.models.client import Client  # noqa: F401
from app.models.vehicle import Vehicle  # noqa: F401
from app.models.work_order import WorkOrder  # noqa: F401
from app.models.work_order_photo import WorkOrderPhoto

from app.routers.workshops import router as workshops_router
from app.routers.clients import router as clients_router
from app.routers.vehicles import router as vehicles_router
from app.routers.work_orders import router as work_orders_router
from app.routers.work_order_photos import router as work_order_photos_router

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Taller PRO API",
    version="1.0.0",
    description="API multi-tenant para la administración de talleres automotrices",
)

# CORS para desarrollo local + frontend desplegado
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://tallerpro-frontend.vercel.app",  # cámbialo por tu dominio real cuando deployes
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


@app.get("/")
def root():
    return {"message": "Taller PRO API multi-tenant funcionando correctamente"}

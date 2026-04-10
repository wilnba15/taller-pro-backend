from fastapi import FastAPI
from app.database import Base, engine

# Importar los modelos UNA sola vez
from app.models.workshop import Workshop
from app.models.client import Client
from app.models.vehicle import Vehicle
from app.models.work_order import WorkOrder

from app.routers.workshops import router as workshops_router
from app.routers.clients import router as clients_router
from app.routers.vehicles import router as vehicles_router
from app.routers.work_orders import router as work_orders_router

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Taller PRO API",
    version="1.0.0",
    description="API multi-tenant para la administración de talleres automotrices"
)

app.include_router(workshops_router)
app.include_router(clients_router)
app.include_router(vehicles_router)
app.include_router(work_orders_router)


@app.get("/")
def root():
    return {"message": "Taller PRO API multi-tenant funcionando correctamente"}
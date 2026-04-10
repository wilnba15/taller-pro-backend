from fastapi import FastAPI
from app.database import Base, engine
from app.models import workshop, client, vehicle, work_order
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
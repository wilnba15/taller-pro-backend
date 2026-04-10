from fastapi import FastAPI
from app.database import Base, engine
from app.models import client, vehicle, work_order
from app.routers.clients import router as clients_router
from app.routers.vehicles import router as vehicles_router
from app.routers.work_orders import router as work_orders_router

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Taller PRO API",
    version="1.0.0",
    description="API para la administración de un taller automotriz"
)

app.include_router(clients_router)
app.include_router(vehicles_router)
app.include_router(work_orders_router)


@app.get("/")
def root():
    return {"message": "Taller PRO API funcionando correctamente"}
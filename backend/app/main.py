from fastapi import FastAPI
from app.core.config import settings
from app.db.session import engine
from app.db.base import Base
from app.models.service import Service  
from app.models.customer import Customer  
from app.models.tenant import Tenant 
from app.models.user import User      
from app.models.branch import Branch  
from app.models.appointment import Appointment  
from app.models.appointment_service import AppointmentService 
from app.models.staff import Staff  
from app.models.payment import Payment  # noqa: F401
from app.models.payment_event import PaymentEvent  # noqa: F401
from app.api.v1.router import api_router


app = FastAPI(title="SmartServeAI")


app.include_router(api_router, prefix="/api/v1")

@app.on_event("startup")
def startup():
    # Temporary for local dev: create tables automatically (no Alembic needed right now)
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health():
    return {"ok": True}

from fastapi import APIRouter
from app.api.v1 import auth, branches, services, customers, appointments, staff
router = APIRouter(prefix="/api/v1")
router.include_router(auth.router, tags=["auth"])
router.include_router(branches.router, tags=["branches"])
router.include_router(services.router, tags=["services"])
router.include_router(customers.router, tags=["customers"])
router.include_router(appointments.router, tags=["appointments"])
router.include_router(staff.router, tags=["staff"])


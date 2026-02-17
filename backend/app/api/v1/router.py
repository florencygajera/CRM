
from fastapi import APIRouter

from app.api.v1 import auth, branches, services, customers, appointments, staff, reports
from app.api.v1.payments import router as payments_router

api_router = APIRouter()

# Auth / Users
api_router.include_router(auth.router, tags=["auth"])

# Core SaaS modules
api_router.include_router(branches.router, tags=["branches"])
api_router.include_router(services.router, tags=["services"])
api_router.include_router(customers.router, tags=["customers"])
api_router.include_router(appointments.router, tags=["appointments"])
api_router.include_router(staff.router, tags=["staff"])
api_router.include_router(reports.router, tags=["reports"])

# Payments (Razorpay / Stripe)
api_router.include_router(payments_router, tags=["payments"])

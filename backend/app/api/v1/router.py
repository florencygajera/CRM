
from fastapi import APIRouter
from app.core.deps import get_db
from app.api.v1 import auth, branches, services, customers, appointment, staff, reports
from app.api.v1.payments import router as payments_router
from app.schemas.payment import RazorpayVerifyOut, RefundOut

api_router = APIRouter()

# Auth / Users
api_router.include_router(auth.router, tags=["auth"])

# Core SaaS modules
api_router.include_router(branches.router, tags=["branches"])
api_router.include_router(services.router, tags=["services"])
api_router.include_router(customers.router, tags=["customers"])
api_router.include_router(appointment.router, tags=["appointments"])
api_router.include_router(staff.router, tags=["staff"])
api_router.include_router(reports.router, tags=["reports"])

# Payments (Razorpay / Stripe)
api_router.include_router(payments_router, tags=["payments"])

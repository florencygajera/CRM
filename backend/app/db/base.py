from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

from app.models.tenant import Tenant  # noqa
from app.models.user import User  # noqa
from app.models.branch import Branch  # noqa
from app.models.service import Service  # noqa
from app.models.customer import Customer  # noqa
from app.models.staff import Staff  # noqa
from app.models.appointment import Appointment  # noqa
from app.models.appointment_service import AppointmentService  # noqa
from app.models.payment import Payment  # noqa
from app.models.payment_event import PaymentEvent  # noqa
 # noqa

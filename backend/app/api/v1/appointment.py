import uuid
from datetime import datetime, timedelta, time
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.staff import Staff
from app.core.deps import get_db, get_token_payload, get_branch_id
from app.models.appointment import Appointment, AppointmentStatus
from app.models.service import Service
from app.models.appointment_service import AppointmentService
from app.schemas.appointment import AppointmentCreateIn, AppointmentPatchIn
from app.models.customer import Customer
from app.workers.tasks import send_booking_email

router = APIRouter(prefix="/appointments")


def _calc_total_duration_min(services: list[Service]) -> int:
    return sum(int(s.duration_min) for s in services)


def _overlap_exists(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    branch_id: uuid.UUID,
    staff_user_id: uuid.UUID,
    start_at: datetime,
    end_at: datetime,
    exclude_id: uuid.UUID | None = None,
) -> bool:
    stmt = select(Appointment.id).where(
        Appointment.tenant_id == tenant_id,
        Appointment.branch_id == branch_id,
        Appointment.staff_user_id == staff_user_id,
        Appointment.status != AppointmentStatus.CANCELLED,
        Appointment.start_at < end_at,
        Appointment.end_at > start_at,
    )
    if exclude_id:
        stmt = stmt.where(Appointment.id != exclude_id)
    return db.scalar(stmt) is not None


@router.get("/availability")
def availability(
    staff_user_id: str = Query(...),
    service_ids: list[str] = Query(...),
    day: str = Query(..., description="YYYY-MM-DD"),
    slot_step_min: int = Query(15, ge=5, le=60),
    db: Session = Depends(get_db),
    payload: dict = Depends(get_token_payload),
    branch_id: uuid.UUID = Depends(get_branch_id),
):
    """
    Returns available start times for a staff on a given day (branch-scoped).
    Uses staff working hours (work_start_time/work_end_time).
    """
    tenant_id = uuid.UUID(payload["tenant_id"])
    staff_uuid = uuid.UUID(staff_user_id)

    try:
        day_date = datetime.fromisoformat(day).date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid day format. Use YYYY-MM-DD")

    svc_uuids = [uuid.UUID(s) for s in service_ids]
    services = db.scalars(
        select(Service).where(
            Service.tenant_id == tenant_id,
            Service.id.in_(svc_uuids),
            Service.is_active == True,
        )
    ).all()
    if len(services) != len(svc_uuids):
        raise HTTPException(status_code=400, detail="One or more services not found")

    duration_min = _calc_total_duration_min(services)

    staff = db.scalar(
        select(Staff).where(
            Staff.tenant_id == tenant_id,
            Staff.id == staff_uuid,
            # If staff is branch-scoped in your DB, uncomment:
            # Staff.branch_id == branch_id,
        )
    )
    if not staff:
        raise HTTPException(status_code=404, detail="Staff not found")

    start_hour, start_min = map(int, staff.work_start_time.split(":"))
    end_hour, end_min = map(int, staff.work_end_time.split(":"))

    start_work = datetime.combine(day_date, time(start_hour, start_min))
    end_work = datetime.combine(day_date, time(end_hour, end_min))

    day_start = datetime.combine(day_date, time(0, 0))
    day_end = datetime.combine(day_date, time(23, 59, 59))

    existing = db.scalars(
        select(Appointment).where(
            Appointment.tenant_id == tenant_id,
            Appointment.branch_id == branch_id,
            Appointment.staff_user_id == staff_uuid,
            Appointment.status != AppointmentStatus.CANCELLED,
            Appointment.start_at >= day_start,
            Appointment.start_at <= day_end,
        )
    ).all()

    busy = [(a.start_at, a.end_at) for a in existing]

    slots: list[str] = []
    cursor = start_work
    while cursor + timedelta(minutes=duration_min) <= end_work:
        cand_start = cursor
        cand_end = cursor + timedelta(minutes=duration_min)

        conflict = False
        for bs, be in busy:
            if bs < cand_end and be > cand_start:
                conflict = True
                break

        if not conflict:
            slots.append(cand_start.isoformat())

        cursor += timedelta(minutes=slot_step_min)

    return {"success": True, "data": {"duration_min": duration_min, "slots": slots}}


@router.post("")
def create_appointment(
    body: AppointmentCreateIn,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_token_payload),
    branch_id: uuid.UUID = Depends(get_branch_id),
):
    tenant_id = uuid.UUID(payload["tenant_id"])

    staff_uuid = uuid.UUID(body.staff_user_id)
    customer_uuid = uuid.UUID(body.customer_id)

    svc_uuids = [uuid.UUID(s) for s in body.service_ids]
    services = db.scalars(
        select(Service).where(
            Service.tenant_id == tenant_id,
            Service.id.in_(svc_uuids),
            Service.is_active == True,
        )
    ).all()
    if len(services) != len(svc_uuids):
        raise HTTPException(status_code=400, detail="One or more services not found")

    duration_min = _calc_total_duration_min(services)
    end_time = body.start_at + timedelta(minutes=duration_min)

    # Double-book prevention (branch-scoped)
    if _overlap_exists(
        db,
        tenant_id=tenant_id,
        branch_id=branch_id,
        staff_user_id=staff_uuid,
        start_at=body.start_at,
        end_at=end_time,
    ):
        raise HTTPException(status_code=400, detail="Time slot already booked")

    appt = Appointment(
        tenant_id=tenant_id,
        branch_id=branch_id,  # ✅ REQUIRED
        customer_id=customer_uuid,
        staff_user_id=staff_uuid,
        start_at=body.start_at,
        end_at=end_time,
        status=AppointmentStatus.CONFIRMED,
        notes=body.notes,
    )
    db.add(appt)
    db.flush()  # get appt.id

    # Save service snapshots for this appointment
    for s in services:
        db.add(
            AppointmentService(
                tenant_id=tenant_id,
                appointment_id=appt.id,
                service_id=s.id,
                price_snapshot=float(s.price),
                duration_snapshot_min=int(s.duration_min),
            )
        )

    db.commit()
    db.refresh(appt)

    # Email after commit
    customer = db.scalar(
        select(Customer).where(
            Customer.tenant_id == tenant_id,
            Customer.id == customer_uuid,
            # If customers are branch-scoped, uncomment:
            # Customer.branch_id == branch_id,
        )
    )

    if customer and getattr(customer, "email", None):
        subject = "Booking Confirmed ✅"
        email_body = (
            "Your appointment is confirmed.\n"
            f"Start: {appt.start_at}\n"
            f"End: {appt.end_at}\n"
            f"Status: {appt.status}"
        )

        # send immediately
        send_booking_email.delay(customer.email, subject, email_body)

        # reminder 24 hours before
        reminder_time = appt.start_at - timedelta(hours=24)
        # schedule only if reminder is in the future
        if reminder_time > datetime.utcnow():
            send_booking_email.apply_async(
                args=[customer.email, "Appointment Reminder ⏰", email_body],
                eta=reminder_time,
            )

    return {"success": True, "data": {"id": str(appt.id), "start_at": appt.start_at, "end_at": appt.end_at, "status": appt.status}}


@router.patch("/{appointment_id}")
def patch_appointment(
    appointment_id: str,
    body: AppointmentPatchIn,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_token_payload),
    branch_id: uuid.UUID = Depends(get_branch_id),
):
    tenant_id = uuid.UUID(payload["tenant_id"])
    appt_id = uuid.UUID(appointment_id)

    appt = db.scalar(
        select(Appointment).where(
            Appointment.tenant_id == tenant_id,
            Appointment.branch_id == branch_id,  # ✅ enforce branch
            Appointment.id == appt_id,
        )
    )
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found")

    # cancel
    if body.status == AppointmentStatus.CANCELLED:
        appt.status = AppointmentStatus.CANCELLED

    # reschedule
    if body.start_at is not None:
        new_start = body.start_at
        duration = int((appt.end_at - appt.start_at).total_seconds() // 60)
        new_end = new_start + timedelta(minutes=duration)

        if _overlap_exists(
            db,
            tenant_id=tenant_id,
            branch_id=branch_id,
            staff_user_id=appt.staff_user_id,
            start_at=new_start,
            end_at=new_end,
            exclude_id=appt.id,
        ):
            raise HTTPException(status_code=400, detail="Time slot already booked")

        appt.start_at = new_start
        appt.end_at = new_end

    if body.notes is not None:
        appt.notes = body.notes

    db.commit()
    db.refresh(appt)

    return {"success": True, "data": {"id": str(appt.id), "start_at": appt.start_at, "end_at": appt.end_at, "status": appt.status}}


@router.get("/")
def list_appointments(
    db: Session = Depends(get_db),
    payload: dict = Depends(get_token_payload),
    branch_id: uuid.UUID = Depends(get_branch_id),
):
    tenant_id = uuid.UUID(payload["tenant_id"])
    q = select(Appointment).where(
        Appointment.tenant_id == tenant_id,
        Appointment.branch_id == branch_id,
    ).order_by(Appointment.start_at.desc())
    return db.scalars(q).all()

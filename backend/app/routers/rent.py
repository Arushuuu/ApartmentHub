"""Tenant rent history and admin-managed monthly rent ledger."""

from calendar import monthrange
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import LeaseAgreement, RentPayment, RentShare, Tenant
from app.rent_ledger import add_payment_shares, change_rent_status, rent_payment_view, rent_share_view
from app.routers.admin import require_admin
from app.routers.auth import get_current_tenant

tenant_router = APIRouter(prefix="/rent", tags=["Rent"])
admin_router = APIRouter(prefix="/admin/rent", tags=["Rent ledger"])


class RentMonthCreate(BaseModel):
    billing_month: date
    lease_id: int | None = Field(default=None, gt=0)


class RentReportInput(BaseModel):
    reference: str = Field(default="", max_length=100)


class RentStatusInput(BaseModel):
    payment_status: Literal["Paid", "Unpaid"]
    note: str = Field(default="", max_length=500)


@tenant_router.get("/me")
def my_rent(current_tenant: Tenant = Depends(get_current_tenant), db: Session = Depends(get_db)):
    shares = (db.query(RentShare).join(RentPayment)
              .filter(RentShare.tenant_id == current_tenant.tenant_id)
              .order_by(RentPayment.billing_month.desc(), RentShare.share_id.desc()).all())
    return [{**rent_share_view(share), "billing_month": share.payment.billing_month,
             "lease_id": share.payment.lease_id, "full_rent": share.payment.amount,
             "unit_label": f"{share.payment.lease.unit.building_name} · Unit {share.payment.lease.unit.unit_no}"}
            for share in shares]


@tenant_router.patch("/shares/{share_id}/report-payment")
def report_rent_payment(share_id: int, payload: RentReportInput,
                        current_tenant: Tenant = Depends(get_current_tenant), db: Session = Depends(get_db)):
    share = (db.query(RentShare).filter(RentShare.share_id == share_id,
                                       RentShare.tenant_id == current_tenant.tenant_id)
             .with_for_update().first())
    if share is None:
        raise HTTPException(status_code=404, detail="Rent share not found")
    if share.payment_status != "Unpaid":
        db.rollback()
        raise HTTPException(status_code=409, detail="Only an unpaid rent share can be reported")
    reference = payload.reference.strip()
    note = "Tenant reported offline rent payment; awaiting admin verification"
    if reference:
        note += f". Reference: {reference}"
    change_rent_status(db, share, "Pending Verification", current_tenant.tenant_name, note)
    db.commit()
    db.refresh(share)
    return rent_share_view(share)


@admin_router.get("/months")
def list_rent_months(lease_id: int | None = None, db: Session = Depends(get_db),
                     _: Tenant = Depends(require_admin)):
    query = db.query(RentPayment)
    if lease_id is not None:
        query = query.filter(RentPayment.lease_id == lease_id)
    payments = query.order_by(RentPayment.billing_month.desc(), RentPayment.payment_id.desc()).limit(500).all()
    return [rent_payment_view(payment) for payment in payments]


@admin_router.post("/months", status_code=status.HTTP_201_CREATED)
def generate_rent_month(payload: RentMonthCreate, db: Session = Depends(get_db),
                        _: Tenant = Depends(require_admin)):
    month = payload.billing_month
    if month.day != 1:
        raise HTTPException(status_code=400, detail="Billing month must be the first day of a month")
    last_day = month.replace(day=monthrange(month.year, month.month)[1])
    query = db.query(LeaseAgreement).filter(LeaseAgreement.start_date <= last_day,
                                            LeaseAgreement.end_date >= month)
    if payload.lease_id is not None:
        query = query.filter(LeaseAgreement.lease_id == payload.lease_id)
    leases = query.order_by(LeaseAgreement.lease_id).all()
    if payload.lease_id is not None and not leases:
        raise HTTPException(status_code=404, detail="Lease is not active in that month")
    created = 0
    imported = 0
    try:
        for lease in leases:
            payment = (db.query(RentPayment).filter(RentPayment.lease_id == lease.lease_id,
                                                    RentPayment.billing_month == month).first())
            if payment is None:
                payment = RentPayment(lease_id=lease.lease_id, billing_month=month,
                                      amount=lease.monthly_rent, payment_status="Pending")
                db.add(payment)
                db.flush()
                add_payment_shares(db, payment)
                created += 1
            elif not payment.shares:
                add_payment_shares(db, payment, imported=True)
                imported += 1
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"billing_month": month, "created": created, "existing": len(leases) - created,
            "imported_existing": imported}


@admin_router.patch("/shares/{share_id}/status")
def update_rent_status(share_id: int, payload: RentStatusInput,
                       db: Session = Depends(get_db), current_admin: Tenant = Depends(require_admin)):
    share = db.query(RentShare).filter(RentShare.share_id == share_id).with_for_update().first()
    if share is None:
        raise HTTPException(status_code=404, detail="Rent share not found")
    if share.payment_status == payload.payment_status:
        db.rollback()
        raise HTTPException(status_code=409, detail="Rent share already has that status")
    note = payload.note.strip() or ("Offline rent payment verified by admin" if payload.payment_status == "Paid"
                                    else "Rent payment returned to unpaid by admin")
    change_rent_status(db, share, payload.payment_status, current_admin.tenant_name, note)
    db.commit()
    db.refresh(share)
    return rent_payment_view(share.payment)

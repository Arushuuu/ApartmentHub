"""Admin-managed lease signatories and per-tenant deposit accounting."""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.lease_service import lease_tenant_ids, lease_view
from app.models import ApartmentUnit, DepositContribution, DepositLedgerEntry, LeaseAgreement, LeaseSignatory, SecurityDeposit, Tenant
from app.routers.admin import require_admin

router = APIRouter(prefix="/admin/shared-leases", tags=["Shared leases"])


class SharedLeaseCreate(BaseModel):
    unit_id: int = Field(gt=0)
    primary_tenant_id: int = Field(gt=0)
    start_date: date
    end_date: date
    monthly_rent: Decimal = Field(gt=0, max_digits=10, decimal_places=2)


class SignatoryAdd(BaseModel):
    tenant_id: int = Field(gt=0)


class ContributionAdd(BaseModel):
    tenant_id: int = Field(gt=0)
    amount: Decimal = Field(gt=0, max_digits=10, decimal_places=2)


class RefundAdd(ContributionAdd):
    note: str = Field(default="", max_length=500)


class RefundReconcile(BaseModel):
    tenant_id: int = Field(gt=0)
    refunded_amount: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    note: str = Field(default="", max_length=500)


def require_lease(db: Session, lease_id: int):
    lease = db.get(LeaseAgreement, lease_id)
    if lease is None:
        raise HTTPException(status_code=404, detail="Lease not found")
    return lease


def update_refund_status(deposit: SecurityDeposit):
    attributed = sum((row.contributed_amt for row in deposit.contributions), Decimal("0.00"))
    if attributed != deposit.amount_held or any(row.refunded_amt is None for row in deposit.contributions):
        return  # Legacy partial refunds need an admin-entered historical amount.
    refunded = sum((row.refunded_amt for row in deposit.contributions), Decimal("0.00"))
    if refunded == 0:
        deposit.refund_status = "Held"
    elif refunded >= deposit.amount_held:
        deposit.refund_status = "Fully Refunded"
    else:
        deposit.refund_status = "Partial Refund"


@router.get("")
def list_shared_leases(db: Session = Depends(get_db), _: Tenant = Depends(require_admin)):
    leases = db.query(LeaseAgreement).order_by(LeaseAgreement.lease_id.desc()).all()
    return [lease_view(lease) for lease in leases]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_shared_lease(payload: SharedLeaseCreate, db: Session = Depends(get_db), _: Tenant = Depends(require_admin)):
    if db.get(ApartmentUnit, payload.unit_id) is None:
        raise HTTPException(status_code=404, detail="Apartment unit not found")
    if db.get(Tenant, payload.primary_tenant_id) is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    if payload.end_date < payload.start_date:
        raise HTTPException(status_code=400, detail="Lease end date must follow its start date")
    try:
        lease = LeaseAgreement(unit_id=payload.unit_id, tenant_id=payload.primary_tenant_id,
                               start_date=payload.start_date, end_date=payload.end_date,
                               monthly_rent=payload.monthly_rent)
        db.add(lease)
        db.flush()
        db.add(LeaseSignatory(lease_id=lease.lease_id, tenant_id=payload.primary_tenant_id))
        db.commit()
        db.refresh(lease)
    except Exception:
        db.rollback()
        raise
    return lease_view(lease)


@router.post("/{lease_id}/signatories", status_code=status.HTTP_201_CREATED)
def add_signatory(lease_id: int, payload: SignatoryAdd, db: Session = Depends(get_db), _: Tenant = Depends(require_admin)):
    lease = require_lease(db, lease_id)
    if db.get(Tenant, payload.tenant_id) is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    if payload.tenant_id in lease_tenant_ids(lease):
        raise HTTPException(status_code=409, detail="Tenant already signs this lease")
    db.add(LeaseSignatory(lease_id=lease_id, tenant_id=payload.tenant_id))
    db.commit()
    db.refresh(lease)
    return lease_view(lease)


@router.post("/{lease_id}/contributions", status_code=status.HTTP_201_CREATED)
def add_contribution(lease_id: int, payload: ContributionAdd, db: Session = Depends(get_db),
                     current_admin: Tenant = Depends(require_admin)):
    lease = require_lease(db, lease_id)
    if payload.tenant_id not in lease_tenant_ids(lease):
        raise HTTPException(status_code=400, detail="Tenant must sign this lease before contributing")
    try:
        deposit = (db.query(SecurityDeposit).filter(SecurityDeposit.lease_id == lease_id)
                   .with_for_update().first())
        if deposit is None:
            deposit = SecurityDeposit(lease_id=lease_id, amount_held=Decimal("0.00"), refund_status="Held")
            db.add(deposit)
            db.flush()
        contribution = (db.query(DepositContribution)
                        .filter(DepositContribution.deposit_id == deposit.deposit_id,
                                DepositContribution.tenant_id == payload.tenant_id)
                        .with_for_update().first())
        if contribution is None:
            contribution = DepositContribution(deposit_id=deposit.deposit_id, tenant_id=payload.tenant_id,
                                               contributed_amt=Decimal("0.00"), refunded_amt=Decimal("0.00"))
            db.add(contribution)
        attributed = sum((row.contributed_amt for row in deposit.contributions), Decimal("0.00"))
        unattributed = max(deposit.amount_held - attributed, Decimal("0.00"))
        allocated = min(payload.amount, unattributed)
        newly_contributed = payload.amount - allocated
        contribution.contributed_amt += payload.amount
        deposit.amount_held += newly_contributed
        if allocated:
            db.add(DepositLedgerEntry(deposit_id=deposit.deposit_id, tenant_id=payload.tenant_id,
                                      action="Allocation", amount=allocated,
                                      recorded_by=current_admin.tenant_name,
                                      note="Existing recorded deposit attributed to this signatory"))
        if newly_contributed:
            db.add(DepositLedgerEntry(deposit_id=deposit.deposit_id, tenant_id=payload.tenant_id,
                                      action="Contribution", amount=newly_contributed,
                                      recorded_by=current_admin.tenant_name, note="New deposit contribution recorded"))
        db.flush()
        update_refund_status(deposit)
        db.commit()
        db.refresh(lease)
    except Exception:
        db.rollback()
        raise
    return lease_view(lease)


@router.post("/{lease_id}/refunds", status_code=status.HTTP_201_CREATED)
def record_refund(lease_id: int, payload: RefundAdd, db: Session = Depends(get_db),
                  current_admin: Tenant = Depends(require_admin)):
    lease = require_lease(db, lease_id)
    deposit = (db.query(SecurityDeposit).filter(SecurityDeposit.lease_id == lease_id)
               .with_for_update().first())
    if deposit is None:
        raise HTTPException(status_code=404, detail="Lease has no deposit")
    contribution = (db.query(DepositContribution)
                    .filter(DepositContribution.deposit_id == deposit.deposit_id,
                            DepositContribution.tenant_id == payload.tenant_id)
                    .with_for_update().first())
    if contribution is None:
        raise HTTPException(status_code=404, detail="Tenant has no deposit contribution")
    if contribution.refunded_amt is None:
        raise HTTPException(status_code=409, detail="Reconcile this historical partial refund before recording another refund")
    if sum((row.contributed_amt for row in deposit.contributions), Decimal("0.00")) != deposit.amount_held:
        raise HTTPException(status_code=409, detail="Attribute the full recorded deposit before issuing refunds")
    if payload.amount > contribution.contributed_amt - contribution.refunded_amt:
        raise HTTPException(status_code=400, detail="Refund exceeds this tenant's remaining contribution")
    try:
        contribution.refunded_amt += payload.amount
        db.add(DepositLedgerEntry(deposit_id=deposit.deposit_id, tenant_id=payload.tenant_id,
                                  action="Refund", amount=payload.amount,
                                  recorded_by=current_admin.tenant_name,
                                  note=payload.note.strip() or "Deposit refund recorded"))
        db.flush()
        update_refund_status(deposit)
        db.commit()
        db.refresh(lease)
    except Exception:
        db.rollback()
        raise
    return lease_view(lease)


@router.patch("/{lease_id}/reconcile-refund")
def reconcile_refund(lease_id: int, payload: RefundReconcile, db: Session = Depends(get_db),
                     current_admin: Tenant = Depends(require_admin)):
    lease = require_lease(db, lease_id)
    deposit = (db.query(SecurityDeposit).filter(SecurityDeposit.lease_id == lease_id)
               .with_for_update().first())
    if deposit is None:
        raise HTTPException(status_code=404, detail="Lease has no deposit")
    contribution = (db.query(DepositContribution)
                    .filter(DepositContribution.deposit_id == deposit.deposit_id,
                            DepositContribution.tenant_id == payload.tenant_id)
                    .with_for_update().first())
    if contribution is None or contribution.refunded_amt is not None:
        raise HTTPException(status_code=409, detail="No unknown historical refund for this tenant")
    if payload.refunded_amount > contribution.contributed_amt:
        raise HTTPException(status_code=400, detail="Historical refund exceeds contribution")
    try:
        contribution.refunded_amt = payload.refunded_amount
        db.add(DepositLedgerEntry(deposit_id=deposit.deposit_id, tenant_id=payload.tenant_id,
                                  action="Reconciliation", amount=payload.refunded_amount,
                                  recorded_by=current_admin.tenant_name,
                                  note=payload.note.strip() or "Historical refund total reconciled"))
        db.flush()
        update_refund_status(deposit)
        db.commit()
        db.refresh(lease)
    except Exception:
        db.rollback()
        raise
    return lease_view(lease)

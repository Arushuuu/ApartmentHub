from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ApartmentUnit, BillSplitShare, DepositContribution, DepositLedgerEntry, LeaseAgreement, LeaseSignatory, MaintenanceTicket, RentPayment, RentShare, SecurityDeposit
from app.lease_service import lease_tenant_ids, tenant_leases_query
from app.rent_ledger import split_amount
from app.routers.auth import get_current_tenant
from app.schemas import AccountSetup

router = APIRouter(prefix="/account", tags=["Account"])

@router.get("/dashboard")
def dashboard(current_tenant=Depends(get_current_tenant), db: Session = Depends(get_db)):
    tenant_id = current_tenant.tenant_id
    active_lease = (tenant_leases_query(db, tenant_id)
        .order_by(LeaseAgreement.end_date.desc()).first())
    due = db.query(func.coalesce(func.sum(BillSplitShare.owed_amt), 0)).filter(BillSplitShare.tenant_id == tenant_id, BillSplitShare.payment_status != "Paid").scalar()
    open_tickets = db.query(func.count(MaintenanceTicket.ticket_id)).filter(MaintenanceTicket.tenant_id == tenant_id, MaintenanceTicket.status.in_(["Open", "In Progress"])).scalar()
    my_rent_share = 0
    if active_lease:
        current_month = date.today().replace(day=1)
        billed_share = (db.query(RentShare).join(RentPayment)
                        .filter(RentPayment.lease_id == active_lease.lease_id,
                                RentPayment.billing_month == current_month,
                                RentShare.tenant_id == tenant_id).first())
        if billed_share:
            my_rent_share = billed_share.owed_amt
        else:
            my_rent_share = next((amount for member_id, amount in split_amount(active_lease.monthly_rent, lease_tenant_ids(active_lease))
                                  if member_id == tenant_id), 0)
    return {"tenant_name": current_tenant.tenant_name, "monthly_rent": active_lease.monthly_rent if active_lease else 0,
            "my_rent_share": my_rent_share, "utilities_due": due, "open_tickets": open_tickets,
            "lease_end": active_lease.end_date if active_lease else None}

@router.post("/setup")
def complete_setup(payload: AccountSetup, current_tenant=Depends(get_current_tenant), db: Session = Depends(get_db)):
    unit = db.get(ApartmentUnit, payload.existing_unit_id) if payload.existing_unit_id else None
    if payload.existing_unit_id and unit is None:
        return {"message": "Unit ID was not found", "created": False}
    unit_values = [payload.building_name, payload.street, payload.unit_no, payload.pincode, payload.base_rent]
    if unit is None and any(value is not None for value in unit_values):
        if not all(value is not None for value in unit_values):
            return {"message": "Complete every apartment field or leave that section blank", "created": False}
        unit = ApartmentUnit(building_name=payload.building_name, street=payload.street, unit_no=payload.unit_no, pincode=payload.pincode, base_rent=payload.base_rent)
        db.add(unit)
        db.flush()
    lease_values = [payload.start_date, payload.end_date, payload.monthly_rent]
    if any(value is not None for value in lease_values):
        if unit is None or not all(value is not None for value in lease_values):
            return {"message": "A lease needs a unit, both dates, and monthly rent", "created": False}
        lease = LeaseAgreement(unit_id=unit.unit_id, tenant_id=current_tenant.tenant_id, start_date=payload.start_date, end_date=payload.end_date, monthly_rent=payload.monthly_rent)
        db.add(lease)
        db.flush()
        db.add(LeaseSignatory(lease_id=lease.lease_id, tenant_id=current_tenant.tenant_id))
        if payload.deposit_amount is not None and payload.deposit_amount < 0:
            raise HTTPException(status_code=400, detail="Security deposit cannot be negative")
        if payload.deposit_amount:
            deposit = SecurityDeposit(lease_id=lease.lease_id, amount_held=payload.deposit_amount, refund_status="Held")
            db.add(deposit)
            db.flush()
            db.add(DepositContribution(deposit_id=deposit.deposit_id, tenant_id=current_tenant.tenant_id,
                                       contributed_amt=payload.deposit_amount, refunded_amt=0))
            db.add(DepositLedgerEntry(deposit_id=deposit.deposit_id, tenant_id=current_tenant.tenant_id,
                                      action="Contribution", amount=payload.deposit_amount,
                                      recorded_by=current_tenant.tenant_name, note="Initial deposit at lease setup"))
    db.commit()
    return {"message": "Optional setup saved", "created": True, "unit_id": unit.unit_id if unit else None}

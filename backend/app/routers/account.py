from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ApartmentUnit, BillSplitShare, LeaseAgreement, MaintenanceTicket, SecurityDeposit
from app.routers.auth import get_current_tenant
from app.schemas import AccountSetup

router = APIRouter(prefix="/account", tags=["Account"])

@router.get("/dashboard")
def dashboard(current_tenant=Depends(get_current_tenant), db: Session = Depends(get_db)):
    tenant_id = current_tenant.tenant_id
    active_lease = (db.query(LeaseAgreement).filter(LeaseAgreement.tenant_id == tenant_id)
        .order_by(LeaseAgreement.end_date.desc()).first())
    due = db.query(func.coalesce(func.sum(BillSplitShare.owed_amt), 0)).filter(BillSplitShare.tenant_id == tenant_id, BillSplitShare.payment_status != "Paid").scalar()
    open_tickets = db.query(func.count(MaintenanceTicket.ticket_id)).filter(MaintenanceTicket.tenant_id == tenant_id, MaintenanceTicket.status.in_(["Open", "In Progress"])).scalar()
    return {"tenant_name": current_tenant.tenant_name, "monthly_rent": active_lease.monthly_rent if active_lease else 0, "utilities_due": due, "open_tickets": open_tickets, "lease_end": active_lease.end_date if active_lease else None}

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
        if payload.deposit_amount is not None:
            db.add(SecurityDeposit(lease_id=lease.lease_id, amount_held=payload.deposit_amount, refund_status="Held"))
    db.commit()
    return {"message": "Optional setup saved", "created": True, "unit_id": unit.unit_id if unit else None}

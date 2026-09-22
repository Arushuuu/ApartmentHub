from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import BillSplitShare, LeaseAgreement, MaintenanceTicket
from app.routers.auth import get_current_tenant

router = APIRouter(prefix="/account", tags=["Account"])

@router.get("/dashboard")
def dashboard(current_tenant=Depends(get_current_tenant), db: Session = Depends(get_db)):
    tenant_id = current_tenant.tenant_id
    active_lease = (db.query(LeaseAgreement).filter(LeaseAgreement.tenant_id == tenant_id)
        .order_by(LeaseAgreement.end_date.desc()).first())
    due = db.query(func.coalesce(func.sum(BillSplitShare.owed_amt), 0)).filter(BillSplitShare.tenant_id == tenant_id, BillSplitShare.payment_status != "Paid").scalar()
    open_tickets = db.query(func.count(MaintenanceTicket.ticket_id)).filter(MaintenanceTicket.tenant_id == tenant_id, MaintenanceTicket.status.in_(["Open", "In Progress"])).scalar()
    return {"tenant_name": current_tenant.tenant_name, "monthly_rent": active_lease.monthly_rent if active_lease else 0, "utilities_due": due, "open_tickets": open_tickets, "lease_end": active_lease.end_date if active_lease else None}

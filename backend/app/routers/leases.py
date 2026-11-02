from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import LeaseAgreement
from app.routers.auth import get_current_tenant
from app.lease_service import lease_view, tenant_leases_query

router = APIRouter(prefix="/leases", tags=["Leases"])

@router.get("/me")
def my_leases(current_tenant=Depends(get_current_tenant), db: Session = Depends(get_db)):
    leases = tenant_leases_query(db, current_tenant.tenant_id).order_by(LeaseAgreement.end_date.desc()).all()
    return [lease_view(lease) for lease in leases]

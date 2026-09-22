from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import LeaseAgreement
from app.routers.auth import get_current_tenant
from app.schemas import LeaseResponse

router = APIRouter(prefix="/leases", tags=["Leases"])

@router.get("/me", response_model=list[LeaseResponse])
def my_leases(current_tenant=Depends(get_current_tenant), db: Session = Depends(get_db)):
    return db.query(LeaseAgreement).filter(LeaseAgreement.tenant_id == current_tenant.tenant_id).order_by(LeaseAgreement.end_date.desc()).all()

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import BillSplitShare, UtilityBill
from app.routers.auth import get_current_tenant

router = APIRouter(prefix="/utilities", tags=["Utilities"])

@router.get("/me")
def my_utility_shares(current_tenant=Depends(get_current_tenant), db: Session = Depends(get_db)):
    rows = (db.query(BillSplitShare, UtilityBill)
        .join(UtilityBill, UtilityBill.bill_id == BillSplitShare.bill_id)
        .filter(BillSplitShare.tenant_id == current_tenant.tenant_id)
        .order_by(UtilityBill.due_date.desc()).all())
    return [{"share_id": share.share_id, "bill_id": share.bill_id, "owed_amt": share.owed_amt,
             "payment_status": share.payment_status, "bill_date": bill.bill_date, "due_date": bill.due_date,
             "total_amount": bill.total_amount} for share, bill in rows]

@router.patch("/{share_id}/mark-paid")
def mark_share_paid(share_id: int, current_tenant=Depends(get_current_tenant), db: Session = Depends(get_db)):
    share = db.query(BillSplitShare).filter(BillSplitShare.share_id == share_id, BillSplitShare.tenant_id == current_tenant.tenant_id).first()
    if share is None:
        raise HTTPException(status_code=404, detail="Utility share not found")
    share.payment_status = "Pending Verification"
    db.commit()
    return {"message": "Payment marked for verification"}

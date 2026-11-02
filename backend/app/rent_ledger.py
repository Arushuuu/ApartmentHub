"""Monthly rent shares and the audit trail for offline payments."""

from datetime import date
from decimal import Decimal

from fastapi import HTTPException

from app.lease_service import lease_tenant_ids
from app.models import RentPayment, RentPaymentLog, RentShare


def split_amount(amount: Decimal, tenant_ids: list[int]) -> list[tuple[int, Decimal]]:
    if not tenant_ids:
        raise HTTPException(status_code=400, detail="A lease needs a signatory before rent can be split")
    cents = int((amount * 100).to_integral_exact())
    if cents < len(tenant_ids):
        raise HTTPException(status_code=400, detail="Monthly rent is too small to split among all signatories")
    each, remainder = divmod(cents, len(tenant_ids))
    return [(tenant_id, Decimal(each + (index < remainder)) / 100)
            for index, tenant_id in enumerate(sorted(tenant_ids))]


def add_payment_shares(db, payment: RentPayment, imported: bool = False):
    if payment.shares:
        return
    tenant_ids = lease_tenant_ids(payment.lease)
    if imported and payment.payment_status == "Paid" and len(tenant_ids) > 1:
        raise HTTPException(status_code=409, detail="Cannot attribute an older shared rent payment to individual signatories automatically")
    for tenant_id, amount in split_amount(payment.amount, tenant_ids):
        initial_status = "Paid" if imported and payment.payment_status == "Paid" else "Unpaid"
        share = RentShare(payment_id=payment.payment_id, tenant_id=tenant_id,
                          owed_amt=amount, payment_status=initial_status,
                          paid_on=payment.paid_on if initial_status == "Paid" else None)
        db.add(share)
        db.flush()
        db.add(RentPaymentLog(share_id=share.share_id, previous_status=None,
                              new_status=initial_status, recorded_by="System import" if imported else "System",
                              note="Existing rent record imported; original payment evidence was not recorded"
                              if imported else "Monthly rent split among lease signatories"))


def change_rent_status(db, share: RentShare, new_status: str, actor: str, note: str):
    previous = share.payment_status
    share.payment_status = new_status
    share.paid_on = date.today() if new_status == "Paid" else None
    db.add(RentPaymentLog(share_id=share.share_id, previous_status=previous,
                          new_status=new_status, recorded_by=actor, note=note))
    db.flush()
    payment = share.payment
    payment.payment_status = "Paid" if payment.shares and all(row.payment_status == "Paid" for row in payment.shares) else "Pending"
    payment.paid_on = date.today() if payment.payment_status == "Paid" else None


def rent_share_view(share: RentShare):
    return {
        "share_id": share.share_id,
        "tenant_id": share.tenant_id,
        "tenant_name": share.tenant.tenant_name,
        "owed_amt": share.owed_amt,
        "payment_status": share.payment_status,
        "paid_on": share.paid_on,
        "ledger": [{"log_id": row.log_id, "previous_status": row.previous_status,
                    "new_status": row.new_status, "recorded_by": row.recorded_by,
                    "note": row.note, "created_at": row.created_at} for row in share.ledger],
    }


def rent_payment_view(payment: RentPayment):
    lease = payment.lease
    return {
        "payment_id": payment.payment_id,
        "lease_id": lease.lease_id,
        "unit_label": f"{lease.unit.building_name} · Unit {lease.unit.unit_no}",
        "billing_month": payment.billing_month,
        "amount": payment.amount,
        "payment_status": payment.payment_status,
        "paid_on": payment.paid_on,
        "shares": [rent_share_view(row) for row in payment.shares],
    }

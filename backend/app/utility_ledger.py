"""Shared serialization and status history for utility bill shares."""

from app.models import BillSplitShare, UtilityBill, UtilityPaymentLog


def ledger_view(entry: UtilityPaymentLog):
    return {
        "log_id": entry.log_id,
        "previous_status": entry.previous_status,
        "new_status": entry.new_status,
        "recorded_by": entry.recorded_by,
        "note": entry.note,
        "created_at": entry.created_at,
    }


def share_view(share: BillSplitShare):
    return {
        "share_id": share.share_id,
        "bill_id": share.bill_id,
        "tenant_id": share.tenant_id,
        "tenant_name": share.tenant.tenant_name,
        "owed_amt": share.owed_amt,
        "payment_status": share.payment_status,
        "ledger": [ledger_view(entry) for entry in share.ledger],
    }


def bill_view(bill: UtilityBill):
    return {
        "bill_id": bill.bill_id,
        "unit_id": bill.unit_id,
        "unit_label": f"{bill.unit.building_name} · Unit {bill.unit.unit_no}",
        "total_amount": bill.total_amount,
        "bill_date": bill.bill_date,
        "due_date": bill.due_date,
        "shares": [share_view(share) for share in sorted(bill.shares, key=lambda row: row.tenant_id)],
    }


def change_share_status(db, share: BillSplitShare, new_status: str, actor: str, note: str):
    previous_status = share.payment_status
    share.payment_status = new_status
    db.add(UtilityPaymentLog(
        share_id=share.share_id,
        previous_status=previous_status,
        new_status=new_status,
        recorded_by=actor,
        note=note,
    ))

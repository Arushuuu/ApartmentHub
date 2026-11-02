"""Membership and deposit views shared by tenant and admin routes."""

from decimal import Decimal

from sqlalchemy import or_

from app.models import LeaseAgreement, LeaseSignatory


def tenant_leases_query(db, tenant_id: int):
    return db.query(LeaseAgreement).filter(or_(
        LeaseAgreement.tenant_id == tenant_id,
        LeaseAgreement.signatories.any(LeaseSignatory.tenant_id == tenant_id),
    ))


def lease_tenant_ids(lease: LeaseAgreement):
    return sorted({lease.tenant_id, *(signatory.tenant_id for signatory in lease.signatories)})


def deposit_view(deposit):
    if deposit is None:
        return None
    contributions = sorted(deposit.contributions, key=lambda row: row.tenant_id)
    attributed = sum((row.contributed_amt for row in contributions), Decimal("0.00"))
    unattributed = max(deposit.amount_held - attributed, Decimal("0.00"))
    needs_reconciliation = any(row.refunded_amt is None for row in contributions) or unattributed > 0
    remaining = None if needs_reconciliation else sum(
        (row.contributed_amt - row.refunded_amt for row in contributions), Decimal("0.00")
    )
    return {
        "deposit_id": deposit.deposit_id,
        "amount_held": deposit.amount_held,
        "refund_status": deposit.refund_status,
        "remaining_balance": remaining,
        "needs_reconciliation": needs_reconciliation,
        "unattributed_amt": unattributed,
        "contributions": [{
            "tenant_id": row.tenant_id,
            "tenant_name": row.tenant.tenant_name,
            "contributed_amt": row.contributed_amt,
            "refunded_amt": row.refunded_amt,
            "refundable_amt": None if row.refunded_amt is None else row.contributed_amt - row.refunded_amt,
        } for row in contributions],
        "ledger": [{
            "entry_id": entry.entry_id,
            "tenant_id": entry.tenant_id,
            "tenant_name": entry.tenant.tenant_name,
            "action": entry.action,
            "amount": entry.amount,
            "recorded_by": entry.recorded_by,
            "note": entry.note,
            "created_at": entry.created_at,
        } for entry in deposit.ledger],
    }


def lease_view(lease: LeaseAgreement):
    tenant_ids = lease_tenant_ids(lease)
    names = {signatory.tenant_id: signatory.tenant.tenant_name for signatory in lease.signatories}
    names.setdefault(lease.tenant_id, lease.tenant.tenant_name)
    return {
        "lease_id": lease.lease_id,
        "unit_id": lease.unit_id,
        "unit_label": f"{lease.unit.building_name} · Unit {lease.unit.unit_no}",
        "primary_tenant_id": lease.tenant_id,
        "start_date": lease.start_date,
        "end_date": lease.end_date,
        "monthly_rent": lease.monthly_rent,
        "signatories": [{"tenant_id": tenant_id, "tenant_name": names[tenant_id]} for tenant_id in tenant_ids],
        "deposit": deposit_view(lease.deposit),
    }

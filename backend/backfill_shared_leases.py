"""Add shared-lease tables and preserve existing lease/deposit records.

Existing partial refunds have no amount in the old schema. Their contributed
total is imported, but refunded_amt remains NULL until an admin reconciles it.
Running this script again does not duplicate signatories or ledger entries.
"""

from app.database import SessionLocal, engine
from app.models import DepositContribution, DepositLedgerEntry, LeaseAgreement, LeaseSignatory, SecurityDeposit
from sqlalchemy import inspect, text


def main():
    for table in (LeaseSignatory.__table__, DepositContribution.__table__, DepositLedgerEntry.__table__):
        table.create(bind=engine, checkfirst=True)
    if "refunded_amt" not in {column["name"] for column in inspect(engine).get_columns("deposit_contributions")}:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE deposit_contributions ADD COLUMN refunded_amt DECIMAL(10,2) NULL"))

    db = SessionLocal()
    added_signatories = 0
    added_contributions = 0
    unknown_refunds = 0
    try:
        for lease in db.query(LeaseAgreement).all():
            if db.get(LeaseSignatory, (lease.lease_id, lease.tenant_id)) is None:
                db.add(LeaseSignatory(lease_id=lease.lease_id, tenant_id=lease.tenant_id))
                added_signatories += 1

        for deposit in db.query(SecurityDeposit).all():
            tenant_id = deposit.lease.tenant_id
            contribution = db.get(DepositContribution, (deposit.deposit_id, tenant_id))
            if contribution is None:
                # A new shared lease may have contributions only from other
                # signatories; never invent a primary-tenant payment for it.
                if db.query(DepositContribution).filter(DepositContribution.deposit_id == deposit.deposit_id).first():
                    continue
                contribution = DepositContribution(deposit_id=deposit.deposit_id, tenant_id=tenant_id,
                                                   contributed_amt=deposit.amount_held, refunded_amt=None)
                db.add(contribution)
                added_contributions += 1
            if contribution.refunded_amt is None and deposit.refund_status != "Partial Refund":
                contribution.refunded_amt = (contribution.contributed_amt
                                             if deposit.refund_status == "Fully Refunded" else 0)
            if contribution.refunded_amt is None:
                unknown_refunds += 1
            opening = db.query(DepositLedgerEntry).filter(
                DepositLedgerEntry.deposit_id == deposit.deposit_id,
                DepositLedgerEntry.tenant_id == tenant_id,
                DepositLedgerEntry.action == "Opening",
            ).first()
            if opening is None:
                db.add(DepositLedgerEntry(deposit_id=deposit.deposit_id, tenant_id=tenant_id,
                                          action="Opening", amount=contribution.contributed_amt,
                                          recorded_by="System import",
                                          note=f"Existing {deposit.refund_status} contribution imported; historical "
                                               + ("refund amount needs reconciliation" if contribution.refunded_amt is None
                                                  else "transaction dates were not recorded")))
        db.commit()
        unattributed = sum(sum(row.contributed_amt for row in deposit.contributions) < deposit.amount_held
                           for deposit in db.query(SecurityDeposit).all())
        print(f"Added {added_signatories} signatories and {added_contributions} contribution records; "
              f"{unknown_refunds} partial refunds and {unattributed} unattributed totals need reconciliation")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

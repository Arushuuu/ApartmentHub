"""Create the utility ledger table and record opening states for old shares.

Safe to run repeatedly: an existing share receives an opening entry only when
it has no ledger entries yet. Existing payment statuses are never changed.
"""

from app.database import SessionLocal, engine
from app.models import BillSplitShare, UtilityPaymentLog


def main():
    UtilityPaymentLog.__table__.create(bind=engine, checkfirst=True)
    db = SessionLocal()
    created = 0
    try:
        for share in db.query(BillSplitShare).all():
            if share.ledger:
                continue
            db.add(UtilityPaymentLog(
                share_id=share.share_id,
                previous_status=None,
                new_status=share.payment_status,
                recorded_by="System import",
                note="Opening status imported from existing utility records",
            ))
            created += 1
        db.commit()
        print(f"Created {created} opening ledger entries")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

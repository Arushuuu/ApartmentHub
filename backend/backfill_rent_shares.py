"""Add per-tenant rent records for existing lease-level rent payments."""

from app.database import SessionLocal, engine
from app.models import RentPayment, RentPaymentLog, RentShare
from app.rent_ledger import add_payment_shares


def main():
    for table in (RentShare.__table__, RentPaymentLog.__table__):
        table.create(bind=engine, checkfirst=True)
    db = SessionLocal()
    migrated = 0
    try:
        for payment in db.query(RentPayment).order_by(RentPayment.payment_id).all():
            if not payment.shares:
                add_payment_shares(db, payment, imported=True)
                migrated += 1
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    print(f"Rent share tables ready; imported {migrated} existing monthly payments")


if __name__ == "__main__":
    main()

import unittest
from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import ApartmentUnit, MaintenanceTicket, Tenant, TicketUpdateLog
from app.routers.admin import TicketStatusInput, update_ticket_status
from app.routers.tickets import my_tickets
from app.schemas import TicketResponse


class TicketLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.admin = Tenant(tenant_name="Admin", t_email="admin@example.test", password_hash="x", t_dob=date(2000, 1, 1), t_phone_no="1")
        self.owner = Tenant(tenant_name="Owner", t_email="owner@example.test", password_hash="x", t_dob=date(2000, 1, 1), t_phone_no="2")
        self.other = Tenant(tenant_name="Other", t_email="other@example.test", password_hash="x", t_dob=date(2000, 1, 1), t_phone_no="3")
        unit = ApartmentUnit(building_name="A", street="Main", unit_no="1", pincode="123456", base_rent=Decimal("1000"))
        self.db.add_all([self.admin, self.owner, self.other, unit])
        self.db.commit()
        self.ticket = MaintenanceTicket(unit_id=unit.unit_id, tenant_id=self.owner.tenant_id,
                                        category="Plumbing", description="Tap leaks", status="Open")
        self.db.add(self.ticket)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_ordered_transitions_and_tenant_history(self):
        with self.assertRaises(HTTPException) as denied:
            update_ticket_status(self.ticket.ticket_id, TicketStatusInput(status="Closed"), db=self.db, current_admin=self.admin)
        self.assertEqual(denied.exception.status_code, 409)
        self.assertEqual(self.db.query(TicketUpdateLog).count(), 0)

        for before, after in [("Open", "In Progress"), ("In Progress", "Resolved"), ("Resolved", "Closed")]:
            result = update_ticket_status(self.ticket.ticket_id, TicketStatusInput(status=after, update_message="Checked"), db=self.db, current_admin=self.admin)
            self.assertEqual(result["status"], after)
            self.assertEqual(result["updates"][-1]["previous_status"], before)
            self.assertEqual(result["updates"][-1]["new_status"], after)

        own = my_tickets(current_tenant=self.owner, db=self.db)
        self.assertEqual(len(own), 1)
        self.assertEqual(len(own[0]["updates"]), 3)
        self.assertEqual(TicketResponse.model_validate(own[0]).updates[-1].new_status, "Closed")
        self.assertEqual(my_tickets(current_tenant=self.other, db=self.db), [])
        with self.assertRaises(HTTPException) as denied:
            update_ticket_status(self.ticket.ticket_id, TicketStatusInput(status="Closed"), db=self.db, current_admin=self.admin)
        self.assertEqual(denied.exception.status_code, 409)
        self.assertEqual(self.db.query(TicketUpdateLog).count(), 3)


if __name__ == "__main__":
    unittest.main()

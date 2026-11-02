"""Add status transition fields to existing ticket logs without changing old rows."""

from sqlalchemy import inspect, text

from app.database import engine


def main():
    columns = {column["name"] for column in inspect(engine).get_columns("ticket_update_logs")}
    added = []
    with engine.begin() as connection:
        for name in ("previous_status", "new_status"):
            if name not in columns:
                connection.execute(text(f"ALTER TABLE ticket_update_logs ADD COLUMN {name} VARCHAR(30) NULL"))
                added.append(name)
    print(f"Ticket status history ready; added: {', '.join(added) if added else 'no columns needed'}")


if __name__ == "__main__":
    main()

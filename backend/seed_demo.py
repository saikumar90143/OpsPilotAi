"""Insert realistic sample incidents for a local demo.

Run from the backend directory with: python seed_demo.py
"""

from sqlalchemy import select

from app.core.database import Base, SessionLocal, engine
from app.models.incident import Incident

DEMO_INCIDENTS = [
    {
        "title": "Checkout API error rate elevated",
        "description": "HTTP 5xx responses increased from 0.4% to 8.7% over five minutes.",
        "service": "checkout-api",
        "severity": "critical",
        "status": "investigating",
        "source": "prometheus-demo",
    },
    {
        "title": "Background worker queue backlog",
        "description": "Order processing queue has 2,430 pending jobs; normal baseline is below 200.",
        "service": "orders-worker",
        "severity": "high",
        "status": "open",
        "source": "manual-demo",
    },
    {
        "title": "Payment webhook delivery delayed",
        "description": "Partner webhook acknowledgements are taking more than 30 seconds.",
        "service": "payments-webhook",
        "severity": "medium",
        "status": "open",
        "source": "webhook-demo",
    },
]


def main() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        existing_titles = set(db.scalars(select(Incident.title)).all())
        inserted = 0
        for data in DEMO_INCIDENTS:
            if data["title"] not in existing_titles:
                db.add(Incident(**data))
                inserted += 1
        db.commit()
    print(f"Demo seed complete: inserted {inserted} incident(s).")


if __name__ == "__main__":
    main()

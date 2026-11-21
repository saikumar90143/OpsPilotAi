"""Insert realistic sample incidents for a local demo.

Run from the backend directory, after migrations and bootstrap:
    alembic upgrade head
    python -m app.bootstrap
    python seed_demo.py

Idempotent: incidents whose title already exists in the demo org are skipped.
"""

import sys

from sqlalchemy import inspect, select

from app.core.database import SessionLocal, engine
from app.models.incident import Incident
from app.repositories import auth_repo

DEMO_ORG_SLUG = "acme-ops"

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
        "description": (
            "Order processing queue has 2,430 pending jobs; normal baseline is below 200."
        ),
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


def main() -> int:
    if not inspect(engine).has_table(Incident.__tablename__):
        print("Table 'incidents' not found. Run 'alembic upgrade head' first.", file=sys.stderr)
        return 1
    with SessionLocal() as db:
        org = auth_repo.get_organization_by_slug(db, DEMO_ORG_SLUG)
        if org is None:
            print(
                "Demo organization not found. Run 'python -m app.bootstrap' first.", file=sys.stderr
            )
            return 1
        existing_titles = set(
            db.scalars(select(Incident.title).where(Incident.organization_id == org.id)).all()
        )
        new = [
            Incident(organization_id=org.id, **data)
            for data in DEMO_INCIDENTS
            if data["title"] not in existing_titles
        ]
        db.add_all(new)
        db.commit()
    print(f"Demo seed complete: inserted {len(new)} incident(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

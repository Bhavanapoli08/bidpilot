"""
Seed script — creates a demo organization, user, and company profile
so you can log in immediately and test scoring without manual setup.

Usage:
    cd backend
    DATABASE_URL="sqlite:///./bidpilot.db" python seed_demo.py

Demo login:
    email:    demo@bidpilot.ai
    password: demo12345
"""
from app.database import SessionLocal, init_db
from app.models import (
    Organization, User, Subscription, CompanyProfile,
    UserRole, SubscriptionTier,
)
from app.auth.jwt_handler import JWTHandler


def seed():
    init_db()
    db = SessionLocal()

    try:
        if db.query(User).filter(User.email == "demo@bidpilot.ai").first():
            print("Demo account already exists — nothing to do.")
            print("Login: demo@bidpilot.ai / demo12345")
            return

        org = Organization(
            name="Demo Constructions Pvt Ltd",
            email="demo@bidpilot.ai",
        )
        db.add(org)
        db.flush()

        db.add(User(
            organization_id=org.id,
            email="demo@bidpilot.ai",
            password_hash=JWTHandler.hash_password("demo12345"),
            role=UserRole.OWNER,
        ))

        db.add(Subscription(
            organization_id=org.id,
            tier=SubscriptionTier.PRO,
            price_per_month=4999,
        ))

        db.add(CompanyProfile(
            organization_id=org.id,
            company_name="Demo Constructions Pvt Ltd",
            annual_turnover=250,   # ₹ lakhs
            net_worth=120,         # ₹ lakhs
            team_size=45,
            sectors=["construction", "civil"],
            operating_states=["Maharashtra", "Gujarat"],
            certifications={"ISO_9001": True, "ISO_14001": True},
            registrations={"GST": "27DEMO1234F1Z5", "PAN": "DEMOP1234F"},
            years_in_business=12,
            past_projects=[
                {"name": "Highway Resurfacing NH-48", "sectors": ["construction"],
                 "contract_value": 8500000, "year": 2024, "won": True},
                {"name": "Municipal Drainage Phase 2", "sectors": ["civil"],
                 "contract_value": 4200000, "year": 2023, "won": True},
                {"name": "School Building Block C", "sectors": ["construction"],
                 "contract_value": 2600000, "year": 2023, "won": True},
            ],
            bid_success_rate=0.55,
        ))

        db.commit()
        print("✓ Demo data seeded")
        print("  Login: demo@bidpilot.ai / demo12345")
        print("  Plan:  Pro (50 tenders/month)")
    finally:
        db.close()


if __name__ == "__main__":
    seed()

"""Seed initial users into the database."""

import hashlib
from datetime import datetime

from app.database import SessionLocal
from app.models import User


def hash_password(password: str) -> str:
    """Hash password using SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()


def seed_users():
    """Add initial test users with hashed passwords."""
    db = SessionLocal()
    try:
        # Check if users already exist
        existing = db.query(User).first()
        if existing:
            print("Users already exist, skipping seed.")
            return

        # Create test users with hashed passwords
        users = [
            User(username="user1", password=hash_password("1234"), created_at=datetime.utcnow()),
            User(username="user2", password=hash_password("1234"), created_at=datetime.utcnow()),
        ]

        db.add_all(users)
        db.commit()

        print("✓ Successfully created 2 test users:")
        print("  - user1 / 1234")
        print("  - user2 / 1234")

    except Exception as e:
        print(f"Error seeding users: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    seed_users()

"""Migrate existing plain-text passwords to hashed passwords."""

import hashlib

from app.database import SessionLocal
from app.models import User


def hash_password(password: str) -> str:
    """Hash password using SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()


def migrate_passwords():
    """Hash all existing plain-text passwords in the database."""
    db = SessionLocal()
    try:
        users = db.query(User).all()

        if not users:
            print("No users found in database.")
            return

        migrated_count = 0
        for user in users:
            # Check if password is already hashed (SHA-256 produces 64 character hex string)
            if len(user.password) == 64:
                print(f"User '{user.username}' already has hashed password, skipping.")
                continue

            # Hash the plain-text password
            old_password = user.password
            user.password = hash_password(old_password)
            migrated_count += 1
            print(f"Migrated password for user '{user.username}'")

        if migrated_count > 0:
            db.commit()
            print(f"\n✓ Successfully migrated {migrated_count} user password(s)")
        else:
            print("\n✓ All passwords are already hashed")

    except Exception as e:
        print(f"Error migrating passwords: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    migrate_passwords()

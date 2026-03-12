#!/usr/bin/env python3
"""
User Provisioning Script for Trading Assistant

Creates regular (non-admin) users in the database via CLI.

Usage:
    python scripts/create_user.py <email> <password>
    python scripts/create_user.py user@example.com SecurePass123!
"""

import sys
import os
import argparse
from uuid import uuid4

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.db.session import SessionLocal
from app.domain.models import User
from app.core.security import hash_password


def create_user(email: str, password: str) -> User:
    """Create a new regular (non-admin) user."""
    db = SessionLocal()
    
    try:
        # Check if user already exists
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            print(f"✗ Error: User with email '{email}' already exists")
            sys.exit(1)
        
        # Create new user
        new_user = User(
            user_id=uuid4(),
            email=email,
            password_hash=hash_password(password),
            is_enabled=True,
            is_bootstrap_admin=False,  # Regular user, not admin
        )
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        return new_user
        
    except Exception as e:
        db.rollback()
        print(f"✗ Error creating user: {e}")
        sys.exit(1)
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Create a new Trading Assistant user"
    )
    parser.add_argument("email", help="User email address")
    parser.add_argument("password", help="User password")
    parser.add_argument(
        "--admin", 
        action="store_true", 
        help="Create as admin user (optional)"
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Trading Assistant - User Provisioning")
    print("=" * 60)
    print()
    
    user = create_user(args.email, args.password)
    
    print(f"✓ User created successfully!")
    print()
    print(f"  User ID:    {user.user_id}")
    print(f"  Email:      {user.email}")
    print(f"  Enabled:    {user.is_enabled}")
    print(f"  Admin:      {user.is_bootstrap_admin}")
    print()
    print("User can now log in with these credentials.")
    print("=" * 60)


if __name__ == "__main__":
    main()

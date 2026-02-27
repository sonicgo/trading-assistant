#!/usr/bin/env python3
"""
Fix admin password hash - hash plaintext password in DB.
Execute via: python3 scripts/fix_admin_password.py
"""

import os
import sys

# Add backend to path
sys.path.insert(0, '/home/lei-dev/projects/trading-assistant/backend')

from app.db.session import SessionLocal
from app.domain.models import User
from app.core.security import hash_password

def fix_admin_password():
    db = SessionLocal()
    try:
        # Find the bootstrap admin user
        admin = db.query(User).filter(User.is_bootstrap_admin == True).first()
        
        if not admin:
            print("No bootstrap admin user found")
            return
        
        print(f"Found admin user: {admin.email}")
        print(f"Current password hash: {admin.password_hash}")
        
        # Check if password looks like plaintext (not a bcrypt hash)
        # Bcrypt hashes start with $2b$ or $2a$
        if not admin.password_hash.startswith('$2'):
            print("Password appears to be plaintext - hashing now...")
            
            # Hash the plaintext password
            new_hash = hash_password(admin.password_hash)
            admin.password_hash = new_hash
            
            db.commit()
            print(f"✓ Password hashed successfully")
            print(f"New hash: {new_hash[:30]}...")
        else:
            print("Password is already properly hashed - no action needed")
            
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    fix_admin_password()

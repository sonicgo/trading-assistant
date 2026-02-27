#!/usr/bin/env python3
"""
Change admin password script.
Run with: docker compose exec api python3 /app/scripts/change_admin_password.py
"""

import sys
sys.path.insert(0, '/app')

from app.db.session import SessionLocal
from app.domain.models import User
from app.core.security import hash_password

def change_admin_password():
    # Get new password from user
    new_password = input("Enter new admin password (min 8 chars): ").strip()
    
    if len(new_password) < 8:
        print("Error: Password must be at least 8 characters")
        return
    
    confirm = input("Confirm password: ").strip()
    
    if new_password != confirm:
        print("Error: Passwords do not match")
        return
    
    db = SessionLocal()
    try:
        # Find admin user
        admin = db.query(User).filter(User.is_bootstrap_admin == True).first()
        
        if not admin:
            print("Error: No admin user found")
            return
        
        # Hash and update password
        hashed = hash_password(new_password)
        admin.password_hash = hashed
        db.commit()
        
        print(f"✓ Password updated successfully for {admin.email}")
        print(f"  New hash: {hashed[:30]}...")
        
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    change_admin_password()

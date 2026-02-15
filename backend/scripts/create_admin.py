from app.db.session import SessionLocal
from app.domain.models import User
from app.core.security import get_password_hash
from uuid import uuid4

db = SessionLocal()
email = "admin@example.com"
pwd = "admin"

user = db.query(User).filter(User.email == email).first()
if not user:
    print(f"Creating admin user: {email}")
    user = User(
        user_id=uuid4(),
        email=email,
        password_hash=get_password_hash(pwd),
        is_enabled=True,
        is_bootstrap_admin=True
    )
    db.add(user)
    db.commit()
else:
    print("Admin user already exists")
db.close()

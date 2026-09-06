"""
Seed database with initial data including admin user.
Run this script to initialize the database with default credentials.

⚠️ SECURITY WARNING: 
This script creates a default admin user with hardcoded credentials.
This is ONLY for demonstration and development purposes.
For production deployment:
1. Change the default password immediately
2. Use environment variables for credentials
3. Implement proper credential rotation policies
4. Remove this script from production deployments
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import engine, Base, SessionLocal
from app.models.user import User
from app.core.security import get_password_hash


def seed_database():
    """Initialize database with seed data."""
    print("Initializing database...")
    
    # Security: Use environment variables for credentials in production
    admin_username = os.getenv("ADMIN_USERNAME", "admin@trackx.com")
    admin_password = os.getenv("ADMIN_PASSWORD", "admin123")
    
    # Security warning for production use
    if os.getenv("ENVIRONMENT") == "production" and admin_password == "admin123":
        print("⚠️  SECURITY WARNING: Using default password in production environment!")
        print("Please set ADMIN_PASSWORD environment variable.")
    
    # Create all tables
    Base.metadata.create_all(engine)
    print("OK Database tables created")
    
    # Create session
    db = SessionLocal()
    
    try:
        # Check if admin user already exists
        admin_user = db.query(User).filter(User.username == admin_username).first()
        
        if not admin_user:
            # Create admin user
            admin_user = User(
                username=admin_username,
                email=admin_username,
                hashed_password=get_password_hash(admin_password),
                full_name="TrackX Administrator",
                role="admin",
                is_admin=True,
                organization="TrackX",
                department="IT",
                is_active=True
            )
            db.add(admin_user)
            db.commit()
            print("OK Admin user created")
            print(f"  Username: {admin_username}")
            print(f"  Password: {'[FROM ENV VAR]' if os.getenv('ADMIN_PASSWORD') else admin_password}")
            print("⚠️  SECURITY: Change default password before production deployment")
        else:
            print("OK Admin user already exists")
        
        print("\nDatabase seeding completed successfully!")
        
    except Exception as e:
        print(f"Error seeding database: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
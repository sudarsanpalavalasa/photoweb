"""
Script to create admin user with custom credentials
"""
import sys
sys.path.append('.')

from app_sqlite import app, db, User

# CUSTOMIZE THESE:
USERNAME = "admin"
PASSWORD = "mypassword123"  # Change this to your password
EMAIL = "admin@gmail.com"

with app.app_context():
    # Delete existing admin if exists
    existing_admin = User.query.filter_by(username=USERNAME).first()
    if existing_admin:
        print(f"Deleting existing user: {USERNAME}")
        db.session.delete(existing_admin)
        db.session.commit()
    
    # Create new admin
    admin = User(
        username=USERNAME,
        email=EMAIL,
        role='admin'
    )
    admin.set_password(PASSWORD)
    
    db.session.add(admin)
    db.session.commit()
    
    print("✅ Admin user created successfully!")
    print("=" * 50)
    print(f"Username: {USERNAME}")
    print(f"Password: {PASSWORD}")
    print(f"Email: {EMAIL}")
    print("=" * 50)
    
    # Test
    test_user = User.query.filter_by(username=USERNAME).first()
    if test_user and test_user.check_password(PASSWORD):
        print("✅ Login test: SUCCESS")
    else:
        print("❌ Login test: FAILED")

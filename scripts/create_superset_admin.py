"""Script to create Superset admin user."""

from flask_appbuilder.security.manager import BaseSecurityManager
from superset import create_app

app = create_app()
app.app_context().push()

security_manager = app.appbuilder.sm

# Check if admin user exists
admin_user = security_manager.find_user(username="admin")

if admin_user:
    print("Admin user already exists")
else:
    # Create admin user
    admin_user = security_manager.add_user(
        username="admin",
        first_name="Admin",
        last_name="User",
        email="admin@example.com",
        role=security_manager.find_role("Admin"),
        password="admin",
    )
    if admin_user:
        print("Admin user created successfully!")
    else:
        print("Failed to create admin user")

# List all users
print("\nAll users:")
for user in security_manager.get_all_users():
    print(f"  - {user.username} ({user.email}) - roles: {[r.name for r in user.roles]}")
#!/usr/bin/env python3
"""Initialize Superset database and create admin user."""

import os
import subprocess
import time

def wait_for_superset(timeout=60):
    """Wait for Superset to be ready."""
    for i in range(timeout):
        result = subprocess.run(
            ["docker", "compose", "exec", "superset", "superset", "health"],
            capture_output=True,
            text=True
        )
        if "ok" in result.stdout.lower():
            return True
        time.sleep(1)
    return False

def main():
    print("Waiting for Superset to start...")
    if not wait_for_superset():
        print("ERROR: Superset did not start in time")
        return 1
    
    print("Initializing Superset database...")
    subprocess.run(["docker", "compose", "exec", "superset", "superset", "db", "upgrade"], check=True)
    
    print("Creating admin user...")
    subprocess.run([
        "docker", "compose", "exec", "-e", "FLASK_APP=superset.app:create_app()",
        "superset", "flask", "fab", "create-admin",
        "--username", "admin",
        "--email", "admin@example.com",
        "--firstname", "Admin",
        "--lastname", "User",
        "--password", "admin"
    ], check=True)
    
    print("Loading examples (optional)...")
    subprocess.run(["docker", "compose", "exec", "superset", "superset", "load-examples"], check=False)
    
    print("Superset initialized successfully!")
    print("Access at: http://localhost:8088")
    print("Username: admin")
    print("Password: admin")
    return 0

if __name__ == "__main__":
    exit(main())
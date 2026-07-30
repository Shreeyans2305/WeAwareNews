"""
WeAwareNews - Create Admin User (Manual Step)
===============================================
Run this AFTER setup_auth.py to create your first admin account
directly via the Supabase service-role key (bypasses email confirm).

Usage:
  python create_admin.py --email you@example.com --password YourPass123
"""

import os
import sys
import argparse
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    print("[ERR] Missing SUPABASE_URL or SUPABASE_SERVICE_KEY in .env")
    sys.exit(1)

try:
    from supabase import create_client
except ImportError:
    print("[ERR] supabase-py not installed. Run:  python -m pip install supabase python-dotenv")
    sys.exit(1)

client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

parser = argparse.ArgumentParser(description="Create a WeAware admin user")
parser.add_argument("--email",    required=True,  help="Admin email address")
parser.add_argument("--password", required=True,  help="Admin password (min 8 chars)")
parser.add_argument("--name",     default="Admin", help="Display name")
args = parser.parse_args()

print(f"[*]  Creating admin user: {args.email} ...")

try:
    # Use admin API to skip email confirmation
    resp = client.auth.admin.create_user({
        "email":          args.email,
        "password":       args.password,
        "email_confirm":  True,
        "user_metadata":  {"full_name": args.name, "role": "admin"},
    })
    user_id = resp.user.id
    print(f"[OK] Auth user created -- id: {user_id}")
except Exception as e:
    print(f"[ERR] Auth error: {e}")
    sys.exit(1)

# Update the auto-created profile to set role = admin
try:
    client.table("profiles").update({"role": "admin", "full_name": args.name}) \
        .eq("id", user_id).execute()
    print("[OK] Profile updated to admin role")
except Exception as e:
    print(f"[WARN] Could not update profile: {e}")

print("\n[DONE] Admin created! You can now log in at the WeAware login page.")
print(f"       Email:    {args.email}")
print(f"       Password: {args.password}")

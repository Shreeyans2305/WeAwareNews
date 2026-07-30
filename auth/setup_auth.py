"""
WeAwareNews — Supabase Auth Setup Script
========================================
Run this ONCE to verify your Supabase connection and seed the
'roles' lookup table with the default values the app expects.

Requirements:
  pip install supabase python-dotenv

Usage:
  1. Copy .env.example → .env and fill in your values
  2. python setup_auth.py
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")  # service_role key (bypasses RLS)

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    print("[ERR] Missing SUPABASE_URL or SUPABASE_SERVICE_KEY in .env")
    sys.exit(1)

try:
    from supabase import create_client, Client
except ImportError:
    print("[ERR] supabase-py not installed.  Run:  pip install supabase")
    sys.exit(1)

client: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# -- 1. Verify connection -------------------------------------------------------
print("[*]  Connecting to Supabase ...")
try:
    # A lightweight query to confirm the connection works
    result = client.table("profiles").select("id").limit(1).execute()
    print("[OK] Connection OK -- profiles table reachable")
except Exception as e:
    print(f"[ERR] Could not reach 'profiles' table: {e}")
    print("      Make sure you have run the SQL in supabase/schema.sql first.")
    sys.exit(1)

# -- 2. Seed roles ---------------------------------------------------------------
DEFAULT_ROLES = [
    {"name": "guest",          "display": "Anonymous Guest",    "level": 0},
    {"name": "reader",         "display": "Reader",             "level": 1},
    {"name": "correspondent",  "display": "Senior Correspondent","level": 2},
    {"name": "auditor",        "display": "AI Node Auditor",     "level": 3},
    {"name": "admin",          "display": "Administrator",       "level": 99},
]

print("\n[*]  Seeding roles ...")
for role in DEFAULT_ROLES:
    try:
        # upsert so re-running is safe
        client.table("roles").upsert(role, on_conflict="name").execute()
        print(f"   [OK] {role['name']}")
    except Exception as e:
        print(f"   [WARN] {role['name']} -- {e}")

# -- 3. Summary -----------------------------------------------------------------
print("\n[DONE] Setup complete!")
print("       Next steps:")
print("       1. Copy Frontend/.env.local.example -> Frontend/.env.local")
print("       2. Fill in VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY")
print("       3. Run:  cd Frontend && npm run dev")

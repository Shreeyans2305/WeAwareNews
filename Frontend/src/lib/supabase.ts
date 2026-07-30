/// <reference types="vite/client" />
import { createClient } from "@supabase/supabase-js";

const SUPABASE_URL  = import.meta.env.VITE_SUPABASE_URL  as string;
const SUPABASE_ANON = import.meta.env.VITE_SUPABASE_ANON_KEY as string;

if (!SUPABASE_URL || !SUPABASE_ANON) {
  throw new Error(
    "Missing VITE_SUPABASE_URL or VITE_SUPABASE_ANON_KEY in environment.\n" +
    "Copy Frontend/.env.local.example → Frontend/.env.local and fill in your values."
  );
}

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON);

// ── Typed helpers ──────────────────────────────────────────────────────────────

export interface Profile {
  id:         string;
  email:      string;
  full_name:  string | null;
  avatar_url: string | null;
  role:       string;
  created_at: string;
  updated_at: string;
}

/** Fetch the profile row for the currently signed-in user. */
export async function getProfile(userId: string): Promise<Profile | null> {
  const { data, error } = await supabase
    .from("profiles")
    .select("*")
    .eq("id", userId)
    .single();
  if (error) return null;
  return data as Profile;
}

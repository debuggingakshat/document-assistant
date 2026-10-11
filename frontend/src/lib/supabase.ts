/**
 * Browser Supabase client — the single instance for the whole app.
 *
 * Used for:
 *   - Email sign-in / sign-up
 *   - Reading the current session and access token
 *   - Listening to auth state changes
 *
 * Never use the service-role key here. The anon key is the only credential
 * that belongs in the browser.
 */

import { createClient, type SupabaseClient } from "@supabase/supabase-js"

import { env } from "@/lib/env"

export const supabase: SupabaseClient = createClient(
  env.supabaseUrl,
  env.supabaseAnonKey,
)

/**
 * Returns the current user's access token, or null if not signed in.
 * Used by the HTTP client to inject the bearer token on every request.
 */
export async function getAccessToken(): Promise<string | null> {
  const { data } = await supabase.auth.getSession()
  return data.session?.access_token ?? null
}

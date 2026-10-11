/**
 * Single source of truth for all environment variables.
 *
 * Fails fast at module load time if any required var is missing or empty.
 * Import from here — never read `import.meta.env.*` directly in app code.
 */

function require(key: string): string {
  const value = import.meta.env[key]
  if (!value || typeof value !== "string" || value.trim() === "") {
    throw new Error(
      `Missing required environment variable: ${key}. ` +
        `Check your .env file and ensure the variable is set.`,
    )
  }
  return value.trim()
}

export const env = {
  /** Base URL for the FastAPI backend, e.g. http://localhost:8000 */
  apiBaseUrl: require("VITE_API_BASE_URL"),

  /** Supabase project URL, e.g. https://xyz.supabase.co */
  supabaseUrl: require("VITE_SUPABASE_URL"),

  /** Supabase anon/public key — safe to expose in the browser */
  supabaseAnonKey: require("VITE_SUPABASE_ANON_KEY"),
} as const

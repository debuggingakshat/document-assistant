/**
 * Thin fetch wrapper for the FastAPI backend.
 *
 * Responsibilities:
 *   - Prefixes every request with VITE_API_BASE_URL
 *   - Injects `Authorization: Bearer <token>` from the Supabase session
 *   - Sets a default timeout (10 s)
 *   - Converts non-2xx responses into a typed ApiError
 *   - Distinguishes network/CORS failures from HTTP failures via isNetworkError
 *
 * Do not use fetch() directly in app code — use this module or api.ts.
 */

import { env } from "@/lib/env"
import { getAccessToken } from "@/lib/supabase"

// ---------------------------------------------------------------------------
// Error type
// ---------------------------------------------------------------------------

export class ApiError extends Error {
  readonly status: number
  /** True when the request never reached the server (CORS, offline, etc.) */
  readonly isNetworkError: boolean

  constructor(
    status: number,
    message: string,
    isNetworkError: boolean = false,
  ) {
    super(message)
    this.name = "ApiError"
    this.status = status
    this.isNetworkError = isNetworkError
  }
}

// ---------------------------------------------------------------------------
// Core request helper
// ---------------------------------------------------------------------------

const DEFAULT_TIMEOUT_MS = 10_000

export type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE"

export interface RequestOptions {
  /** Extra headers merged on top of the defaults. */
  headers?: Record<string, string>
  /** Request body. Objects are JSON-serialised automatically. */
  body?: unknown
  /** Override the default 10 s timeout. */
  timeoutMs?: number
}

async function request<T>(
  method: HttpMethod,
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const token = await getAccessToken()

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  }

  const controller = new AbortController()
  const timeoutId = setTimeout(
    () => controller.abort(),
    options.timeoutMs ?? DEFAULT_TIMEOUT_MS,
  )

  let response: Response
  try {
    response = await fetch(`${env.apiBaseUrl}${path}`, {
      method,
      headers,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
      signal: controller.signal,
    })
  } catch (err) {
    // AbortError from timeout, or CORS / network failure before a response.
    const message =
      err instanceof DOMException && err.name === "AbortError"
        ? "Request timed out"
        : "Network error — could not reach the server"
    throw new ApiError(0, message, true)
  } finally {
    clearTimeout(timeoutId)
  }

  if (!response.ok) {
    let detail = response.statusText
    try {
      const body = await response.json()
      if (typeof body?.detail === "string") detail = body.detail
    } catch {
      // non-JSON error body — keep statusText
    }
    throw new ApiError(response.status, detail)
  }

  // 204 No Content — return empty object rather than trying to parse nothing.
  if (response.status === 204) return {} as T

  return response.json() as Promise<T>
}

// ---------------------------------------------------------------------------
// Convenience methods
// ---------------------------------------------------------------------------

export const http = {
  get: <T>(path: string, options?: Omit<RequestOptions, "body">) =>
    request<T>("GET", path, options),

  post: <T>(path: string, body?: unknown, options?: Omit<RequestOptions, "body">) =>
    request<T>("POST", path, { ...options, body }),

  put: <T>(path: string, body?: unknown, options?: Omit<RequestOptions, "body">) =>
    request<T>("PUT", path, { ...options, body }),

  patch: <T>(path: string, body?: unknown, options?: Omit<RequestOptions, "body">) =>
    request<T>("PATCH", path, { ...options, body }),

  delete: <T>(path: string, options?: Omit<RequestOptions, "body">) =>
    request<T>("DELETE", path, options),
}

/**
 * Product-level API calls against the FastAPI backend.
 *
 * All functions use http.ts — never call fetch() directly here.
 * Add new product calls to this file as features are built.
 */

import { http } from "@/lib/http"

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface Thread {
  id: string
  title: string | null
  created_at: string
  updated_at: string
}

export interface Message {
  id: string
  thread_id: string
  role: "user" | "assistant"
  content: string
  created_at: string
}

// ---------------------------------------------------------------------------
// Thread endpoints
// ---------------------------------------------------------------------------

/** List all chat threads belonging to the authenticated user. */
export function listThreads(): Promise<Thread[]> {
  return http.get<Thread[]>("/threads")
}

/** Create a new chat thread. */
export function createThread(title?: string): Promise<Thread> {
  return http.post<Thread>("/threads", { title })
}

/** Load the message history for a thread. */
export function listMessages(threadId: string): Promise<Message[]> {
  return http.get<Message[]>(`/threads/${threadId}/messages`)
}

/** Rename an existing chat thread. */
export function updateThread(threadId: string, title: string): Promise<Thread> {
  return http.patch<Thread>(`/threads/${threadId}`, { title })
}

/** Delete a chat thread and all its messages. */
export function deleteThread(threadId: string): Promise<void> {
  return http.delete<void>(`/threads/${threadId}`)
}

// ---------------------------------------------------------------------------
// Auth smoke-test
// ---------------------------------------------------------------------------

/** Verify the backend can read the current user's identity. */
export function getMe(): Promise<{ id: string; email: string }> {
  return http.get<{ id: string; email: string }>("/me")
}

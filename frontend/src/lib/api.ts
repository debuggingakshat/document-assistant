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
  is_pinned?: boolean
  is_archived?: boolean
  created_at: string
  updated_at: string
}

export interface UpdateThreadPayload {
  title?: string
  is_pinned?: boolean
  is_archived?: boolean
}

export interface Citation {
  id?: string
  chunk_id: string
  citation_index: number
  ticker?: string | null
  company_name?: string | null
  fiscal_year?: number | null
  filing_type?: string | null
  filing_date?: string | null
  section?: string | null
  page?: number | null
  snippet?: string | null
  excerpt?: string | null
  full_context_text?: string | null
  is_table?: boolean
}

export interface Message {
  id: string
  thread_id: string
  role: "user" | "assistant"
  content: string
  created_at: string
  citations?: Citation[]
  ai_sdk_metadata?: Record<string, any>
  suggested_followups?: string[]
}

export interface PipelineStatus {
  stage: "searching" | "fusion" | "reasoning" | "validating" | "complete" | string
  title?: string
  message: string
  technical_details?: Record<string, any>
}

// ---------------------------------------------------------------------------
// Thread endpoints
// ---------------------------------------------------------------------------

/** List all chat threads belonging to the authenticated user. */
export function listThreads(archived = false): Promise<Thread[]> {
  const query = archived ? "?archived=true" : ""
  return http.get<Thread[]>(`/threads${query}`)
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
export function updateThread(
  threadId: string,
  payload: string | UpdateThreadPayload
): Promise<Thread> {
  const body = typeof payload === "string" ? { title: payload } : payload
  return http.patch<Thread>(`/threads/${threadId}`, body)
}

/** Delete a chat thread and all its messages. */
export function deleteThread(threadId: string): Promise<void> {
  return http.delete<void>(`/threads/${threadId}`)
}

/** Fetch stored citations for an assistant message. */
export function listMessageCitations(messageId: string): Promise<Citation[]> {
  return http.get<Citation[]>(`/messages/${messageId}/citations`)
}

// ---------------------------------------------------------------------------
// Auth smoke-test
// ---------------------------------------------------------------------------

/** Verify the backend can read the current user's identity. */
export function getMe(): Promise<{ id: string; email: string }> {
  return http.get<{ id: string; email: string }>("/me")
}

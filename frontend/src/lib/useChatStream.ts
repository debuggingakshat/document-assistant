import { useCallback, useEffect, useRef, useState } from "react"
import {
  createThread,
  listMessages,
  type Citation,
  type Message,
  type PipelineStatus,
} from "@/lib/api"
import { env } from "@/lib/env"
import { getAccessToken } from "@/lib/supabase"

interface UseChatStreamOptions {
  threadId: string | undefined
}

// Global in-memory cache for 0ms instantaneous thread switching (Stale-While-Revalidate)
const threadMessagesCache = new Map<string, Message[]>()

export function useChatStream({ threadId }: UseChatStreamOptions) {
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isStreaming, setIsStreaming] = useState(false)
  const [pipelineStatus, setPipelineStatus] = useState<PipelineStatus | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Track the current active thread ID (initialized from route or set when draft creates a thread)
  const [activeThreadId, setActiveThreadId] = useState<string | undefined>(threadId)
  const justCreatedThreadIdRef = useRef<string | null>(null)

  useEffect(() => {
    setActiveThreadId(threadId)
  }, [threadId])

  // Automatically keep in-memory cache fresh for instant switches
  useEffect(() => {
    if (activeThreadId && messages.length > 0) {
      threadMessagesCache.set(activeThreadId, messages)
    }
  }, [activeThreadId, messages])

  // Universal reset listener: when user clicks "New Research Thread", clear all session state
  useEffect(() => {
    function handleResetToDraft() {
      setMessages([])
      setActiveThreadId(undefined)
      setIsLoading(false)
      setIsStreaming(false)
      setPipelineStatus(null)
      setError(null)
      justCreatedThreadIdRef.current = null
      if (typeof window !== "undefined") {
        window.history.replaceState(null, "", "/")
      }
    }

    window.addEventListener("meridian_reset_to_draft", handleResetToDraft)
    return () => {
      window.removeEventListener("meridian_reset_to_draft", handleResetToDraft)
    }
  }, [])

  // Load message history when threadId changes
  useEffect(() => {
    if (!threadId) {
      setMessages([])
      setIsLoading(false)
      setError(null)
      return
    }

    // If this thread was just created on the fly in draft mode, do not wipe/refetch
    if (justCreatedThreadIdRef.current === threadId) {
      justCreatedThreadIdRef.current = null
      return
    }

    // 0ms Cache Hit: If previously opened in this session, display immediately without skeleton!
    const cached = threadMessagesCache.get(threadId)
    if (cached && cached.length > 0) {
      setMessages(cached)
      setIsLoading(false)
    } else {
      setIsLoading(true)
    }

    let isMounted = true

    // Citations are now directly embedded in the single backend payload (N+1 cascade eliminated)
    listMessages(threadId)
      .then((history) => {
        if (!isMounted) return
        threadMessagesCache.set(threadId, history)
        setMessages(history)
        setIsLoading(false)
        setError(null)
      })
      .catch((err) => {
        if (isMounted) {
          setError(err instanceof Error ? err.message : "Failed to load messages")
          setIsLoading(false)
        }
      })

    return () => {
      isMounted = false
    }
  }, [threadId])

  const sendMessage = useCallback(
    async (
      content: string,
      modelOverride?: string,
      options?: { parentUserMessageId?: string }
    ) => {
      const trimmed = content.trim()
      if (!trimmed || isStreaming) return

      setError(null)
      setPipelineStatus({
        stage: "searching",
        message: "Searching SEC 10-K filings with hybrid keyword & vector retrieval...",
      })

      const parentUserMessageId = options?.parentUserMessageId
      const userMessageId = parentUserMessageId || `user-${Date.now()}`
      const assistantMessageId = `assistant-${Date.now()}`

      let targetThreadId = activeThreadId || threadId
      const placeholderThreadId = targetThreadId || `draft-${Date.now()}`

      // 1. OPTIMISTIC MOUNT (0ms UI latency): Immediately show user prompt & assistant thinking state
      const initialAssistantMsg: Message = {
        id: assistantMessageId,
        thread_id: placeholderThreadId,
        role: "assistant",
        content: "",
        created_at: new Date().toISOString(),
        citations: [],
        ai_sdk_metadata: {
          parent_user_message_id: parentUserMessageId,
          model: modelOverride || localStorage.getItem("selected_llm_model") || "gemini-2.5-flash",
        },
      }

      if (parentUserMessageId) {
        // Regeneration turn: append new assistant version under the existing user prompt
        setMessages((prev) => [...prev, initialAssistantMsg])
      } else {
        const userMsg: Message = {
          id: userMessageId,
          thread_id: placeholderThreadId,
          role: "user",
          content: trimmed,
          created_at: new Date().toISOString(),
        }
        setMessages((prev) => [...prev, userMsg, initialAssistantMsg])
      }
      setIsStreaming(true)

      // 2. If in draft mode (no thread exists yet), create the thread on the fly in the background!
      // Decoupled architecture: New threads always initialize as "Untitled Analysis"; the backend LLM semantic gate titles the thread.
      if (!targetThreadId) {
        try {
          const newThread = await createThread("Untitled Analysis")
          targetThreadId = newThread.id
          setActiveThreadId(newThread.id)
          justCreatedThreadIdRef.current = newThread.id

          // Re-link the optimistically mounted messages to the real thread ID
          setMessages((prev) =>
            prev.map((m) =>
              m.thread_id === placeholderThreadId ? { ...m, thread_id: newThread.id } : m
            )
          )

          if (typeof window !== "undefined") {
            window.dispatchEvent(
              new CustomEvent("meridian_thread_created", { detail: newThread })
            )
            window.history.replaceState(null, "", `/chat/${newThread.id}`)
          }
        } catch (err) {
          setError(err instanceof Error ? err.message : "Failed to initialize research thread")
          setMessages((prev) =>
            prev.filter((m) => m.id !== assistantMessageId && m.id !== userMessageId)
          )
          setPipelineStatus(null)
          setIsStreaming(false)
          return
        }
      }

      try {
        const token = await getAccessToken()
        const headers: Record<string, string> = {
          "Content-Type": "application/json",
        }
        if (token) {
          headers.Authorization = `Bearer ${token}`
        }

        const response = await fetch(`${env.apiBaseUrl}/chat/stream`, {
          method: "POST",
          headers,
          body: JSON.stringify({
            threadId: targetThreadId,
            messages: [{ role: "user", content: trimmed }],
            model: modelOverride || localStorage.getItem("selected_llm_model") || "gemini-2.5-flash",
            parentUserMessageId,
          }),
        })

        if (!response.ok) {
          const errorData = await response.json().catch(() => null)
          const message = errorData?.detail || `Server returned ${response.status}`
          throw new Error(message)
        }

        if (!response.body) {
          throw new Error("No response body received from server")
        }

        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ""
        let accumulatedAssistantText = ""
        let currentAssistantId = assistantMessageId

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split("\n")
          buffer = lines.pop() ?? ""

          for (const line of lines) {
            if (!line) continue

            // 0: Text chunks
            if (line.startsWith("0:")) {
              try {
                const textChunk = JSON.parse(line.slice(2)) as string
                accumulatedAssistantText += textChunk

                // Update assistant message content in state
                setMessages((prev) =>
                  prev.map((m) =>
                    (m.id === assistantMessageId || m.id === currentAssistantId)
                      ? { ...m, content: accumulatedAssistantText }
                      : m
                  )
                )
              } catch {
                // Ignore parse failures
              }
            }

            // 2: Structured metadata events (status, citations)
            else if (line.startsWith("2:")) {
              try {
                const dataArr = JSON.parse(line.slice(2))
                if (Array.isArray(dataArr)) {
                  for (const item of dataArr) {
                    if (item.type === "status") {
                      setPipelineStatus({
                        stage: item.stage,
                        title: item.title,
                        message: item.message,
                        technical_details: item.technical_details,
                      })
                      if (item.stage === "complete") {
                        setTimeout(() => setPipelineStatus(null), 800)
                      }
                    } else if (item.type === "thread_title") {
                      if (typeof window !== "undefined") {
                        window.dispatchEvent(
                          new CustomEvent("thread_title_updated", {
                            detail: {
                              threadId: item.threadId,
                              title: item.title,
                            },
                          })
                        )
                      }
                    } else if (item.type === "citations") {
                      const cits = item.citations as Citation[]
                      if (item.messageId) currentAssistantId = item.messageId
                      setMessages((prev) =>
                        prev.map((m) =>
                          (m.id === assistantMessageId || m.id === currentAssistantId)
                            ? {
                                ...m,
                                id: item.messageId || m.id,
                                citations: cits,
                              }
                            : m
                        )
                      )
                    }
                  }
                }
              } catch {
                // Ignore parse failures
              }
            }
          }
        }

        // Inform application that stream finished to trigger title & thread synchronization
        if (typeof window !== "undefined") {
          window.dispatchEvent(
            new CustomEvent("meridian_stream_finished", {
              detail: { threadId: targetThreadId },
            })
          )
        }
      } catch (err) {
        const errMsg = err instanceof Error ? err.message : "Failed to send message"
        setError(errMsg)
        setMessages((prev) =>
          prev.filter((m) => m.id !== assistantMessageId || m.content.length > 0)
        )
      } finally {
        setIsStreaming(false)
        setPipelineStatus(null)
      }
    },
    [activeThreadId, threadId, isStreaming]
  )

  return {
    messages,
    isLoading,
    isStreaming,
    pipelineStatus,
    error,
    sendMessage,
  }
}

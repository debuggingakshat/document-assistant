import { useCallback, useEffect, useState } from "react"
import {
  listMessageCitations,
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

export function useChatStream({ threadId }: UseChatStreamOptions) {
  const [messages, setMessages] = useState<Message[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [isStreaming, setIsStreaming] = useState(false)
  const [pipelineStatus, setPipelineStatus] = useState<PipelineStatus | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Load message history when threadId changes
  useEffect(() => {
    if (!threadId) {
      return
    }

    let isMounted = true
    setIsLoading(true)

    listMessages(threadId)
      .then(async (history) => {
        if (!isMounted) return

        // For assistant messages, load stored citations if available
        const enriched = await Promise.all(
          history.map(async (msg) => {
            if (msg.role === "assistant") {
              try {
                const cits = await listMessageCitations(msg.id)
                return { ...msg, citations: cits }
              } catch {
                return msg
              }
            }
            return msg
          })
        )

        if (isMounted) {
          setMessages(enriched)
          setIsLoading(false)
          setError(null)
        }
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
    async (content: string) => {
      const trimmed = content.trim()
      if (!trimmed || !threadId || isStreaming) return

      setError(null)
      setPipelineStatus({
        stage: "searching",
        message: "Searching SEC 10-K filings with hybrid keyword & vector retrieval...",
      })

      const userMessageId = `user-${Date.now()}`
      const assistantMessageId = `assistant-${Date.now()}`

      const userMsg: Message = {
        id: userMessageId,
        thread_id: threadId,
        role: "user",
        content: trimmed,
        created_at: new Date().toISOString(),
      }

      const initialAssistantMsg: Message = {
        id: assistantMessageId,
        thread_id: threadId,
        role: "assistant",
        content: "",
        created_at: new Date().toISOString(),
        citations: [],
      }

      setMessages((prev) => [...prev, userMsg, initialAssistantMsg])
      setIsStreaming(true)

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
            threadId,
            messages: [{ role: "user", content: trimmed }],
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
                    m.id === assistantMessageId
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
                        message: item.message,
                      })
                      if (item.stage === "complete") {
                        setTimeout(() => setPipelineStatus(null), 800)
                      }
                    } else if (item.type === "citations") {
                      const cits = item.citations as Citation[]
                      setMessages((prev) =>
                        prev.map((m) =>
                          m.id === assistantMessageId
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
    [threadId, isStreaming]
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

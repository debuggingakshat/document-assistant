import { useEffect, useRef, useState } from "react"
import { ArrowUpRight, Cpu, FileText, Sparkles, TrendingUp } from "lucide-react"
import { MessageInput } from "@/components/chat/MessageInput"
import { MessageItem } from "@/components/chat/MessageItem"
import { PipelineStatusIndicator } from "@/components/chat/PipelineStatusIndicator"
import { SourcePassageDrawer } from "@/components/chat/SourcePassageDrawer"
import type { Citation } from "@/lib/api"
import { formatMessageDate, isDifferentDay } from "@/lib/dateUtils"
import { useChatStream } from "@/lib/useChatStream"

interface ChatAreaProps {
  threadId: string
}

const STARTER_PROMPTS = [
  {
    category: "Apple Financial Performance",
    icon: TrendingUp,
    question: "What were Apple's net sales for iPhone and Services in fiscal 2024?",
    tag: "AAPL FY2024 10-K",
  },
  {
    category: "Amazon GenAI & Margins",
    icon: FileText,
    question: "Did generative AI improve operating margins for Amazon in 2023?",
    tag: "AMZN FY2023 10-K",
  },
  {
    category: "Nvidia Data Center Growth",
    icon: Cpu,
    question: "What drove Nvidia's Data Center revenue growth in fiscal 2024?",
    tag: "NVDA FY2024 10-K",
  },
]

export function ChatArea({ threadId }: ChatAreaProps) {
  const { messages, isLoading, isStreaming, pipelineStatus, error, sendMessage } =
    useChatStream({ threadId })
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, isStreaming, pipelineStatus])

  return (
    <div className="flex h-screen flex-1 flex-col overflow-hidden bg-background">
      {/* Top Header Bar */}
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-border/80 px-6">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-emerald-500 ring-2 ring-emerald-500/20" />
            <span className="text-xs font-semibold text-foreground">
              SEC Research Session
            </span>
          </div>
          <span className="rounded-md border border-border/70 bg-muted/60 px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
            id:{threadId.slice(0, 8)}
          </span>
        </div>

        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span className="hidden sm:inline rounded-full border border-border/60 bg-card px-2.5 py-1 text-[11px] font-medium text-foreground">
            Corpus: SEC 10-K Filings
          </span>
        </div>
      </header>

      {/* Messages Viewport */}
      <div className="flex-1 overflow-y-auto px-4 py-6 md:px-8">
        <div className="mx-auto max-w-3xl">
          {isLoading ? (
            <div className="flex h-64 flex-col items-center justify-center gap-2 text-xs text-muted-foreground">
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
              <span>Loading conversation history & citations...</span>
            </div>
          ) : messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-border/80 bg-foreground text-background shadow-xs">
                <Sparkles className="h-6 w-6" />
              </div>
              <h2 className="mt-4 text-lg font-semibold tracking-tight text-foreground">
                Document Assistant
              </h2>
              <p className="mt-1.5 max-w-md text-xs leading-relaxed text-muted-foreground">
                Query disclosures, financial metrics, and notes from filed SEC reports with grounded citations and source verification.
              </p>

              {/* Starter Question Cards */}
              <div className="mt-8 grid w-full max-w-2xl gap-3 sm:grid-cols-3">
                {STARTER_PROMPTS.map((item) => {
                  const Icon = item.icon
                  return (
                    <button
                      key={item.category}
                      type="button"
                      onClick={() => void sendMessage(item.question)}
                      className="group flex flex-col justify-between rounded-xl border border-border/70 bg-card p-3.5 text-left shadow-2xs transition-all hover:border-foreground/30 hover:shadow-xs cursor-pointer"
                    >
                      <div>
                        <div className="flex items-center justify-between text-muted-foreground">
                          <Icon className="h-4 w-4 text-foreground" />
                          <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-[9px] font-medium text-muted-foreground">
                            {item.tag}
                          </span>
                        </div>
                        <p className="mt-2 text-xs font-medium text-foreground leading-snug">
                          {item.category}
                        </p>
                        <p className="mt-1 text-[11px] text-muted-foreground line-clamp-3">
                          {item.question}
                        </p>
                      </div>

                      <div className="mt-3 flex items-center gap-1 text-[10px] font-medium text-primary opacity-0 transition-opacity group-hover:opacity-100">
                        <span>Ask query</span>
                        <ArrowUpRight className="h-3 w-3" />
                      </div>
                    </button>
                  )
                })}
              </div>
            </div>
          ) : (
            <div className="space-y-1">
              {messages.map((message, idx) => {
                const isLastAssistant =
                  isStreaming &&
                  idx === messages.length - 1 &&
                  message.role === "assistant"

                const prevMessage = idx > 0 ? messages[idx - 1] : null
                const showDateDivider =
                  idx === 0 || isDifferentDay(prevMessage?.created_at, message.created_at)

                return (
                  <div key={message.id}>
                    {showDateDivider && message.created_at && (
                      <div className="relative my-5 flex items-center justify-center">
                        <div className="absolute inset-0 flex items-center">
                          <div className="w-full border-t border-border/60" />
                        </div>
                        <span className="relative rounded-full border border-border/70 bg-card px-3 py-1 font-mono text-[10.5px] font-medium text-muted-foreground shadow-2xs">
                          {formatMessageDate(message.created_at)}
                        </span>
                      </div>
                    )}
                    <MessageItem
                      message={message}
                      isStreamingLast={isLastAssistant}
                      onSelectCitation={(cit) => setSelectedCitation(cit)}
                    />
                  </div>
                )
              })}

              {/* Live Pipeline Progress Indicator */}
              {isStreaming && pipelineStatus && (
                <PipelineStatusIndicator status={pipelineStatus} />
              )}
            </div>
          )}

          {error && (
            <div className="my-4 rounded-xl border border-destructive/20 bg-destructive/10 p-3.5 text-xs text-destructive shadow-2xs">
              <p className="font-semibold">Stream Error</p>
              <p className="mt-0.5">{error}</p>
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      </div>

      {/* Input Dock */}
      <MessageInput onSend={sendMessage} disabled={isStreaming} />

      {/* Source Passage Inspection Drawer */}
      <SourcePassageDrawer
        citation={selectedCitation}
        onClose={() => setSelectedCitation(null)}
      />
    </div>
  )
}

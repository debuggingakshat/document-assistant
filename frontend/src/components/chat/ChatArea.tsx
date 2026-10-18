import { useEffect, useMemo, useRef, useState } from "react"
import {
  Activity,
  ArrowDown,
  ArrowUpRight,
  BarChart3,
  Building2,
  Cloud,
  Cpu,
  DollarSign,
  FileText,
  Globe,
  Layers,
  LineChart,
  Megaphone,
  RotateCw,
  Search,
  Server,
  ShieldAlert,
  TrendingUp,
  Zap,
} from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { MessageInput } from "@/components/chat/MessageInput"
import { MessageItem } from "@/components/chat/MessageItem"
import { PipelineStatusIndicator } from "@/components/chat/PipelineStatusIndicator"
import { SourcePassageSheet } from "@/components/chat/SourcePassageSheet"
import { ThemeToggle } from "@/components/chat/ThemeToggle"
import { type Citation, type Message } from "@/lib/api"
import { formatMessageDate, isDifferentDay } from "@/lib/dateUtils"
import { cn } from "@/lib/utils"
import { useChatStream } from "@/lib/useChatStream"

interface ChatAreaProps {
  threadId: string
}

interface Turn {
  id: string
  userMessage?: Message
  assistantVersions: Message[]
}

// Institutional library of 36 curated research inquiries (12 sets of 3)
// covering all 5 coverage issuers, audited line items, segment revenues, CapEx, cash flows, and cross-filing comparisons.
const ALL_STARTER_PROMPTS = [
  // Set 1: Apple Flagship Performance & Margins
  {
    category: "Apple Segment Net Sales",
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

  // Set 2: Microsoft Cloud & AI Infrastructure
  {
    category: "Microsoft Cloud Revenue",
    icon: Cloud,
    question: "What was Microsoft Intelligent Cloud revenue and Azure growth rate in fiscal 2024?",
    tag: "MSFT FY2024 10-K",
  },
  {
    category: "Microsoft AI CapEx Spending",
    icon: Building2,
    question: "What were Microsoft's additions to property and equipment in fiscal 2024 to support cloud and AI?",
    tag: "MSFT FY2024 CapEx",
  },
  {
    category: "Commercial RPO Obligations",
    icon: Layers,
    question: "What was Microsoft's commercial remaining performance obligation (RPO) and recognition schedule in 2024?",
    tag: "MSFT FY2024 RPO",
  },

  // Set 3: Alphabet Search Ecosystem & Cloud
  {
    category: "Google Cloud Profitability",
    icon: Cloud,
    question: "What was Google Cloud revenue and operating income across fiscal 2023 and 2024?",
    tag: "GOOGL Cloud 10-K",
  },
  {
    category: "YouTube Ad Breakdown",
    icon: LineChart,
    question: "What were YouTube advertising revenues in fiscal years 2022, 2023, and 2024?",
    tag: "GOOGL FY2024 Segments",
  },
  {
    category: "Google Traffic Acquisition (TAC)",
    icon: DollarSign,
    question: "What were Alphabet's Traffic Acquisition Costs (TAC) as a percentage of advertising revenues in 2024?",
    tag: "GOOGL FY2024 MD&A",
  },

  // Set 4: Amazon Commerce & AWS Margins
  {
    category: "AWS Segment Operating Margins",
    icon: Server,
    question: "What were AWS net sales and operating income in 2023 and 2024, and what were AWS margins?",
    tag: "AMZN AWS Segments",
  },
  {
    category: "Amazon Advertising Services",
    icon: Megaphone,
    question: "How much revenue did Amazon generate from Advertising Services in 2023 versus 2024?",
    tag: "AMZN Ad Growth",
  },
  {
    category: "Amazon Free Cash Flow Trajectory",
    icon: BarChart3,
    question: "What was Amazon's trailing 12-month Free Cash Flow in 2023 and 2024, and how was it calculated?",
    tag: "AMZN Non-GAAP FCF",
  },

  // Set 5: Nvidia Customers, Architecture & Margins
  {
    category: "Nvidia Customer Concentration",
    icon: ShieldAlert,
    question: "Did Customer A or Customer B account for more than 10% of Nvidia's total revenue in fiscal 2024 or 2025?",
    tag: "NVDA Customer Notes",
  },
  {
    category: "Nvidia Gross Margin Expansion",
    icon: TrendingUp,
    question: "How much did Nvidia's GAAP gross margin expand between fiscal 2023 and fiscal 2024, and why?",
    tag: "NVDA FY2024 Margins",
  },
  {
    category: "Nvidia Compute vs Networking",
    icon: Activity,
    question: "What was the breakdown between Compute revenue and Networking revenue in Nvidia's Data Center segment?",
    tag: "NVDA Compute Split",
  },

  // Set 6: Apple Capital Return & Geographic Markets
  {
    category: "Apple Share Buybacks & Dividends",
    icon: DollarSign,
    question: "How much capital did Apple deploy toward common stock repurchases and dividends in fiscal 2024?",
    tag: "AAPL Cash Return",
  },
  {
    category: "Apple Greater China Trajectory",
    icon: Globe,
    question: "What were Apple's net sales in Greater China across fiscal years 2022, 2023, and 2024?",
    tag: "AAPL Geographic",
  },
  {
    category: "Apple Gross Margin Drivers",
    icon: BarChart3,
    question: "What primary factors drove Apple's products and services gross margin expansion in fiscal 2024?",
    tag: "AAPL FY2024 MD&A",
  },

  // Set 7: Cross-Company Hyperscaler & AI Comparisons
  {
    category: "Cloud Hyperscaler Comparison",
    icon: Server,
    question: "Compare the revenue and growth trajectory of Amazon AWS, Microsoft Cloud, and Google Cloud in 2024.",
    tag: "Cloud Titans FY24",
  },
  {
    category: "AI Infrastructure CapEx Race",
    icon: Zap,
    question: "Compare the capital expenditures (CapEx) of Microsoft, Alphabet, and Amazon in fiscal 2024.",
    tag: "Big Tech CapEx",
  },
  {
    category: "Hardware Gross Margin Comparison",
    icon: TrendingUp,
    question: "Compare Apple's Products gross margin with Nvidia's overall gross margin in fiscal 2024.",
    tag: "Hardware Margins",
  },

  // Set 8: Core Sanity Checks & Testing Prompts
  {
    category: "Apple Revenue & Net Income",
    icon: Search,
    question: "What was Apple's total net sales, gross margin, and net income in fiscal 2024?",
    tag: "AAPL FY2024 Summary",
  },
  {
    category: "Microsoft Gaming & Activision",
    icon: Layers,
    question: "How did the Activision Blizzard acquisition impact Microsoft's More Personal Computing segment in 2024?",
    tag: "MSFT M&A Impact",
  },
  {
    category: "Alphabet Headcount & Severance",
    icon: FileText,
    question: "How much did Alphabet record in employee severance and related charges during 2023 and 2024?",
    tag: "GOOGL Restructuring",
  },

  // Set 9: Research & Development (R&D) & Innovation Allocation
  {
    category: "Alphabet R&D Expenditure",
    icon: Cpu,
    question: "What were Alphabet's research and development (R&D) expenses in 2023 and 2024, and what percentage of revenue did it represent?",
    tag: "GOOGL FY2024 R&D",
  },
  {
    category: "Apple Wearables & Home Segment",
    icon: BarChart3,
    question: "What was the annual net sales trend for Apple's Wearables, Home, and Accessories segment from 2022 to 2024?",
    tag: "AAPL Product Lines",
  },
  {
    category: "Microsoft Office 365 Commercial",
    icon: Building2,
    question: "What drove revenue growth in Microsoft's Productivity and Business Processes segment and Office 365 Commercial in 2024?",
    tag: "MSFT Office 365",
  },

  // Set 10: Logistics, Fulfillment & Infrastructure Costs
  {
    category: "Amazon Shipping & Fulfillment Costs",
    icon: Server,
    question: "How much did Amazon spend on fulfillment and shipping costs in 2023 and 2024, and what was the growth rate?",
    tag: "AMZN Cost Structure",
  },
  {
    category: "Nvidia Supply & Inventory Commitments",
    icon: ShieldAlert,
    question: "What were Nvidia's outstanding purchase obligations and inventory levels heading into fiscal 2025?",
    tag: "NVDA Supply Chain",
  },
  {
    category: "Google Services Operating Income",
    icon: LineChart,
    question: "What was the operating income and operating margin for Google Services (Search, YouTube, Android) in 2024?",
    tag: "GOOGL Core Margins",
  },

  // Set 11: International Exposure & Foreign Exchange Headwinds
  {
    category: "Apple Foreign Currency Hedging",
    icon: Globe,
    question: "Did foreign currency exchange rate fluctuations create headwinds for Apple's net sales in fiscal 2023 or 2024?",
    tag: "AAPL FX Disclosures",
  },
  {
    category: "Amazon International Segment Performance",
    icon: Megaphone,
    question: "What was the operating income or loss for Amazon's International segment in 2022, 2023, and 2024?",
    tag: "AMZN Global Retail",
  },
  {
    category: "Microsoft Dividend Policy & Debt",
    icon: DollarSign,
    question: "How much total cash dividend per share did Microsoft declare and pay to common shareholders in fiscal 2024?",
    tag: "MSFT Dividends",
  },

  // Set 12: Professional Valuation & Operating Leverage Metrics
  {
    category: "Nvidia Automotive Trajectory",
    icon: Activity,
    question: "What was Nvidia's Automotive revenue in fiscal 2024 and 2025, and what were the primary growth drivers?",
    tag: "NVDA Automotive",
  },
  {
    category: "Big Tech Employee Headcount Comparison",
    icon: Layers,
    question: "Compare the total full-time employee headcount disclosures of Microsoft, Apple, and Alphabet in their latest 10-K filings.",
    tag: "Workforce Metrics",
  },
  {
    category: "Alphabet Google Other Revenues",
    icon: Search,
    question: "What were Google subscriptions, platforms, and devices revenues (formerly Google Other) in 2024?",
    tag: "GOOGL Subscriptions",
  },
]

const PROMPTS_PER_SET = 3
const TOTAL_PROMPT_SETS = 12

export function ChatArea({ threadId }: ChatAreaProps) {
  const { messages, isLoading, isStreaming, pipelineStatus, error, sendMessage } =
    useChatStream({ threadId })
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null)
  const [activeVersionMap, setActiveVersionMap] = useState<Record<string, number>>({})

  // Internal rotating starter prompt state (cycles quietly through 12 sets of 3 prompts)
  const [promptSetIndex, setPromptSetIndex] = useState<number>(() => {
    try {
      const saved = sessionStorage.getItem("meridian_prompt_set_idx")
      if (saved !== null) {
        const next = (parseInt(saved, 10) + 1) % TOTAL_PROMPT_SETS
        sessionStorage.setItem("meridian_prompt_set_idx", String(next))
        return next
      }
    } catch {
      // ignore storage access errors
    }
    return Math.floor(Math.random() * TOTAL_PROMPT_SETS)
  })

  // Whenever the user clicks "New Research" or changes threads, automatically rotate internally to the next set
  useEffect(() => {
    setPromptSetIndex((prev) => {
      const next = (prev + 1) % TOTAL_PROMPT_SETS
      try {
        sessionStorage.setItem("meridian_prompt_set_idx", String(next))
      } catch {
        // ignore
      }
      return next
    })
  }, [threadId])

  const activePrompts = useMemo(() => {
    const start = promptSetIndex * PROMPTS_PER_SET
    return ALL_STARTER_PROMPTS.slice(start, start + PROMPTS_PER_SET)
  }, [promptSetIndex])

  // Smart auto-scroll state
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const [showScrollBottom, setShowScrollBottom] = useState(false)

  // Group messages into logical turns (prompt + response versions)
  const turns = useMemo(() => {
    const result: Turn[] = []
    let currentTurn: Turn | null = null

    for (const msg of messages) {
      if (msg.role === "user") {
        currentTurn = {
          id: msg.id,
          userMessage: msg,
          assistantVersions: [],
        }
        result.push(currentTurn)
      } else if (msg.role === "assistant") {
        const parentId = msg.ai_sdk_metadata?.parent_user_message_id
        if (parentId) {
          const matchingTurn = result.find(
            (t) => t.userMessage?.id === parentId || t.id === parentId
          )
          if (matchingTurn) {
            matchingTurn.assistantVersions.push(msg)
            continue
          }
        }

        if (currentTurn) {
          currentTurn.assistantVersions.push(msg)
        } else {
          result.push({
            id: msg.id,
            assistantVersions: [msg],
          })
        }
      }
    }

    return result
  }, [messages])

  function handleSelectVersion(turnId: string, index: number) {
    setActiveVersionMap((prev) => ({
      ...prev,
      [turnId]: index,
    }))
  }

  function handleRegenerate(turn: Turn) {
    if (!turn.userMessage || isStreaming) return
    const nextIndex = turn.assistantVersions.length
    setActiveVersionMap((prev) => ({
      ...prev,
      [turn.id]: nextIndex,
    }))
    void sendMessage(turn.userMessage.content, undefined, {
      parentUserMessageId: turn.userMessage.id,
    })
  }

  function handleRetryPrompt(userMsg: Message) {
    if (isStreaming) return
    void sendMessage(userMsg.content, undefined, {
      parentUserMessageId: userMsg.id,
    })
  }

  // Detect if user has scrolled away from the bottom
  function handleScroll() {
    const el = scrollContainerRef.current
    if (!el) return
    const isAtBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 120
    setShowScrollBottom(!isAtBottom)
  }

  function scrollToBottom(behavior: ScrollBehavior = "smooth") {
    bottomRef.current?.scrollIntoView({ behavior })
    setShowScrollBottom(false)
  }

  // Only auto-scroll if the user is already near the bottom
  useEffect(() => {
    if (!showScrollBottom) {
      bottomRef.current?.scrollIntoView({ behavior: isStreaming ? "auto" : "smooth" })
    }
  }, [messages, isStreaming, pipelineStatus, showScrollBottom])

  // Get the most recent user prompt if any
  const lastUserTurn = turns.slice().reverse().find((t) => t.userMessage)

  return (
    <div className="relative flex h-screen flex-1 flex-col overflow-hidden bg-background">
      {/* Top Header Bar */}
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-border/80 px-4 select-none">
        <div className="flex items-center gap-3">
          {/* Session breadcrumb */}
          <div className="flex items-center gap-2">
            <span className="size-2 rounded-full bg-emerald-500 ring-2 ring-emerald-500/20" />
            <span className="text-xs font-semibold text-foreground">
              SEC Research Session
            </span>
          </div>
        </div>

        {/* Right Header Controls */}
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="hidden sm:inline-flex text-[11px] font-mono">
            Coverage: 5 Companies (FY21–25)
          </Badge>

          <div className="h-4 w-px bg-border/60 hidden sm:inline" />

          <ThemeToggle />
        </div>
      </header>

      {/* Messages Scrollable Viewport */}
      <div
        ref={scrollContainerRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto px-4 py-6 md:px-8"
      >
        <div className="mx-auto max-w-3xl">
          {isLoading ? (
            <div className="flex h-64 flex-col items-center justify-center gap-2 text-xs text-muted-foreground">
              <span className="size-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
              <span>Loading conversation history & citations...</span>
            </div>
          ) : turns.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center select-none">
              {/* Meridian Research Logo and Text */}
              <div className="flex items-center justify-center">
                <img
                  src="/meridian-logo-light.png"
                  alt="Meridian Research"
                  className="h-12 w-auto object-contain dark:hidden"
                />
                <img
                  src="/meridian-logo-dark.png"
                  alt="Meridian Research"
                  className="h-12 w-auto object-contain hidden dark:block"
                />
              </div>

              {/* Document Assistant Subtitle */}
              <h2 className="mt-3 text-base font-semibold tracking-wide text-foreground">
                Document Assistant
              </h2>

              <p className="mt-1.5 max-w-md text-xs leading-relaxed text-muted-foreground">
                Institutional SEC 10-K analysis across Apple, Amazon, Alphabet, Microsoft, and Nvidia with fail-closed grounding verification.
              </p>

              {/* Starter Question Header - Clean institutional typography */}
              <div className="mt-8 flex w-full max-w-2xl items-center px-0.5">
                <p className="text-[11px] font-semibold tracking-wider uppercase text-muted-foreground/80">
                  Suggested Research Inquiries
                </p>
              </div>

              {/* Starter Question Cards */}
              <div className="mt-2.5 grid w-full max-w-2xl gap-3 sm:grid-cols-3">
                {activePrompts.map((item) => {
                  const Icon = item.icon
                  return (
                    <button
                      key={item.category + item.tag}
                      type="button"
                      onClick={() => void sendMessage(item.question)}
                      className="group flex flex-col justify-between rounded-xl border border-border/70 bg-card p-3.5 text-left shadow-2xs transition-all hover:border-foreground/30 hover:shadow-xs cursor-pointer hover:bg-accent/15"
                    >
                      <div>
                        <div className="flex items-center justify-between text-muted-foreground">
                          <Icon className="size-4 text-foreground" />
                          <Badge variant="muted" className="font-mono text-[9px]">
                            {item.tag}
                          </Badge>
                        </div>
                        <p className="mt-2 text-xs font-medium text-foreground leading-snug">
                          {item.category}
                        </p>
                        <p className="mt-1 text-[11px] text-muted-foreground line-clamp-3">
                          {item.question}
                        </p>
                      </div>

                      <div className="mt-3 flex items-center gap-1 text-[10px] font-medium text-primary opacity-0 transition-opacity group-hover:opacity-100">
                        <span>Run analysis</span>
                        <ArrowUpRight className="size-3" />
                      </div>
                    </button>
                  )
                })}
              </div>
            </div>
          ) : (
            <div className="space-y-1">
              {turns.map((turn, idx) => {
                const prevTurn = idx > 0 ? turns[idx - 1] : null
                const firstMsgOfTurn = turn.userMessage || turn.assistantVersions[0]
                const prevLastMsg =
                  prevTurn?.assistantVersions[prevTurn.assistantVersions.length - 1] ||
                  prevTurn?.userMessage
                const showDateDivider =
                  idx === 0 ||
                  isDifferentDay(prevLastMsg?.created_at, firstMsgOfTurn?.created_at)

                const savedIdx = activeVersionMap[turn.id]
                const activeVersionIdx =
                  savedIdx !== undefined &&
                  savedIdx >= 0 &&
                  savedIdx < turn.assistantVersions.length
                    ? savedIdx
                    : Math.max(0, turn.assistantVersions.length - 1)
                const activeAssistantMsg = turn.assistantVersions[activeVersionIdx]
                const hasAssistantResponse = turn.assistantVersions.length > 0

                return (
                  <div key={turn.id}>
                    {showDateDivider && firstMsgOfTurn?.created_at && (
                      <div className="relative my-5 flex items-center justify-center">
                        <div className="absolute inset-0 flex items-center">
                          <div className="w-full border-t border-border/60" />
                        </div>
                        <span className="relative rounded-full border border-border/70 bg-card px-3 py-1 font-mono text-[10.5px] font-medium text-muted-foreground shadow-2xs">
                          {formatMessageDate(firstMsgOfTurn.created_at)}
                        </span>
                      </div>
                    )}

                    {/* User Prompt */}
                    {turn.userMessage && (
                      <MessageItem
                        message={turn.userMessage}
                        onRetryPrompt={() => handleRetryPrompt(turn.userMessage!)}
                        hasResponse={hasAssistantResponse}
                        isStreaming={isStreaming}
                      />
                    )}

                    {/* If user message has no response yet (e.g. after error or interrupted stream) */}
                    {turn.userMessage && !hasAssistantResponse && !isStreaming && (
                      <div className="flex justify-end pr-1 mt-1 mb-2">
                        <button
                          type="button"
                          onClick={() => handleRetryPrompt(turn.userMessage!)}
                          className="flex items-center gap-1.5 rounded-lg border border-border/70 bg-card px-2.5 py-1 text-[11px] font-medium text-muted-foreground hover:border-primary/40 hover:bg-muted hover:text-foreground cursor-pointer shadow-2xs transition-all"
                          title="Generate response for this prompt"
                        >
                          <RotateCw className="size-3 text-primary" />
                          <span>Generate response</span>
                        </button>
                      </div>
                    )}

                    {/* Assistant Response with Version Branching */}
                    {activeAssistantMsg && (
                      <MessageItem
                        message={activeAssistantMsg}
                        versions={turn.assistantVersions}
                        currentVersionIndex={activeVersionIdx}
                        onSelectVersion={(newIdx) => handleSelectVersion(turn.id, newIdx)}
                        onRegenerate={
                          turn.userMessage ? () => handleRegenerate(turn) : undefined
                        }
                        isStreaming={isStreaming}
                        isStreamingLast={
                          isStreaming &&
                          activeAssistantMsg.id === messages[messages.length - 1]?.id
                        }
                        pipelineStatus={
                          isStreaming &&
                          activeAssistantMsg.id === messages[messages.length - 1]?.id
                            ? pipelineStatus
                            : null
                        }
                        onSelectCitation={(cit) => setSelectedCitation(cit)}
                      />
                    )}
                  </div>
                )
              })}

              {/* Live Technical Pipeline Telemetry */}
              {isStreaming && pipelineStatus && (
                <PipelineStatusIndicator status={pipelineStatus} />
              )}
            </div>
          )}

          {/* Stream Error Banner with Interactive Retry Button */}
          {error && (
            <div className="my-4 flex items-center justify-between rounded-xl border border-destructive/20 bg-destructive/10 p-3.5 text-xs text-destructive shadow-2xs">
              <div>
                <p className="font-semibold">Generation Interrupted</p>
                <p className="mt-0.5">{error}</p>
              </div>
              {lastUserTurn?.userMessage && (
                <button
                  type="button"
                  onClick={() => handleRetryPrompt(lastUserTurn.userMessage!)}
                  disabled={isStreaming}
                  className="flex items-center gap-1.5 rounded-lg border border-destructive/30 bg-card px-2.5 py-1 text-xs font-medium text-destructive hover:bg-destructive/10 cursor-pointer shadow-2xs transition-all shrink-0 ml-3 disabled:opacity-40"
                  title="Retry generation"
                >
                  <RotateCw className={cn("size-3", isStreaming && "animate-spin")} />
                  <span>Retry</span>
                </button>
              )}
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      </div>

      {/* Floating "Jump to bottom" Button when scrolled up */}
      {showScrollBottom && (
        <button
          type="button"
          onClick={() => scrollToBottom("smooth")}
          className="absolute bottom-24 right-8 z-20 flex items-center gap-1.5 rounded-full border border-border/80 bg-card/90 px-3 py-1.5 text-xs font-medium text-foreground shadow-lg backdrop-blur-md transition-all hover:bg-card hover:scale-105 active:scale-95 cursor-pointer"
        >
          {isStreaming && (
            <span className="size-1.5 animate-ping rounded-full bg-primary" />
          )}
          <span>Jump to latest</span>
          <ArrowDown className="size-3 text-muted-foreground" />
        </button>
      )}

      {/* Input Dock */}
      <MessageInput onSend={sendMessage} disabled={isStreaming} />

      {/* Slide-Over Source Passage Sheet Inspector */}
      <SourcePassageSheet
        citation={selectedCitation}
        onClose={() => setSelectedCitation(null)}
      />
    </div>
  )
}

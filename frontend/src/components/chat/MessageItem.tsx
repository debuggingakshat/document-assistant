import { useMemo, useState } from "react"
import {
  AlertTriangle,
  Check,
  ChevronLeft,
  ChevronRight,
  Clock,
  Copy,
  ExternalLink,
  FileSpreadsheet,
  RotateCw,
  ShieldCheck,
  User,
} from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { FinancialTable } from "@/components/chat/FinancialTable"
import { highlightFinancialFigures } from "@/components/chat/SourcePassageSheet"
import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from "@/components/ui/hover-card"
import type { Citation, Message, PipelineStatus } from "@/lib/api"
import { formatFullDateTime, formatMessageTime } from "@/lib/dateUtils"
import { cn } from "@/lib/utils"

interface MessageItemProps {
  message: Message
  isStreaming?: boolean
  isStreamingLast?: boolean
  versions?: Message[]
  currentVersionIndex?: number
  onSelectVersion?: (index: number) => void
  onRegenerate?: () => void
  onRetryPrompt?: () => void
  hasResponse?: boolean
  pipelineStatus?: PipelineStatus | null
  onSelectCitation?: (citation: Citation) => void
}

export function MessageItem({
  message,
  isStreaming,
  isStreamingLast,
  versions,
  currentVersionIndex = 0,
  onSelectVersion,
  onRegenerate,
  onRetryPrompt,
  hasResponse = true,
  pipelineStatus,
  onSelectCitation,
}: MessageItemProps) {
  const isUser = message.role === "user"
  const [copied, setCopied] = useState(false)

  const modelBadge = useMemo(() => {
    const raw = message.ai_sdk_metadata?.model
    if (raw === "gemini-2.5-pro") return "Gemini 2.5 Pro"
    if (raw === "gemini-2.0-flash-lite") return "Gemini 2.0 Flash Lite"
    if (raw === "gemini-2.5-flash") return "Gemini 2.5 Flash"
    return "Gemini 2.5 Flash"
  }, [message.ai_sdk_metadata])

  const timeDisplay = formatMessageTime(message.created_at)
  const fullDateTimeDisplay = formatFullDateTime(message.created_at)

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(message.content)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Clipboard failed or denied
    }
  }

  // Calculate 10-bar progress during initial generation before tokens arrive
  const progressInfo = useMemo(() => {
    if (!pipelineStatus) {
      return { percent: 10, label: "Initializing pipeline...", filledBars: 1 }
    }
    const stage = pipelineStatus.stage
    if (stage === "searching") {
      return { percent: 25, label: "Step 1 of 4: Hybrid Retrieval", filledBars: 3 }
    }
    if (stage === "fusion") {
      return { percent: 50, label: "Step 2 of 4: Rank Fusion", filledBars: 5 }
    }
    if (stage === "reasoning") {
      return { percent: 75, label: "Step 3 of 4: Agent Synthesis", filledBars: 8 }
    }
    if (stage === "validating") {
      return { percent: 90, label: "Step 4 of 4: Grounding Verification", filledBars: 9 }
    }
    if (stage === "complete") {
      return { percent: 100, label: "Verification complete", filledBars: 10 }
    }
    return { percent: 50, label: "Processing SEC disclosures...", filledBars: 5 }
  }, [pipelineStatus])

  // Map citation_index to Citation object + parse inline source entries from text
  const citationMap = useMemo(() => {
    const map = new Map<number, Citation>()
    if (message.citations) {
      for (const c of message.citations) {
        const numIdx = Number(c.citation_index)
        if (!isNaN(numIdx)) {
          map.set(numIdx, c)
        }
      }
    }

    // Also extract source lines from message text if model hallucinated/listed them:
    // e.g. "- [^5] Amazon.com, Inc. (AMZN) FY2023 10-K, Item 8 - Note 1 (Accounting Policies)"
    const sourceLineRegex = /(?:^|\n)\s*-\s*\[\^(\d+)\]\s*([^,\n]+)(?:,\s*([^\n]+))?/g
    let match: RegExpExecArray | null
    while ((match = sourceLineRegex.exec(message.content)) !== null) {
      const idx = parseInt(match[1], 10)
      if (!map.has(idx)) {
        const fullDetail = match[0].trim()
        const compOrSec = match[2]?.trim() || "SEC Source"
        const rest = match[3]?.trim() || ""

        const tickerMatch = fullDetail.match(/\(([A-Z]{1,5})\)/)
        const fyMatch = fullDetail.match(/FY(\d{4})/i)

        map.set(idx, {
          chunk_id: `extracted-${idx}`,
          citation_index: idx,
          ticker: tickerMatch ? tickerMatch[1] : (message.citations?.[0]?.ticker || "SEC"),
          company_name: compOrSec.replace(/\s*\([A-Z]+\)/, "").trim(),
          filing_type: "10-K",
          fiscal_year: fyMatch ? parseInt(fyMatch[1], 10) : (message.citations?.[0]?.fiscal_year || 2023),
          section: rest || compOrSec,
          snippet: fullDetail.replace(/^-\s*\[\^\d+\]\s*/, ""),
        })
      }
    }

    return map
  }, [message.citations, message.content])

  // Render inline formatting (citations, bold, italics, code, superscripts)
  function renderInlineSpans(inlineText: string): React.ReactNode {
    const inlineRegex = /(\[\^\d+\]|\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g
    const parts = inlineText.split(inlineRegex)

    return parts.map((part, i) => {
      if (!part) return null

      // Interactive Citation Chip [^n]
      const citMatch = part.match(/^\[\^(\d+)\]$/)
      if (citMatch) {
        const index = parseInt(citMatch[1], 10)
        const cit: Citation =
          citationMap.get(index) ||
          message.citations?.find((c) => c.citation_index === index) ||
          (message.citations && message.citations.length >= index
            ? message.citations[index - 1]
            : undefined) ||
          (message.citations && message.citations.length > 0
            ? message.citations[message.citations.length - 1]
            : undefined) || {
            chunk_id: `cit-${index}`,
            citation_index: index,
            ticker: message.citations?.[0]?.ticker || "SEC",
            company_name: "SEC Ingested Filing",
            filing_type: "10-K",
            fiscal_year: 2023,
            section: "Financial Statements & Notes",
            snippet: `Referenced SEC 10-K filing passage citation [^${index}].`,
          }

        return (
          <HoverCard key={i} openDelay={150} closeDelay={100}>
            <HoverCardTrigger asChild>
              <button
                type="button"
                onClick={() => onSelectCitation?.(cit)}
                className="inline-flex items-center gap-0.5 rounded px-1.5 py-0.5 mx-0.5 font-mono text-[11px] font-semibold bg-primary/10 text-primary hover:bg-primary/20 hover:ring-1 hover:ring-primary/40 align-baseline cursor-pointer transition-all"
              >
                <span>[^{index}]</span>
              </button>
            </HoverCardTrigger>
            <HoverCardContent className="w-88 space-y-2 text-left shadow-lg border border-border/80">
              <div className="flex items-center justify-between border-b border-border/60 pb-1.5">
                <div className="flex items-center gap-1.5 truncate">
                  <span className="flex size-5 shrink-0 items-center justify-center rounded bg-primary/10 font-mono text-[10px] font-bold text-primary border border-primary/25">
                    [^{index}]
                  </span>
                  <span className="font-semibold text-foreground truncate text-xs">
                    {cit.company_name || cit.ticker || "SEC 10-K Reference"}
                  </span>
                </div>
                <Badge variant="ticker">{cit.ticker || "10-K"}</Badge>
              </div>

              <p className="font-mono text-[10px] text-muted-foreground truncate">
                {cit.filing_type || "10-K"} · FY{cit.fiscal_year || "Latest"} · {cit.section || "Disclosures"}
              </p>

              {/* Cited Evidence with Highlighted Financial Figures */}
              <div className="rounded-md border border-primary/25 bg-primary/5 p-2.5 text-[11px] text-foreground/90 leading-relaxed max-h-28 overflow-y-auto">
                <span className="text-[9.5px] font-mono font-bold text-primary block mb-1 uppercase tracking-wider">
                  Cited Supporting Evidence:
                </span>
                <p className="line-clamp-3 italic">
                  {highlightFinancialFigures(cit.snippet || cit.full_context_text || "Referenced SEC disclosure context.")}
                </p>
              </div>

              <div className="pt-0.5 flex items-center justify-between text-[10px] text-primary font-medium">
                <span>Click to inspect full passage & metrics</span>
                <ExternalLink className="size-2.5" />
              </div>
            </HoverCardContent>
          </HoverCard>
        )
      }

      // Bold text **bold**
      if (part.startsWith("**") && part.endsWith("**") && part.length >= 4) {
        return (
          <strong key={i} className="font-semibold text-foreground">
            {part.slice(2, -2)}
          </strong>
        )
      }

      // Italic text *italic*
      if (part.startsWith("*") && part.endsWith("*") && part.length >= 2) {
        return (
          <em key={i} className="italic text-foreground/90">
            {part.slice(1, -1)}
          </em>
        )
      }

      // Inline code `code`
      if (part.startsWith("`") && part.endsWith("`") && part.length >= 2) {
        return (
          <code
            key={i}
            className="rounded bg-muted px-1.5 py-0.5 font-mono text-[11px] text-foreground border border-border/60"
          >
            {part.slice(1, -1)}
          </code>
        )
      }

      return <span key={i}>{part}</span>
    })
  }

  // Render text blocks containing paragraphs, headings, and lists
  function renderTextBlock(textBlock: string, blockKey: string | number) {
    const lines = textBlock.split("\n")
    const elements: React.ReactNode[] = []
    let listBuffer: string[] = []

    function flushList() {
      if (listBuffer.length > 0) {
        const currentItems = [...listBuffer]
        elements.push(
          <ul
            key={`ul-${elements.length}`}
            className="my-2 space-y-1 pl-5 list-disc text-[13px] text-foreground/90"
          >
            {currentItems.map((item, idx) => (
              <li key={idx} className="leading-relaxed">
                {renderInlineSpans(item)}
              </li>
            ))}
          </ul>
        )
        listBuffer = []
      }
    }

    for (let lIdx = 0; lIdx < lines.length; lIdx++) {
      const rawLine = lines[lIdx]
      const trimmed = rawLine.trim()

      if (!trimmed) {
        flushList()
        continue
      }

      // Heading 3: ### Title
      if (trimmed.startsWith("### ")) {
        flushList()
        elements.push(
          <h3
            key={`h3-${lIdx}`}
            className="mt-3.5 mb-1.5 font-bold text-foreground text-[14px] tracking-tight"
          >
            {renderInlineSpans(trimmed.replace(/^###\s*/, ""))}
          </h3>
        )
        continue
      }

      // Heading 2: ## Title
      if (trimmed.startsWith("## ")) {
        flushList()
        elements.push(
          <h2
            key={`h2-${lIdx}`}
            className="mt-4 mb-2 font-bold text-foreground text-[15px] tracking-tight border-b border-border/40 pb-1"
          >
            {renderInlineSpans(trimmed.replace(/^##\s*/, ""))}
          </h2>
        )
        continue
      }

      // Heading 1: # Title
      if (trimmed.startsWith("# ")) {
        flushList()
        elements.push(
          <h1
            key={`h1-${lIdx}`}
            className="mt-4 mb-2 font-bold text-foreground text-[16px] tracking-tight"
          >
            {renderInlineSpans(trimmed.replace(/^#\s*/, ""))}
          </h1>
        )
        continue
      }

      // List Item: - item or * item (not footnote)
      if (/^[-*]\s+/.test(trimmed) && !trimmed.startsWith("*¹") && !trimmed.startsWith("*²")) {
        listBuffer.push(trimmed.replace(/^[-*]\s+/, ""))
        continue
      }

      flushList()

      // Table footnotes e.g. *¹ Previously reported as ... or *² Total revenues...
      if (/^\*?[¹²³\*]/.test(trimmed)) {
        elements.push(
          <p
            key={`fn-${lIdx}`}
            className="my-1 font-mono text-[11px] italic text-muted-foreground/80 leading-normal"
          >
            {renderInlineSpans(trimmed)}
          </p>
        )
        continue
      }

      // Standard Paragraph
      elements.push(
        <p key={`p-${lIdx}`} className="my-1.5 leading-relaxed text-foreground/95">
          {renderInlineSpans(rawLine)}
        </p>
      )
    }

    flushList()
    return (
      <div key={blockKey} className="space-y-0.5">
        {elements}
      </div>
    )
  }

  // Format content with interactive GFM tables, HoverCards, and citation chips
  function renderFormattedContent(text: string) {
    const hasGroundingWarning =
      text.includes("[!WARNING]") || text.includes("Grounding Verification Alert")

    // Match Markdown Tables (header row + separator row + body rows)
    const tableRegex = /((?:^|\n)\|[^\n]+\|\r?\n\|[\s:|-]+\|\r?\n(?:\|[^\n]+\|\r?\n?)+)/g
    const blocks: Array<{ type: "text" | "table"; content: string }> = []

    let lastIndex = 0
    let match: RegExpExecArray | null
    while ((match = tableRegex.exec(text)) !== null) {
      const start = match.index
      const end = tableRegex.lastIndex
      if (start > lastIndex) {
        blocks.push({ type: "text", content: text.slice(lastIndex, start) })
      }
      blocks.push({ type: "table", content: match[0].trim() })
      lastIndex = end
    }
    if (lastIndex < text.length) {
      blocks.push({ type: "text", content: text.slice(lastIndex) })
    }

    let tableCounter = 1

    return (
      <>
        {blocks.map((block, idx) => {
          if (block.type === "table") {
            return (
              <FinancialTable
                key={idx}
                rawMarkdownTable={block.content}
                renderInlineFormatted={renderInlineSpans}
                tableIndex={tableCounter++}
              />
            )
          }
          return renderTextBlock(block.content, idx)
        })}

        {hasGroundingWarning && (
          <div className="mt-3 flex items-start gap-2.5 rounded-xl border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive">
            <AlertTriangle className="size-4 shrink-0 text-destructive mt-0.5" />
            <div>
              <p className="font-semibold text-foreground">
                Grounding Verification Notice
              </p>
              <p className="text-[11px] text-muted-foreground mt-0.5">
                Some claims in this response could not be verified against the ingested SEC corpus. Unverified claims are flagged for analyst review.
              </p>
            </div>
          </div>
        )}
      </>
    )
  }

  return (
    <div
      className={cn(
        "group relative flex w-full gap-3 py-3 transition-colors",
        isUser ? "justify-end" : "justify-start"
      )}
    >
      {/* Assistant Avatar: Meridian Emblem */}
      {!isUser && (
        <div className="flex size-7 shrink-0 items-center justify-center rounded-lg border border-border/80 bg-card p-1 shadow-2xs mt-0.5">
          <img
            src="/meridian-emblem-light.png"
            alt="Meridian Research"
            className={cn("size-4.5 object-contain dark:hidden", isStreamingLast && "animate-pulse")}
          />
          <img
            src="/meridian-emblem-dark.png"
            alt="Meridian Research"
            className={cn("size-4.5 object-contain hidden dark:block", isStreamingLast && "animate-pulse")}
          />
        </div>
      )}

      <div
        className={cn(
          "relative flex flex-col max-w-[85%]",
          isUser ? "items-end" : "items-start"
        )}
      >
        {/* Header bar with Sender & Timestamp */}
        <div
          className={cn(
            "mb-1 flex items-center gap-1.5 text-[11px] text-muted-foreground px-1",
            isUser ? "flex-row-reverse" : "flex-row"
          )}
        >
          <span className="font-medium text-foreground">
            {isUser ? "You" : "Document Assistant"}
          </span>

          {/* Quick retry button for user prompts */}
          {isUser && onRetryPrompt && (
            <button
              type="button"
              onClick={onRetryPrompt}
              disabled={isStreaming}
              className={cn(
                "flex size-5 items-center justify-center rounded text-muted-foreground transition-all hover:bg-muted hover:text-foreground cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed",
                hasResponse ? "opacity-0 group-hover:opacity-100" : "opacity-100 text-foreground"
              )}
              title="Resend prompt & generate response"
            >
              <RotateCw className={cn("size-3", isStreaming && "animate-spin")} />
            </button>
          )}

          {!isUser && (
            <span className="inline-flex items-center gap-1.5 rounded-md border border-border/60 bg-muted/70 px-1.5 py-0.5 font-mono text-[9.5px] text-muted-foreground shadow-2xs">
              <img
                src="/gemini-logo.png"
                alt="Gemini"
                className="size-3 object-contain shrink-0"
              />
              <span>{modelBadge}</span>
            </span>
          )}

          {timeDisplay && (
            <span
              className="flex items-center gap-1 font-mono text-[10px] text-muted-foreground/75 cursor-default"
              title={fullDateTimeDisplay}
            >
              <Clock className="size-2.5 opacity-60" />
              {timeDisplay}
            </span>
          )}
        </div>

        {/* Message Box (Subtle card for assistant, refined soft neutral bubble for user) */}
        <div
          className={cn(
            "relative w-full rounded-2xl px-4 py-3 text-[13.5px] leading-relaxed tracking-normal shadow-xs",
            isUser
              ? "border border-border/80 bg-muted/70 text-foreground shadow-2xs"
              : "border border-border/70 bg-card text-foreground"
          )}
        >
          {/* While generating and no content has arrived yet: Segmented 10-Bar Indicator */}
          {!isUser && isStreamingLast && !message.content ? (
            <div className="flex flex-col gap-2.5 py-1 select-none">
              {/* Interactive 10-Bar Segmented Progress Indicator */}
              <div
                className="inline-flex items-center gap-2.5 w-fit rounded-lg border border-border/60 bg-muted/40 px-2.5 py-1.5 shadow-2xs backdrop-blur-xs transition-all hover:border-primary/40 hover:bg-muted/70 cursor-pointer group/bars"
                title={`${progressInfo.percent}% complete · ${progressInfo.label} (Click to inspect telemetry)`}
                onClick={() => {
                  const el = document.getElementById("pipeline-telemetry-card")
                  if (el) {
                    el.scrollIntoView({ behavior: "smooth", block: "nearest" })
                  }
                }}
              >
                {/* Shortened 10-bar cluster */}
                <div className="flex items-center gap-1">
                  {Array.from({ length: 10 }).map((_, barIdx) => {
                    const isFilled = barIdx < progressInfo.filledBars
                    const isLeading = barIdx === progressInfo.filledBars - 1

                    return (
                      <span
                        key={barIdx}
                        className={cn(
                          "inline-block h-2.5 w-1 rounded-full transition-all duration-300",
                          isFilled
                            ? "bg-neutral-900 dark:bg-neutral-100 shadow-2xs group-hover/bars:scale-y-115 group-hover/bars:brightness-110"
                            : "bg-neutral-200 dark:bg-neutral-800/80 group-hover/bars:opacity-60",
                          isLeading && "animate-pulse ring-1 ring-foreground/50 shadow-xs"
                        )}
                      />
                    )
                  })}
                </div>

                {/* Progress Percentage & Step Indicator */}
                <div className="flex items-center gap-1.5 font-mono text-[11px]">
                  <span className="font-bold text-foreground">
                    {progressInfo.percent}%
                  </span>
                  <span className="text-muted-foreground font-medium text-[10.5px]">
                    · {progressInfo.label}
                  </span>
                </div>
              </div>

              {/* Live pipeline telemetry micro-description */}
              <p className="text-[11.5px] text-muted-foreground/85 font-normal leading-normal animate-pulse pl-0.5">
                {pipelineStatus?.message || "Executing hybrid keyword and vector retrieval across SEC 10-K filings..."}
              </p>
            </div>
          ) : (
            <div className={cn("break-words font-normal", isUser ? "whitespace-pre-wrap text-foreground" : "space-y-1 text-[13.5px]")}>
              {isUser ? (
                message.content
              ) : (
                renderFormattedContent(message.content)
              )}
              {!isUser && isStreamingLast && (
                <span className="inline-block h-2.5 w-1 rounded-full animate-pulse bg-foreground align-middle ml-1" />
              )}
            </div>
          )}

          {/* Verified Sources Pill List */}
          {!isUser && message.citations && message.citations.length > 0 && (
            <div className="mt-3.5 pt-3 border-t border-border/50">
              <div className="flex items-center gap-1.5 text-[10.5px] font-semibold text-muted-foreground uppercase tracking-wider mb-2 font-mono">
                <ShieldCheck className="size-3.5 text-primary" />
                <span>Verified Sources ({message.citations.length})</span>
              </div>

              <div className="flex flex-wrap gap-1.5">
                {message.citations.map((c) => (
                  <button
                    key={c.citation_index}
                    type="button"
                    onClick={() => onSelectCitation?.(c)}
                    className="flex items-center gap-1.5 rounded-lg border border-border/70 bg-muted/40 px-2.5 py-1 text-left text-[11px] text-muted-foreground transition-all hover:border-primary/40 hover:bg-muted hover:text-foreground cursor-pointer shadow-2xs"
                    title={c.snippet || "View source excerpt"}
                  >
                    <span className="font-mono text-[10px] font-bold text-primary">
                      [^{c.citation_index}]
                    </span>
                    <span className="font-medium text-foreground">
                      {c.ticker || "SEC"}
                    </span>
                    <span className="text-muted-foreground/80">
                      FY{c.fiscal_year || "10-K"}
                    </span>
                    {c.is_table && (
                      <FileSpreadsheet className="size-3 text-amber-500" />
                    )}
                    <ExternalLink className="size-2.5 opacity-60 ml-0.5" />
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Assistant Message Actions & Footer Timestamp (Below the answer box) */}
        {!isUser && message.content && (
          <div className="mt-1.5 flex items-center gap-1 text-[11px] text-muted-foreground select-none">
            {/* Version Branching Navigation */}
            {versions && versions.length > 1 && (
              <div className="flex items-center gap-0.5 font-mono text-[10.5px] text-muted-foreground mr-1.5">
                <button
                  type="button"
                  onClick={() => onSelectVersion?.(currentVersionIndex - 1)}
                  disabled={currentVersionIndex <= 0 || isStreaming}
                  className="flex size-5 items-center justify-center rounded hover:bg-muted text-muted-foreground hover:text-foreground disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer transition-colors"
                  title="Previous version"
                >
                  <ChevronLeft className="size-3" />
                </button>
                <span className="px-1 text-[10px] tabular-nums text-muted-foreground/80 font-medium">
                  {currentVersionIndex + 1} / {versions.length}
                </span>
                <button
                  type="button"
                  onClick={() => onSelectVersion?.(currentVersionIndex + 1)}
                  disabled={currentVersionIndex >= versions.length - 1 || isStreaming}
                  className="flex size-5 items-center justify-center rounded hover:bg-muted text-muted-foreground hover:text-foreground disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer transition-colors"
                  title="Next version"
                >
                  <ChevronRight className="size-3" />
                </button>
              </div>
            )}

            {/* Copy Button (Icon only) */}
            <button
              type="button"
              onClick={() => void handleCopy()}
              className="flex size-6 items-center justify-center rounded-md text-muted-foreground hover:bg-muted/70 hover:text-foreground cursor-pointer transition-colors"
              title={copied ? "Copied!" : "Copy message"}
            >
              {copied ? (
                <Check className="size-3.5 text-emerald-500" />
              ) : (
                <Copy className="size-3.5" />
              )}
            </button>

            {/* Regenerate Button (Icon only) */}
            {onRegenerate && (
              <button
                type="button"
                onClick={onRegenerate}
                disabled={isStreaming}
                className="flex size-6 items-center justify-center rounded-md text-muted-foreground hover:bg-muted/70 hover:text-foreground disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer transition-colors"
                title="Regenerate response"
              >
                <RotateCw
                  className={cn("size-3.5", isStreamingLast && "animate-spin")}
                />
              </button>
            )}

            {/* Timestamp */}
            {timeDisplay && (
              <span
                className="ml-1 font-mono text-[9.5px] text-muted-foreground/60 cursor-default"
                title={fullDateTimeDisplay}
              >
                · {timeDisplay}
              </span>
            )}
          </div>
        )}
      </div>

      {/* User Avatar */}
      {isUser && (
        <div className="flex size-7 shrink-0 items-center justify-center rounded-lg border border-border/80 bg-muted text-muted-foreground shadow-xs mt-0.5">
          <User className="size-3.5" />
        </div>
      )}
    </div>
  )
}

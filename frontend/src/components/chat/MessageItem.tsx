import { useEffect, useMemo, useRef, useState } from "react"
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
    if (raw === "gemini-3-flash" || raw === "gemini-3-flash-preview") return "Gemini 3 Flash"
    if (raw === "gemini-2.5-flash") return "Gemini 2.5 Flash"
    if (raw === "gemini-2.0-flash" || raw === "gemini-3.8-flash") return "Gemini 2.0 Flash"
    if (raw === "gemini-2.0-flash-lite" || raw === "gemini-flash-lite-latest") return "Gemini 2.0 Flash Lite"
    if (raw === "gemini-3.1-flash-lite" || raw === "gemini-3.1-flash-lite-preview") return "Gemini 3.1 Flash Lite"
    if (raw === "gemini-3.5-flash-lite") return "Gemini 3.5 Flash Lite"
    return raw || "Gemini 2.5 Flash"
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

  // Uniform 1% -> 100% progressive ticker with stage-anchored pacing and asymptotic velocity decay
  const [smoothPercent, setSmoothPercent] = useState<number>(1)
  const [hasFinished100, setHasFinished100] = useState<boolean>(false)
  const animFrameRef = useRef<number | null>(null)
  const lastTickTimeRef = useRef<number>(Date.now())

  const shouldShowProgress = !isUser && isStreamingLast && (!message.content || !hasFinished100)

  useEffect(() => {
    if (!isStreamingLast || isUser) {
      setSmoothPercent(1)
      setHasFinished100(false)
      return
    }

    // Determine target percentage based on real backend pipeline stage
    let target = 24
    const stage = pipelineStatus?.stage

    if (message.content && message.content.length > 0) {
      target = 100
    } else if (stage === "searching") {
      target = 24
    } else if (stage === "fusion") {
      target = 38
    } else if (stage === "reasoning") {
      target = 88
    } else if (stage === "validating") {
      target = 96
    } else if (stage === "complete") {
      target = 100
    }

    let isRunning = true

    function tick() {
      if (!isRunning) return

      const now = Date.now()
      const dt = now - lastTickTimeRef.current

      // Calculate dynamic tick interval based on current progress & stage
      // Paces Step 3 (LLM generation) across ~5-6s so it never freezes
      let requiredInterval = 30
      if (target === 100) {
        requiredInterval = 20 // Rapid sweep when answer is ready
      } else if (stage === "reasoning") {
        if (smoothPercent < 50) requiredInterval = 35 // Quick ramp to 50%
        else if (smoothPercent < 68) requiredInterval = 75 // Steady ramp to 68%
        else if (smoothPercent < 82) requiredInterval = 160 // Easing ramp to 82%
        else requiredInterval = 380 // Asymptotic creep to 88% while LLM thinks
      }

      if (dt >= requiredInterval) {
        lastTickTimeRef.current = now

        setSmoothPercent((prev) => {
          if (prev >= 100) {
            return 100
          }

          if (target === 100) {
            // Rapid finish sweep to 100% when answer is ready
            return Math.min(100, prev + 4)
          }

          if (prev < target) {
            return prev + 1
          }

          // In Step 3 (LLM reasoning), if backend takes >6s, gently creep (up to 92%) so ticker never looks frozen
          if (stage === "reasoning" && prev < 92 && Math.random() < 0.2) {
            return prev + 1
          }

          return prev
        })
      }

      animFrameRef.current = requestAnimationFrame(tick)
    }

    animFrameRef.current = requestAnimationFrame(tick)

    return () => {
      isRunning = false
      if (animFrameRef.current) {
        cancelAnimationFrame(animFrameRef.current)
      }
    }
  }, [isStreamingLast, isUser, pipelineStatus?.stage, message.content, smoothPercent])

  // Hold at 100% for 250ms celebration before seamlessly revealing answer
  useEffect(() => {
    if (smoothPercent >= 100 && message.content && message.content.length > 0) {
      const timer = setTimeout(() => {
        setHasFinished100(true)
      }, 250)
      return () => clearTimeout(timer)
    }
  }, [smoothPercent, message.content])

  // Compute stage-anchored label and 10-bar fill
  // CRITICAL: Step labels strictly follow backend stage truth, eliminating state drift
  const progressInfo = useMemo(() => {
    const percent = Math.min(100, Math.max(1, Math.round(smoothPercent)))
    const filledBars = Math.min(10, Math.max(1, Math.ceil(percent / 10)))

    const stage = pipelineStatus?.stage
    let label = "Step 1 of 4: Hybrid Retrieval"

    if (stage === "searching") {
      label = "Step 1 of 4: Hybrid Retrieval"
    } else if (stage === "fusion") {
      label = "Step 2 of 4: Rank Fusion"
    } else if (stage === "reasoning") {
      // While in Step 3, ALWAYS display Step 3: Agent Synthesis regardless of %
      label = "Step 3 of 4: Agent Synthesis"
    } else if (stage === "validating") {
      label = "Step 4 of 4: Grounding Verification"
    } else if (stage === "complete" || (message.content && percent >= 100)) {
      label = "Step 4 of 4: Verification Complete"
    } else {
      // Pure fallback if pipelineStatus has not yet arrived
      if (percent < 25) label = "Step 1 of 4: Hybrid Retrieval"
      else if (percent < 40) label = "Step 2 of 4: Rank Fusion"
      else if (percent < 90) label = "Step 3 of 4: Agent Synthesis"
      else label = "Step 4 of 4: Grounding Verification"
    }

    return { percent, label, filledBars }
  }, [smoothPercent, pipelineStatus?.stage, message.content])

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

  // Render text blocks containing paragraphs, headings, lists, and formatted callouts
  function renderTextBlock(textBlock: string, blockKey: string | number) {
    const lines = textBlock.split("\n")
    const elements: React.ReactNode[] = []
    let listBuffer: string[] = []
    let calloutBuffer: string[] = []

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

    function flushCallout() {
      if (calloutBuffer.length > 0) {
        const fullBlockText = calloutBuffer.join(" ")
        const isWarning =
          fullBlockText.includes("[!WARNING]") ||
          fullBlockText.includes("High Demand Notice") ||
          fullBlockText.includes("Alert") ||
          fullBlockText.includes("Warning")

        // Clean out ">", "[!WARNING]", "[!NOTE]"
        const cleanLines = calloutBuffer
          .map((line) =>
            line
              .replace(/^>\s?/, "")
              .replace(/\[!(WARNING|NOTE|TIP|IMPORTANT|CAUTION)\]/g, "")
              .trim()
          )
          .filter((line) => line.length > 0)

        let titleLine = "System Notice"
        let bodyLines = cleanLines

        if (cleanLines.length > 0) {
          const first = cleanLines[0]
          if (first.startsWith("**") && first.endsWith("**")) {
            titleLine = first.slice(2, -2).trim()
            bodyLines = cleanLines.slice(1)
          } else if (first.includes("Notice") || first.includes("Alert") || first.includes("Warning")) {
            titleLine = first.replace(/\*\*/g, "").trim()
            bodyLines = cleanLines.slice(1)
          } else if (isWarning) {
            titleLine = "Notice"
          }
        }

        elements.push(
          <div
            key={`callout-${elements.length}`}
            className={cn(
              "my-3 flex items-start gap-3 rounded-2xl border p-3.5 text-xs shadow-xs transition-all backdrop-blur-sm",
              isWarning
                ? "border-amber-500/35 bg-amber-500/10 text-amber-900 dark:border-amber-500/30 dark:bg-amber-950/30 dark:text-amber-200"
                : "border-primary/30 bg-primary/10 text-foreground"
            )}
          >
            {isWarning ? (
              <AlertTriangle className="size-4.5 shrink-0 text-amber-600 dark:text-amber-400 mt-0.5" />
            ) : (
              <ShieldCheck className="size-4.5 shrink-0 text-primary mt-0.5" />
            )}
            <div className="space-y-1 flex-1">
              <p className="font-bold text-foreground text-[12.5px] tracking-tight">
                {titleLine}
              </p>
              {bodyLines.map((bLine, bIdx) => (
                <p key={bIdx} className="text-[11.5px] leading-relaxed text-muted-foreground">
                  {renderInlineSpans(bLine)}
                </p>
              ))}
            </div>
          </div>
        )
        calloutBuffer = []
      }
    }

    for (let lIdx = 0; lIdx < lines.length; lIdx++) {
      const rawLine = lines[lIdx]
      const trimmed = rawLine.trim()

      if (!trimmed) {
        flushList()
        flushCallout()
        continue
      }

      // Blockquotes and Alerts (> [!WARNING] or > **Title**)
      if (trimmed.startsWith(">")) {
        flushList()
        calloutBuffer.push(trimmed)
        continue
      } else {
        flushCallout()
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
    flushCallout()
    return (
      <div key={blockKey} className="space-y-0.5">
        {elements}
      </div>
    )
  }

  // Format content with interactive GFM tables, HoverCards, and citation chips
  function renderFormattedContent(text: string) {
    const hasGroundingWarning = text.includes("Grounding Verification Alert")

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
          {/* While generating: Uniform 1% -> 100% Segmented 10-Bar Indicator */}
          {shouldShowProgress ? (
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

import { useState } from "react"
import {
  AlertTriangle,
  Bot,
  Check,
  Clock,
  Copy,
  ExternalLink,
  FileSpreadsheet,
  ShieldCheck,
  Sparkles,
  User,
} from "lucide-react"
import type { Citation, Message } from "@/lib/api"
import { formatFullDateTime, formatMessageTime } from "@/lib/dateUtils"
import { cn } from "@/lib/utils"

interface MessageItemProps {
  message: Message
  isStreamingLast?: boolean
  onSelectCitation?: (citation: Citation) => void
}

export function MessageItem({
  message,
  isStreamingLast,
  onSelectCitation,
}: MessageItemProps) {
  const isUser = message.role === "user"
  const [copied, setCopied] = useState(false)

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

  // Map citation_index to Citation object for quick in-text lookup
  const citationMap = new Map<number, Citation>()
  if (message.citations) {
    for (const c of message.citations) {
      citationMap.set(c.citation_index, c)
    }
  }

  // Parse text into regular text and clickable citation tokens
  function renderFormattedContent(text: string) {
    const hasGroundingWarning =
      text.includes("[!WARNING]") || text.includes("Grounding Verification Alert")

    const parts = text.split(/(\[\^\d+\])/g)

    return (
      <>
        {parts.map((part, i) => {
          const match = part.match(/\[\^(\d+)\]/)
          if (match) {
            const index = parseInt(match[1], 10)
            const cit = citationMap.get(index)

            return (
              <button
                key={i}
                type="button"
                onClick={() => {
                  if (cit && onSelectCitation) {
                    onSelectCitation(cit)
                  }
                }}
                className={cn(
                  "inline-flex items-center gap-0.5 rounded px-1.5 py-0.5 mx-0.5 text-[11px] font-mono font-semibold transition-all align-baseline cursor-pointer",
                  cit
                    ? "bg-primary/10 text-primary hover:bg-primary/20 hover:ring-1 hover:ring-primary/40"
                    : "bg-muted text-muted-foreground hover:bg-muted/80"
                )}
                title={
                  cit
                    ? `Click to view source: ${cit.company_name || cit.ticker} ${cit.filing_type || "10-K"} (${cit.section || "Section"})`
                    : `Citation [^${index}]`
                }
              >
                <span>[^{index}]</span>
              </button>
            )
          }

          return <span key={i}>{part}</span>
        })}

        {hasGroundingWarning && (
          <div className="mt-3 flex items-start gap-2 rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-800 dark:text-amber-200">
            <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400 mt-0.5" />
            <div>
              <p className="font-semibold text-amber-900 dark:text-amber-100">
                Grounding Verification Notice
              </p>
              <p className="text-[11px] text-amber-700 dark:text-amber-300">
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
      {/* Assistant Avatar */}
      {!isUser && (
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-border/80 bg-foreground text-background shadow-xs mt-0.5">
          <Bot className="h-3.5 w-3.5" />
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
            "mb-1 flex items-center gap-2 text-[11px] text-muted-foreground px-1",
            isUser ? "flex-row-reverse" : "flex-row"
          )}
        >
          <span className="font-medium text-foreground">
            {isUser ? "You" : "Document Assistant"}
          </span>

          {!isUser && (
            <span className="inline-flex items-center gap-1 rounded bg-muted/80 px-1.5 py-0.2 font-mono text-[9px] text-muted-foreground">
              <Sparkles className="h-2.5 w-2.5 text-primary" />
              Gemini 3 Flash
            </span>
          )}

          {timeDisplay && (
            <span
              className="flex items-center gap-1 font-mono text-[10px] text-muted-foreground/75 cursor-default"
              title={fullDateTimeDisplay}
            >
              <Clock className="h-2.5 w-2.5 opacity-60" />
              {timeDisplay}
            </span>
          )}
        </div>

        {/* Message Bubble */}
        <div
          className={cn(
            "relative w-full rounded-2xl px-4 py-3 text-[13.5px] leading-relaxed tracking-normal shadow-xs",
            isUser
              ? "bg-primary text-primary-foreground"
              : "border border-border/70 bg-card text-foreground"
          )}
        >
          <div className="whitespace-pre-wrap break-words font-normal">
            {renderFormattedContent(message.content)}
            {!isUser && isStreamingLast && (
              <span className="inline-block h-3.5 w-1.5 animate-pulse bg-foreground align-middle ml-1" />
            )}
          </div>

          {/* Verified Sources Pill List (Bottom of assistant answer) */}
          {!isUser && message.citations && message.citations.length > 0 && (
            <div className="mt-3.5 pt-3 border-t border-border/50">
              <div className="flex items-center gap-1.5 text-[11px] font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                <ShieldCheck className="h-3.5 w-3.5 text-primary" />
                <span>Verified Sources ({message.citations.length})</span>
              </div>

              <div className="flex flex-wrap gap-1.5">
                {message.citations.map((c) => (
                  <button
                    key={c.citation_index}
                    type="button"
                    onClick={() => onSelectCitation?.(c)}
                    className="flex items-center gap-1.5 rounded-lg border border-border/70 bg-muted/40 px-2.5 py-1 text-left text-[11px] text-muted-foreground transition-all hover:border-primary/40 hover:bg-muted hover:text-foreground cursor-pointer"
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
                      <FileSpreadsheet className="h-3 w-3 text-amber-500" />
                    )}
                    <ExternalLink className="h-2.5 w-2.5 opacity-60 ml-0.5" />
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Assistant Message Actions & Footer Timestamp */}
          {!isUser && message.content && (
            <div className="mt-2.5 flex items-center justify-between border-t border-border/40 pt-2 text-[11px] text-muted-foreground">
              <div className="flex items-center gap-2">
                <span className="font-mono text-[10px] text-muted-foreground/70">
                  {message.citations && message.citations.length > 0
                    ? "Grounded SEC 10-K Research"
                    : "Grounded Response"}
                </span>
                {timeDisplay && (
                  <span
                    className="hidden sm:inline font-mono text-[9.5px] text-muted-foreground/60"
                    title={fullDateTimeDisplay}
                  >
                    · {timeDisplay}
                  </span>
                )}
              </div>

              <button
                type="button"
                onClick={() => void handleCopy()}
                className="flex items-center gap-1 rounded px-1.5 py-0.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground cursor-pointer"
                title="Copy message to clipboard"
              >
                {copied ? (
                  <>
                    <Check className="h-3 w-3 text-emerald-600 dark:text-emerald-400" />
                    <span className="text-[10px] text-emerald-600 dark:text-emerald-400">Copied</span>
                  </>
                ) : (
                  <>
                    <Copy className="h-3 w-3" />
                    <span className="text-[10px]">Copy</span>
                  </>
                )}
              </button>
            </div>
          )}
        </div>
      </div>

      {/* User Avatar */}
      {isUser && (
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-border/80 bg-muted text-muted-foreground shadow-xs mt-0.5">
          <User className="h-3.5 w-3.5" />
        </div>
      )}
    </div>
  )
}

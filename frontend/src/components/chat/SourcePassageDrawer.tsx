import { useEffect, useState } from "react"
import {
  Building2,
  Calendar,
  Check,
  Copy,
  FileSpreadsheet,
  Hash,
  Layers,
  X,
} from "lucide-react"
import type { Citation } from "@/lib/api"

interface SourcePassageDrawerProps {
  citation: Citation | null
  onClose: () => void
}

export function SourcePassageDrawer({ citation, onClose }: SourcePassageDrawerProps) {
  const [copied, setCopied] = useState(false)
  const [showFullContext, setShowFullContext] = useState(false)

  // Close on Escape key
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        onClose()
      }
    }
    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [onClose])

  if (!citation) return null

  const quoteText = citation.snippet || citation.excerpt || ""
  const fullText = citation.full_context_text || quoteText

  async function handleCopyQuote() {
    try {
      await navigator.clipboard.writeText(quoteText)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Ignore
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/40 backdrop-blur-xs transition-opacity animate-in fade-in">
      {/* Backdrop click to dismiss */}
      <div className="fixed inset-0" onClick={onClose} />

      {/* Slide-over Drawer */}
      <div className="relative z-10 flex h-full w-full max-w-xl flex-col border-l border-border bg-card shadow-2xl transition-transform duration-300 animate-in slide-in-from-right sm:max-w-xl">
        {/* Drawer Header */}
        <div className="flex shrink-0 items-center justify-between border-b border-border/80 px-6 py-4">
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10 text-xs font-bold font-mono text-primary">
              [^{citation.citation_index}]
            </span>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-semibold text-foreground">
                  {citation.company_name || citation.ticker || "SEC Filing"}
                </h3>
                {citation.ticker && (
                  <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] font-medium text-foreground">
                    {citation.ticker}
                  </span>
                )}
                {citation.is_table && (
                  <span className="inline-flex items-center gap-1 rounded bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-medium text-amber-600 dark:text-amber-400">
                    <FileSpreadsheet className="h-3 w-3" />
                    Table
                  </span>
                )}
              </div>
              <p className="text-[11px] text-muted-foreground">
                {citation.filing_type || "10-K"} · FY{citation.fiscal_year || "Latest"} · {citation.section || "Report Disclosures"}
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            title="Close source passage drawer"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Drawer Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Metadata pill list */}
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="flex items-center gap-2 rounded-lg border border-border/60 bg-muted/40 p-2.5">
              <Building2 className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
              <div className="truncate">
                <span className="block text-[10px] text-muted-foreground">Company</span>
                <span className="font-medium text-foreground truncate">
                  {citation.company_name || citation.ticker || "—"}
                </span>
              </div>
            </div>

            <div className="flex items-center gap-2 rounded-lg border border-border/60 bg-muted/40 p-2.5">
              <Calendar className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
              <div>
                <span className="block text-[10px] text-muted-foreground">Filing Date</span>
                <span className="font-medium text-foreground">
                  {citation.filing_date || "Annual 10-K"}
                </span>
              </div>
            </div>

            <div className="col-span-2 flex items-center gap-2 rounded-lg border border-border/60 bg-muted/40 p-2.5">
              <Layers className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
              <div className="truncate">
                <span className="block text-[10px] text-muted-foreground">Section / Heading</span>
                <span className="font-medium text-foreground truncate">
                  {citation.section || "Item 7 — Management's Discussion & Analysis"}
                </span>
              </div>
            </div>
          </div>

          {/* Quoted Snippet Box */}
          {quoteText && (
            <div>
              <div className="flex items-center justify-between pb-1.5">
                <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                  Supporting Quote
                </span>
                <button
                  type="button"
                  onClick={() => void handleCopyQuote()}
                  className="flex items-center gap-1 text-[11px] font-medium text-primary hover:underline"
                >
                  {copied ? (
                    <>
                      <Check className="h-3 w-3 text-emerald-500" />
                      <span>Copied</span>
                    </>
                  ) : (
                    <>
                      <Copy className="h-3 w-3" />
                      <span>Copy quote</span>
                    </>
                  )}
                </button>
              </div>

              <blockquote className="rounded-xl border-l-3 border-primary bg-primary/5 p-4 text-[13px] leading-relaxed text-foreground italic shadow-2xs">
                "{quoteText}"
              </blockquote>
            </div>
          )}

          {/* Context View Toggle */}
          <div>
            <div className="flex items-center justify-between pb-2">
              <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                Surrounding 10-K Text
              </span>
              <button
                type="button"
                onClick={() => setShowFullContext(!showFullContext)}
                className="text-[11px] font-medium text-primary hover:underline"
              >
                {showFullContext ? "Show excerpt only" : "Expand full passage context"}
              </button>
            </div>

            <div className="rounded-xl border border-border/80 bg-muted/30 p-4 font-mono text-xs leading-relaxed text-foreground whitespace-pre-wrap break-words max-h-96 overflow-y-auto">
              {showFullContext ? fullText : quoteText || fullText}
            </div>
          </div>

          {/* Provenance Audit Footer */}
          <div className="rounded-lg border border-border/60 bg-card p-3 text-[11px] text-muted-foreground">
            <div className="flex items-center gap-1.5 font-semibold text-foreground">
              <Hash className="h-3.5 w-3.5 text-primary" />
              <span>Provenance Verification</span>
            </div>
            <p className="mt-1 font-mono text-[10px] text-muted-foreground break-all">
              chunk_id: {citation.chunk_id}
            </p>
            <p className="mt-1 text-[10px] text-muted-foreground">
              Retrieved via Supabase hybrid vector & full-text index with neighbor expansion.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

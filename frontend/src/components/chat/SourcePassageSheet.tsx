import React, { useMemo, useState } from "react"
import {
  Building2,
  Calendar,
  Check,
  Coins,
  Copy,
  FileSpreadsheet,
  Hash,
  Layers,
  Sparkles,
} from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import type { Citation } from "@/lib/api"

interface SourcePassageSheetProps {
  citation: Citation | null
  onClose: () => void
}

/**
 * Highlights dollar values, numbers, shares, percentages, and fiscal years in text.
 */
export function highlightFinancialFigures(text: string): React.ReactNode {
  if (!text) return null
  const numRegex =
    /(\$[\d,]+(?:\.\d+)?(?:\s*(?:billion|million|trillion|thousand))?|\b\d+(?:,\d{3})*(?:\.\d+)?%|\b\d+(?:,\d{3})*(?:\.\d+)?\s*(?:billion|million|shares|common shares)\b|\b(?:FY)?20\d{2}\b)/gi

  const parts = text.split(numRegex)
  return parts.map((part, i) => {
    if (numRegex.test(part)) {
      return (
        <mark
          key={i}
          className="rounded bg-primary/20 text-primary font-mono font-bold px-1 py-0.5 mx-0.5 border border-primary/30 inline-block shadow-2xs"
        >
          {part}
        </mark>
      )
    }
    return <span key={i}>{part}</span>
  })
}

export function SourcePassageSheet({ citation, onClose }: SourcePassageSheetProps) {
  const [copied, setCopied] = useState(false)
  const [showFullContext, setShowFullContext] = useState(false)

  const isOpen = citation !== null
  const quoteText = (citation?.snippet || citation?.excerpt || "").trim()
  const fullText = (citation?.full_context_text || quoteText).trim()

  // Extract all distinct financial metrics from the quote or full text
  const keyFigures = useMemo(() => {
    const source = `${quoteText} ${fullText}`
    const matches = source.match(
      /(\$[\d,]+(?:\.\d+)?(?:\s*(?:billion|million|trillion))?|\b\d+(?:,\d{3})*(?:\.\d+)?%|\b\d+(?:,\d{3})*(?:\.\d+)?\s*(?:billion|million|shares)\b)/gi
    )
    if (!matches) return []
    return Array.from(new Set(matches.map((m) => m.trim()))).slice(0, 6)
  }, [quoteText, fullText])

  async function handleCopyQuote() {
    const textToCopy = quoteText || fullText
    if (!textToCopy) return
    try {
      await navigator.clipboard.writeText(textToCopy)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Ignore
    }
  }

  return (
    <Sheet open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <SheetContent side="right" className="sm:max-w-xl flex flex-col p-0">
        {/* Sheet Header */}
        <SheetHeader className="p-5 pb-4 border-b border-border/60">
          <div className="flex items-center gap-2.5">
            <span className="flex size-8 items-center justify-center rounded-lg bg-primary/10 font-mono text-xs font-bold text-primary border border-primary/25">
              [^{citation?.citation_index}]
            </span>
            <div className="truncate">
              <div className="flex items-center gap-2">
                <SheetTitle className="text-sm font-semibold truncate">
                  {citation?.company_name || citation?.ticker || "SEC Filing Passage"}
                </SheetTitle>
                {citation?.ticker && (
                  <Badge variant="ticker">{citation.ticker}</Badge>
                )}
                {citation?.is_table && (
                  <Badge variant="table">
                    <FileSpreadsheet className="mr-1 size-3" />
                    Table
                  </Badge>
                )}
              </div>
              <SheetDescription className="text-[11px] text-muted-foreground mt-0.5 truncate">
                {citation?.filing_type || "10-K"} · FY{citation?.fiscal_year || "Latest"} · {citation?.section || "Filing Disclosures"}
              </SheetDescription>
            </div>
          </div>
        </SheetHeader>

        {/* Scrollable Passage Body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {/* Metadata Cards */}
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div className="flex items-center gap-2 rounded-xl border border-border/70 bg-card p-3 shadow-2xs">
              <Building2 className="size-3.5 text-muted-foreground shrink-0" />
              <div className="truncate">
                <span className="block text-[10px] text-muted-foreground font-mono">Company</span>
                <span className="font-medium text-foreground truncate">
                  {citation?.company_name || citation?.ticker || "—"}
                </span>
              </div>
            </div>

            <div className="flex items-center gap-2 rounded-xl border border-border/70 bg-card p-3 shadow-2xs">
              <Calendar className="size-3.5 text-muted-foreground shrink-0" />
              <div>
                <span className="block text-[10px] text-muted-foreground font-mono">Filing Date</span>
                <span className="font-medium text-foreground">
                  {citation?.filing_date || "Annual Report"}
                </span>
              </div>
            </div>

            <div className="col-span-2 flex items-center gap-2 rounded-xl border border-border/70 bg-card p-3 shadow-2xs">
              <Layers className="size-3.5 text-muted-foreground shrink-0" />
              <div className="truncate">
                <span className="block text-[10px] text-muted-foreground font-mono">Section Hierarchy</span>
                <span className="font-medium text-foreground truncate">
                  {citation?.section || "Item 7 — Management's Discussion & Analysis"}
                </span>
              </div>
            </div>
          </div>

          {/* Key Extracted Figures Chip List */}
          {keyFigures.length > 0 && (
            <div className="rounded-xl border border-primary/30 bg-primary/5 p-3 space-y-2">
              <div className="flex items-center gap-1.5 text-[10.5px] font-mono font-bold text-primary uppercase tracking-wider">
                <Coins className="size-3.5" />
                <span>Verified Quantitative Figures in Source</span>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {keyFigures.map((fig, idx) => (
                  <span
                    key={idx}
                    className="inline-flex items-center gap-1 rounded-md bg-card border border-primary/40 px-2 py-0.5 font-mono text-[11px] font-bold text-primary shadow-2xs"
                  >
                    <Sparkles className="size-2.5 opacity-70" />
                    {fig}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Supporting Quote Box */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider font-mono">
                Supporting Quote & Evidence
              </span>
              <Button
                variant="ghost"
                size="xs"
                onClick={() => void handleCopyQuote()}
                className="h-6 gap-1 text-[11px] text-primary"
              >
                {copied ? (
                  <>
                    <Check className="size-3 text-emerald-500" />
                    <span>Copied</span>
                  </>
                ) : (
                  <>
                    <Copy className="size-3" />
                    <span>Copy quote</span>
                  </>
                )}
              </Button>
            </div>

            <blockquote className="rounded-xl border-l-3 border-primary bg-primary/5 p-4 text-[13px] leading-relaxed text-foreground shadow-2xs break-words">
              “{highlightFinancialFigures(quoteText || fullText || "Referenced SEC 10-K disclosure context.")}”
            </blockquote>
          </div>

          {/* Surrounding Context Box */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider font-mono">
                Surrounding 10-K Context
              </span>
              <Button
                variant="ghost"
                size="xs"
                onClick={() => setShowFullContext(!showFullContext)}
                className="h-6 text-[11px] text-primary"
              >
                {showFullContext ? "Show concise excerpt" : "Expand full ±1 boundary context"}
              </Button>
            </div>

            <div className="rounded-xl border border-border/80 bg-muted/30 p-4 font-mono text-xs leading-relaxed text-foreground whitespace-pre-wrap break-words max-h-96 overflow-y-auto">
              {highlightFinancialFigures(showFullContext ? fullText : quoteText || fullText)}
            </div>
          </div>

          {/* Provenance Audit Footer */}
          <div className="rounded-xl border border-border/70 bg-card p-3.5 text-[11px] text-muted-foreground space-y-1">
            <div className="flex items-center gap-1.5 font-semibold text-foreground font-mono">
              <Hash className="size-3.5 text-primary" />
              <span>Provenance Verification</span>
            </div>
            <p className="font-mono text-[10.5px] text-muted-foreground/80 break-all">
              chunk_id: {citation?.chunk_id}
            </p>
            <p className="text-[10px] text-muted-foreground/70">
              Retrieved from Supabase PostgreSQL via reciprocal rank fusion (k=60) with boundary expansion.
            </p>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  )
}

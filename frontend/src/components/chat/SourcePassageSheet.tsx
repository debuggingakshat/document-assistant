import { useState } from "react"
import {
  Building2,
  Calendar,
  Check,
  Copy,
  FileSpreadsheet,
  Hash,
  Layers,
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

export function SourcePassageSheet({ citation, onClose }: SourcePassageSheetProps) {
  const [copied, setCopied] = useState(false)
  const [showFullContext, setShowFullContext] = useState(false)

  const isOpen = citation !== null
  const quoteText = citation?.snippet || citation?.excerpt || ""
  const fullText = citation?.full_context_text || quoteText

  async function handleCopyQuote() {
    if (!quoteText) return
    try {
      await navigator.clipboard.writeText(quoteText)
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
        <SheetHeader className="p-5 pb-4">
          <div className="flex items-center gap-2">
            <span className="flex size-7 items-center justify-center rounded-lg bg-primary/10 font-mono text-xs font-bold text-primary">
              [^{citation?.citation_index}]
            </span>
            <div>
              <div className="flex items-center gap-2">
                <SheetTitle className="text-sm font-semibold">
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
              <SheetDescription className="text-[11px] text-muted-foreground mt-0.5">
                {citation?.filing_type || "10-K"} · FY{citation?.fiscal_year || "Latest"} · {citation?.section || "Filing Disclosures"}
              </SheetDescription>
            </div>
          </div>
        </SheetHeader>

        {/* Scrollable Passage Body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-5">
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

          {/* Quoted Snippet Box */}
          {quoteText && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider font-mono">
                  Supporting Quote
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

              <blockquote className="rounded-xl border-l-3 border-primary bg-primary/5 p-4 text-[13px] leading-relaxed text-foreground italic shadow-2xs">
                "{quoteText}"
              </blockquote>
            </div>
          )}

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
                {showFullContext ? "Show excerpt only" : "Expand full ±1 boundary chunks"}
              </Button>
            </div>

            <div className="rounded-xl border border-border/80 bg-muted/30 p-4 font-mono text-xs leading-relaxed text-foreground whitespace-pre-wrap break-words max-h-96 overflow-y-auto">
              {showFullContext ? fullText : quoteText || fullText}
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

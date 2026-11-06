import { useEffect, useState } from "react"
import { Link, useParams } from "react-router-dom"
import { ArrowUpRight, Layers, Loader2, Share2, Sparkles } from "lucide-react"
import { getSharedSnapshot, type Citation, type SharedSnapshotResponse } from "@/lib/api"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { MessageItem } from "@/components/chat/MessageItem"
import { SourcePassageSheet } from "@/components/chat/SourcePassageSheet"
import { ThemeToggle } from "@/components/chat/ThemeToggle"

export function SharedThreadPage() {
  const { shareId } = useParams<{ shareId: string }>()
  const [snapshot, setSnapshot] = useState<SharedSnapshotResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null)

  useEffect(() => {
    if (!shareId) return
    let isMounted = true
    setLoading(true)
    setError(null)

    getSharedSnapshot(shareId)
      .then((data) => {
        if (isMounted) setSnapshot(data)
      })
      .catch((err) => {
        if (isMounted) {
          setError(
            err instanceof Error
              ? err.message
              : "Shared research thread not found or link has expired"
          )
        }
      })
      .finally(() => {
        if (isMounted) setLoading(false)
      })

    return () => {
      isMounted = false
    }
  }, [shareId])

  const turns = snapshot?.snapshot_payload?.turns || []
  const isSingleTurn = snapshot?.share_type === "single_turn"

  return (
    <div className="min-h-screen flex flex-col bg-background text-foreground">
      {/* Top Header Bar */}
      <header className="sticky top-0 z-40 flex h-14 shrink-0 items-center justify-between border-b border-border/80 bg-background/95 backdrop-blur-md px-4 sm:px-8 select-none">
        <div className="flex items-center gap-3">
          <Link to="/" className="flex items-center gap-2 hover:opacity-85 transition-opacity">
            <span className="flex size-7 items-center justify-center rounded-lg bg-primary text-primary-foreground font-bold text-sm shadow-xs">
              M
            </span>
            <span className="font-semibold text-sm tracking-tight text-foreground hidden sm:inline">
              Meridian Document Assistant
            </span>
          </Link>

          <Badge variant="secondary" className="text-[11px] font-mono gap-1.5 py-0.5">
            <Share2 className="size-3 text-primary" />
            <span>{isSingleTurn ? "Shared Response" : "Shared Research Thread"}</span>
          </Badge>
        </div>

        <div className="flex items-center gap-3">
          <ThemeToggle />

          <Button asChild size="sm" className="h-8 gap-1.5 px-3 text-xs font-medium cursor-pointer shadow-xs">
            <Link to="/">
              <span>New Research</span>
              <ArrowUpRight className="size-3.5" />
            </Link>
          </Button>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 w-full max-w-3xl mx-auto px-4 py-8 sm:px-6">
        {loading ? (
          <div className="flex h-64 flex-col items-center justify-center gap-3 text-xs text-muted-foreground">
            <Loader2 className="size-6 animate-spin text-primary" />
            <span>Loading verified SEC research snapshot...</span>
          </div>
        ) : error || !snapshot ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <div className="size-12 rounded-2xl bg-destructive/10 text-destructive flex items-center justify-center mb-3">
              <Layers className="size-6" />
            </div>
            <h1 className="text-base font-semibold text-foreground">Snapshot Not Found</h1>
            <p className="mt-1 text-xs text-muted-foreground max-w-sm">
              {error || "This shared research thread does not exist or may have been unshared."}
            </p>
            <Button asChild variant="outline" size="sm" className="mt-4 text-xs">
              <Link to="/">Return to Document Assistant</Link>
            </Button>
          </div>
        ) : (
          <div className="flex flex-col gap-6">
            {/* Rendered Turns */}
            <div className="space-y-6">
              {turns.map((turn, idx) => (
                <div key={idx} className="space-y-4">
                  {turn.user_message && (
                    <MessageItem message={turn.user_message} readOnly />
                  )}
                  {turn.assistant_message && (
                    <MessageItem
                      message={turn.assistant_message}
                      readOnly
                      onSelectCitation={(cit) => setSelectedCitation(cit)}
                    />
                  )}
                </div>
              ))}
            </div>

            {/* Footnote Compliance Banner */}
            <div className="mt-8 rounded-xl border border-border/60 bg-muted/30 p-4 text-center text-xs text-muted-foreground">
              <div className="flex items-center justify-center gap-1.5 font-medium text-foreground mb-1">
                <Sparkles className="size-3.5 text-primary" />
                <span>Deterministic Grounding Guarantee</span>
              </div>
              <p className="text-[11px] leading-relaxed max-w-lg mx-auto">
                All citations are verified via a 4-gate fail-closed pipeline. Click any citation chip (<span className="font-mono text-primary font-semibold">[^1]</span>) above to inspect raw SEC filing passages and verified cell numbers.
              </p>
            </div>
          </div>
        )}
      </main>

      {/* Interactive Citation Inspection Slide-over Sheet */}
      <SourcePassageSheet
        citation={selectedCitation}
        onClose={() => setSelectedCitation(null)}
      />
    </div>
  )
}


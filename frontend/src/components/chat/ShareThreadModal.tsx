import { useState } from "react"
import { Check, Copy, Link as LinkIcon, Loader2, RotateCw, Share } from "lucide-react"
import { createShare } from "@/lib/api"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"

interface ShareThreadModalProps {
  threadId: string
  threadTitle?: string
  shareType?: "single_turn" | "full_thread"
  messageId?: string
  trigger?: React.ReactNode
}

export function ShareThreadModal({
  threadId,
  threadTitle,
  shareType = "full_thread",
  messageId,
  trigger,
}: ShareThreadModalProps) {
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [shareUrl, setShareUrl] = useState("")
  const [copied, setCopied] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const isSingleTurn = shareType === "single_turn"

  async function fetchShareUrl() {
    setLoading(true)
    setError(null)
    try {
      const res = await createShare(threadId, {
        share_type: shareType,
        message_id: messageId,
      })
      const fullUrl = `${window.location.origin}${res.share_url}`
      setShareUrl(fullUrl)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate share link")
    } finally {
      setLoading(false)
    }
  }

  function handleOpenChange(newOpen: boolean) {
    setOpen(newOpen)
    if (newOpen && !shareUrl) {
      void fetchShareUrl()
    }
  }

  async function handleCopy() {
    if (!shareUrl) return
    try {
      await navigator.clipboard.writeText(shareUrl)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Fallback
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        {trigger ? (
          trigger
        ) : (
          <Button
            variant="outline"
            size="sm"
            className="h-7 gap-1.5 px-2.5 text-xs text-muted-foreground hover:text-foreground cursor-pointer transition-colors"
            title="Share research thread"
          >
            <Share className="size-3.5" />
            <span className="font-medium">Share</span>
          </Button>
        )}
      </DialogTrigger>

      <DialogContent className="sm:max-w-md rounded-2xl border border-border bg-card p-6 shadow-2xl">
        <DialogHeader className="gap-1.5 text-left">
          <DialogTitle className="flex items-center gap-2 text-base font-semibold text-foreground">
            <Share className="size-4 text-primary" />
            {isSingleTurn ? "Share Research Response" : "Share Research Thread"}
          </DialogTitle>
          <DialogDescription className="text-xs text-muted-foreground leading-relaxed">
            {isSingleTurn
              ? "Anyone with this link can view this specific SEC research response and audit its verified sources."
              : "Anyone with this link can view this research conversation and audit citations without an account."}
          </DialogDescription>
        </DialogHeader>

        {threadTitle && (
          <div className="mt-2 rounded-xl bg-muted/50 p-2.5 text-xs text-foreground/80 font-medium truncate">
            {threadTitle}
          </div>
        )}

        <div className="mt-4 flex flex-col gap-3">
          {loading ? (
            <div className="flex h-11 items-center justify-center gap-2 rounded-xl border border-dashed border-border text-xs text-muted-foreground">
              <Loader2 className="size-4 animate-spin text-primary" />
              <span>Generating immutable research snapshot...</span>
            </div>
          ) : error ? (
            <div className="flex flex-col gap-2 rounded-xl border border-destructive/20 bg-destructive/10 p-3 text-xs text-destructive">
              <div className="font-medium">{error}</div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => void fetchShareUrl()}
                className="w-fit h-7 text-xs gap-1.5 self-end border-destructive/30 text-destructive hover:bg-destructive/15 cursor-pointer"
              >
                <RotateCw className="size-3" />
                <span>Try Again</span>
              </Button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <div className="relative flex-1">
                <input
                  type="text"
                  readOnly
                  value={shareUrl}
                  onClick={(e) => (e.target as HTMLInputElement).select()}
                  className="w-full rounded-xl border border-input bg-background/80 px-3 py-2 text-xs font-mono text-foreground focus:outline-none focus:ring-1 focus:ring-primary select-all"
                />
              </div>
              <Button
                type="button"
                onClick={handleCopy}
                className="h-8.5 gap-1.5 rounded-xl px-3.5 text-xs font-medium cursor-pointer shrink-0"
              >
                {copied ? (
                  <>
                    <Check className="size-3.5 text-emerald-400" />
                    <span>Copied!</span>
                  </>
                ) : (
                  <>
                    <Copy className="size-3.5" />
                    <span>Copy Link</span>
                  </>
                )}
              </Button>
            </div>
          )}

          <div className="flex items-center gap-2 text-[11px] text-muted-foreground/70">
            <LinkIcon className="size-3 shrink-0" />
            <span>Public snapshot • Verified citations & tables included</span>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

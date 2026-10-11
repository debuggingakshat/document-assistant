import { useState, type FormEvent, type KeyboardEvent } from "react"
import { CornerDownLeft, Sparkles } from "lucide-react"
import { Button } from "@/components/ui/button"

interface MessageInputProps {
  onSend: (message: string) => void
  disabled?: boolean
}

export function MessageInput({ onSend, disabled }: MessageInputProps) {
  const [input, setInput] = useState("")

  function handleSubmit(e?: FormEvent) {
    if (e) e.preventDefault()
    if (!input.trim() || disabled) return
    onSend(input)
    setInput("")
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  return (
    <div className="w-full bg-linear-to-t from-background via-background/95 to-transparent px-4 pb-4 pt-2">
      <div className="mx-auto max-w-3xl">
        <form
          onSubmit={handleSubmit}
          className="relative rounded-2xl border border-border/80 bg-card p-2 shadow-sm transition-all focus-within:border-foreground/30 focus-within:shadow-md"
        >
          <textarea
            rows={1}
            placeholder="Ask a question about SEC filings (10-K, 10-Q, disclosures)..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            className="max-h-36 min-h-[44px] w-full resize-none bg-transparent px-3 py-2 text-sm leading-relaxed outline-none placeholder:text-muted-foreground/60 disabled:opacity-50"
          />

          <div className="flex items-center justify-between border-t border-border/40 px-2 pt-2 text-[11px] text-muted-foreground">
            <div className="flex items-center gap-1.5 text-muted-foreground/70">
              <Sparkles className="h-3 w-3 text-primary" />
              <span>Grounded with reciprocal rank fusion</span>
            </div>

            <div className="flex items-center gap-2">
              <span className="hidden text-[10px] text-muted-foreground/60 sm:inline">
                Return to send
              </span>
              <Button
                type="submit"
                size="sm"
                disabled={!input.trim() || disabled}
                className="h-7 gap-1 rounded-lg px-2.5 text-xs transition-transform active:scale-95"
              >
                <span>Send</span>
                <CornerDownLeft className="h-3 w-3 opacity-70" />
              </Button>
            </div>
          </div>
        </form>

        <p className="mt-2 text-center text-[10.5px] text-muted-foreground/60">
          Document Assistant generates answers from SEC filings. Always verify key figures against original 10-K and 10-Q disclosures.
        </p>
      </div>
    </div>
  )
}

import { useState } from "react"
import { Bot, Check, Copy, User } from "lucide-react"
import type { Message } from "@/lib/api"
import { cn } from "@/lib/utils"

interface MessageItemProps {
  message: Message
  isStreamingLast?: boolean
}

export function MessageItem({ message, isStreamingLast }: MessageItemProps) {
  const isUser = message.role === "user"
  const [copied, setCopied] = useState(false)

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(message.content)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Clipboard failed or denied
    }
  }

  return (
    <div
      className={cn(
        "group relative flex w-full gap-3 py-4 transition-colors",
        isUser ? "justify-end" : "justify-start"
      )}
    >
      {!isUser && (
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-border/80 bg-foreground text-background shadow-xs">
          <Bot className="h-3.5 w-3.5" />
        </div>
      )}

      <div
        className={cn(
          "relative max-w-[85%] rounded-2xl px-4 py-3 text-[13.5px] leading-relaxed tracking-normal",
          isUser
            ? "bg-primary text-primary-foreground shadow-xs"
            : "border border-border/70 bg-card text-foreground shadow-xs"
        )}
      >
        <div className="whitespace-pre-wrap break-words font-normal">
          {message.content}
          {!isUser && isStreamingLast && (
            <span className="inline-block h-3.5 w-1.5 animate-pulse bg-foreground align-middle ml-1" />
          )}
        </div>

        {/* Assistant Message Actions */}
        {!isUser && message.content && (
          <div className="mt-2.5 flex items-center justify-between border-t border-border/40 pt-2 text-[11px] text-muted-foreground">
            <span className="font-mono text-[10px] text-muted-foreground/70">
              Grounded Response
            </span>
            <button
              type="button"
              onClick={() => void handleCopy()}
              className="flex items-center gap-1 rounded px-1.5 py-0.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              title="Copy message"
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

      {isUser && (
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-border/80 bg-muted text-muted-foreground shadow-xs">
          <User className="h-3.5 w-3.5" />
        </div>
      )}
    </div>
  )
}

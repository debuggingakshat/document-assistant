import { Brain, CheckCircle2, Search, ShieldCheck, Sparkles } from "lucide-react"
import type { PipelineStatus } from "@/lib/api"
import { cn } from "@/lib/utils"

interface PipelineStatusIndicatorProps {
  status: PipelineStatus | null
}

const STAGES = [
  { id: "searching", label: "Retrieval", icon: Search },
  { id: "reasoning", label: "Reasoning", icon: Brain },
  { id: "validating", label: "Grounding", icon: ShieldCheck },
]

export function PipelineStatusIndicator({ status }: PipelineStatusIndicatorProps) {
  if (!status) return null

  const stage = status.stage.toLowerCase()

  const currentIdx = STAGES.findIndex((s) => s.id === stage)
  const activeIdx = currentIdx >= 0 ? currentIdx : stage === "complete" ? 3 : 0

  return (
    <div className="my-3 overflow-hidden rounded-xl border border-primary/20 bg-card/80 p-3.5 shadow-xs backdrop-blur-xs transition-all animate-in fade-in slide-in-from-bottom-2">
      {/* Header bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="relative flex h-6 w-6 items-center justify-center rounded-lg bg-primary/10 text-primary">
            {stage === "searching" && <Search className="h-3.5 w-3.5 animate-pulse" />}
            {stage === "reasoning" && <Sparkles className="h-3.5 w-3.5 animate-spin" />}
            {stage === "validating" && <ShieldCheck className="h-3.5 w-3.5 animate-pulse" />}
            {stage === "complete" && <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />}
          </div>
          <div>
            <p className="text-xs font-semibold tracking-tight text-foreground">
              {stage === "searching" && "Searching 10-K Filings"}
              {stage === "reasoning" && "Synthesizing Disclosures"}
              {stage === "validating" && "Verifying Grounding Gates"}
              {stage === "complete" && "Grounding Verified"}
            </p>
            <p className="text-[11px] text-muted-foreground leading-tight">{status.message}</p>
          </div>
        </div>

        <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary">
          <span className="h-1.5 w-1.5 animate-ping rounded-full bg-primary" />
          Live Pipeline
        </span>
      </div>

      {/* Stepper bar */}
      <div className="mt-3 grid grid-cols-3 gap-1.5 border-t border-border/50 pt-2.5">
        {STAGES.map((s, idx) => {
          const Icon = s.icon
          const isDone = activeIdx > idx
          const isCurrent = activeIdx === idx

          return (
            <div
              key={s.id}
              className={cn(
                "flex items-center gap-1.5 rounded-lg px-2 py-1 text-[11px] font-medium transition-colors",
                isDone && "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
                isCurrent && "bg-primary/10 text-primary ring-1 ring-primary/30",
                !isDone && !isCurrent && "text-muted-foreground/50"
              )}
            >
              {isDone ? (
                <CheckCircle2 className="h-3 w-3 shrink-0 text-emerald-500" />
              ) : (
                <Icon
                  className={cn(
                    "h-3 w-3 shrink-0",
                    isCurrent && "animate-pulse text-primary"
                  )}
                />
              )}
              <span className="truncate">{s.label}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

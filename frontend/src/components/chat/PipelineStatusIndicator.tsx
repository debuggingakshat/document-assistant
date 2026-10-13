import { useState } from "react"
import {
  Brain,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Cpu,
  Layers,
  Search,
  ShieldCheck,
  Sparkles,
  Terminal,
} from "lucide-react"
import type { PipelineStatus } from "@/lib/api"
import { cn } from "@/lib/utils"

interface PipelineStatusIndicatorProps {
  status: PipelineStatus | null
}

const STAGES = [
  {
    id: "searching",
    label: "Hybrid Retrieval",
    sublabel: "FTS + Vector (768-d)",
    icon: Search,
  },
  {
    id: "fusion",
    label: "RRF Fusion",
    sublabel: "RRF k=60 + ±1 Chunks",
    icon: Layers,
  },
  {
    id: "reasoning",
    label: "Agent Synthesis",
    sublabel: "PydanticAI + Gemini Flash",
    icon: Brain,
  },
  {
    id: "validating",
    label: "4-Gate Grounding",
    sublabel: "Fail-Closed Verification",
    icon: ShieldCheck,
  },
]

export function PipelineStatusIndicator({ status }: PipelineStatusIndicatorProps) {
  const [showTechnicalTrace, setShowTechnicalTrace] = useState(false)

  if (!status) return null

  const stage = status.stage.toLowerCase()

  // Map stage to index
  let activeIdx = 0
  if (stage === "searching") activeIdx = 0
  else if (stage === "fusion") activeIdx = 1
  else if (stage === "reasoning") activeIdx = 2
  else if (stage === "validating") activeIdx = 3
  else if (stage === "complete") activeIdx = 4

  const details = status.technical_details || {}
  const hasDetails = Object.keys(details).length > 0

  return (
    <div className="my-3 overflow-hidden rounded-2xl border border-primary/25 bg-card/90 p-4 shadow-sm backdrop-blur-md transition-all animate-in fade-in slide-in-from-bottom-2">
      {/* Top Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <div className="relative mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary shadow-xs">
            {stage === "searching" && <Search className="h-4 w-4 animate-pulse" />}
            {stage === "fusion" && <Layers className="h-4 w-4 animate-bounce" />}
            {stage === "reasoning" && <Sparkles className="h-4 w-4 animate-spin" />}
            {stage === "validating" && <ShieldCheck className="h-4 w-4 animate-pulse" />}
            {stage === "complete" && <CheckCircle2 className="h-4 w-4 text-emerald-500" />}
          </div>

          <div>
            <div className="flex items-center gap-2">
              <h4 className="text-xs font-bold tracking-tight text-foreground">
                {status.title || (
                  stage === "searching"
                    ? "Concurrent Hybrid Retrieval (FTS + pgvector)"
                    : stage === "fusion"
                    ? "Reciprocal Rank Fusion & Neighbor Expansion"
                    : stage === "reasoning"
                    ? "PydanticAI Agent Reasoning & Synthesis"
                    : stage === "validating"
                    ? "4-Gate Fail-Closed Grounding Verification"
                    : "Pipeline Execution Complete"
                )}
              </h4>
              <span className="rounded bg-primary/10 px-1.5 py-0.2 font-mono text-[9px] font-semibold text-primary">
                Step {Math.min(activeIdx + 1, 4)} of 4
              </span>
            </div>
            <p className="mt-0.5 text-[11.5px] leading-relaxed text-muted-foreground">
              {status.message}
            </p>
          </div>
        </div>

        {/* Live telemetry pill */}
        <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full border border-primary/20 bg-primary/5 px-2.5 py-1 text-[10px] font-medium text-primary">
          <span className="h-1.5 w-1.5 animate-ping rounded-full bg-primary" />
          Active Telemetry
        </span>
      </div>

      {/* 4-Step Technical Stepper */}
      <div className="mt-3.5 grid grid-cols-2 gap-2 sm:grid-cols-4 border-t border-border/50 pt-3">
        {STAGES.map((s, idx) => {
          const Icon = s.icon
          const isDone = activeIdx > idx
          const isCurrent = activeIdx === idx

          return (
            <div
              key={s.id}
              className={cn(
                "flex flex-col justify-between rounded-xl p-2.5 text-[11px] font-medium transition-all",
                isDone && "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20",
                isCurrent && "bg-primary/10 text-primary border border-primary/30 ring-1 ring-primary/20",
                !isDone && !isCurrent && "border border-border/30 bg-muted/30 text-muted-foreground/60"
              )}
            >
              <div className="flex items-center justify-between">
                <Icon
                  className={cn(
                    "h-3.5 w-3.5",
                    isCurrent && "animate-pulse text-primary",
                    isDone && "text-emerald-500"
                  )}
                />
                {isDone ? (
                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                ) : isCurrent ? (
                  <span className="h-1.5 w-1.5 animate-ping rounded-full bg-primary" />
                ) : null}
              </div>

              <div className="mt-1.5">
                <span className="block font-semibold leading-tight">{s.label}</span>
                <span className="block text-[9.5px] opacity-75 font-mono leading-tight mt-0.5">
                  {s.sublabel}
                </span>
              </div>
            </div>
          )
        })}
      </div>

      {/* Technical Detail Tags */}
      {hasDetails && (
        <div className="mt-3 flex flex-wrap gap-1.5 pt-1">
          {Object.entries(details).map(([key, val]) => (
            <span
              key={key}
              className="inline-flex items-center gap-1 rounded-md border border-border/60 bg-muted/60 px-2 py-0.5 font-mono text-[10px] text-muted-foreground"
            >
              <span className="text-foreground/70">{key.replace(/_/g, " ")}:</span>
              <span className="font-semibold text-foreground">
                {Array.isArray(val) ? val.length : String(val)}
              </span>
            </span>
          ))}
        </div>
      )}

      {/* Expandable Technical Trace Toggle */}
      <div className="mt-3 border-t border-border/40 pt-2 flex items-center justify-between text-[11px]">
        <button
          type="button"
          onClick={() => setShowTechnicalTrace(!showTechnicalTrace)}
          className="flex items-center gap-1 font-mono text-[10.5px] text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
        >
          <Terminal className="h-3 w-3 text-primary" />
          <span>{showTechnicalTrace ? "Hide Technical Pipeline Trace" : "View Technical Pipeline Trace"}</span>
          {showTechnicalTrace ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
        </button>

        <span className="font-mono text-[10px] text-muted-foreground/60">
          Supabase pgvector · Gemini 3 Flash
        </span>
      </div>

      {/* Collapsible Architecture Trace Drawer */}
      {showTechnicalTrace && (
        <div className="mt-2.5 rounded-xl border border-border/70 bg-black/40 p-3 font-mono text-[11px] leading-relaxed text-foreground/90 space-y-2 animate-in fade-in">
          <div className="flex items-center gap-1.5 text-primary text-[10px] font-bold uppercase tracking-wider">
            <Cpu className="h-3 w-3" />
            <span>Architecture Telemetry</span>
          </div>
          <ul className="space-y-1 text-[10.5px] text-muted-foreground">
            <li>
              • <strong className="text-foreground">Embedding Model</strong>: <span className="text-primary">BAAI/bge-base-en-v1.5</span> (768 dimensions, cosine similarity)
            </li>
            <li>
              • <strong className="text-foreground">FTS Query Engine</strong>: PostgreSQL <span className="text-primary">websearch_to_tsquery</span> with salient keyword extractor & <span className="text-primary">ts_rank_cd</span>
            </li>
            <li>
              • <strong className="text-foreground">Fusion Algorithm</strong>: Reciprocal Rank Fusion (<span className="text-primary">RRF k=60</span>) with boundary context expansion
            </li>
            <li>
              • <strong className="text-foreground">Reasoning Engine</strong>: <span className="text-primary">PydanticAI Agent</span> via Google AI Studio Gemini Flash Preview
            </li>
            <li>
              • <strong className="text-foreground">Safety Contract</strong>: Meridian Research <span className="text-primary">4-Gate Fail-Closed GroundingValidator</span>
            </li>
          </ul>
        </div>
      )}
    </div>
  )
}

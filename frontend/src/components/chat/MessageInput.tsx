import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react"
import { Check, ChevronDown, CornerDownLeft } from "lucide-react"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"

export const FREE_GEMINI_MODELS = [
  {
    id: "gemini-2.5-flash",
    name: "Gemini 2.5 Flash",
    tag: "Fast & Smart",
    desc: "Optimal speed & high quality reasoning for SEC 10-K analysis",
  },
  {
    id: "gemini-2.5-pro",
    name: "Gemini 2.5 Pro",
    tag: "Deep Reasoning",
    desc: "Maximum depth & precision for complex financial tables & math",
  },
  {
    id: "gemini-2.0-flash-lite",
    name: "Gemini 2.0 Flash Lite",
    tag: "Ultra Fast",
    desc: "Lowest latency, lightweight quick answers",
  },
] as const

interface MessageInputProps {
  onSend: (message: string, model?: string) => void
  disabled?: boolean
}

export function MessageInput({ onSend, disabled }: MessageInputProps) {
  const [input, setInput] = useState("")
  const [selectedModel, setSelectedModel] = useState<string>(() => {
    if (typeof window !== "undefined") {
      return localStorage.getItem("selected_llm_model") || "gemini-2.5-flash"
    }
    return "gemini-2.5-flash"
  })

  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Auto-resize textarea based on scrollHeight
  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = "auto"
    const nextHeight = Math.min(el.scrollHeight, 140)
    el.style.height = `${Math.max(nextHeight, 36)}px`
  }, [input])

  function handleSubmit(e?: FormEvent) {
    if (e) e.preventDefault()
    const trimmed = input.trim()
    if (!trimmed || disabled) return
    onSend(trimmed, selectedModel)
    setInput("")
    if (textareaRef.current) {
      textareaRef.current.style.height = "36px"
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  const currentModel =
    FREE_GEMINI_MODELS.find((m) => m.id === selectedModel) || FREE_GEMINI_MODELS[0]

  return (
    <div className="w-full bg-linear-to-t from-background via-background/95 to-transparent px-4 pb-4 pt-2 select-none">
      <div className="mx-auto max-w-3xl">
        <form
          onSubmit={handleSubmit}
          className="relative flex items-center gap-2 rounded-full border border-zinc-200/90 bg-white/95 px-3 py-1.5 shadow-xs transition-all focus-within:border-foreground/30 focus-within:shadow-sm dark:border-[#333333] dark:bg-[#212121]"
        >
          {/* Left Side: Model Selector Dropdown with actual Gemini Logo */}
          <DropdownMenu>
            <Tooltip>
              <TooltipTrigger asChild>
                <DropdownMenuTrigger asChild>
                  <button
                    type="button"
                    className="flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium text-muted-foreground hover:bg-muted/70 hover:text-foreground transition-all cursor-pointer outline-none border border-transparent hover:border-border/60 shrink-0"
                    aria-label="Select model"
                  >
                    <img
                      src="/gemini-logo.png"
                      alt="Gemini"
                      className="size-3.5 object-contain shrink-0"
                    />
                    <span className="font-mono text-[10.5px] hidden sm:inline">
                      {currentModel.name}
                    </span>
                    <ChevronDown className="size-2.5 opacity-60 shrink-0" />
                  </button>
                </DropdownMenuTrigger>
              </TooltipTrigger>
              <TooltipContent side="top">Select Gemini Model</TooltipContent>
            </Tooltip>

            <DropdownMenuContent
              align="start"
              side="top"
              sideOffset={8}
              className="w-68 p-1.5 rounded-2xl border border-zinc-200 bg-white shadow-xl dark:border-[#333333] dark:bg-[#212121] dark:text-[#ececec]"
            >
              {FREE_GEMINI_MODELS.map((m) => {
                const isSelected = m.id === selectedModel
                return (
                  <DropdownMenuItem
                    key={m.id}
                    onClick={() => {
                      setSelectedModel(m.id)
                      localStorage.setItem("selected_llm_model", m.id)
                    }}
                    className={cn(
                      "flex flex-col items-start gap-0.5 rounded-xl px-2.5 py-2 cursor-pointer transition-colors",
                      isSelected
                        ? "bg-accent text-accent-foreground font-medium"
                        : "hover:bg-muted/70 dark:hover:bg-[#2c2c2c]"
                    )}
                  >
                    <div className="flex w-full items-center justify-between">
                      <span className="text-xs font-medium text-foreground flex items-center gap-1.5">
                        <img
                          src="/gemini-logo.png"
                          alt="Gemini"
                          className="size-3 object-contain shrink-0"
                        />
                        {m.name}
                        {isSelected && <Check className="size-3 text-primary shrink-0 ml-1" />}
                      </span>
                      <span className="font-mono text-[9px] px-1.5 py-0.2 rounded-md bg-muted text-muted-foreground">
                        {m.tag}
                      </span>
                    </div>
                    <span className="text-[10px] text-muted-foreground line-clamp-1 pl-4.5">
                      {m.desc}
                    </span>
                  </DropdownMenuItem>
                )
              })}
            </DropdownMenuContent>
          </DropdownMenu>

          {/* Middle: Textarea */}
          <textarea
            ref={textareaRef}
            rows={1}
            placeholder="Ask an SEC 10-K filing question (e.g. Compare Apple & Microsoft Cloud revenue in 2024)..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            className="max-h-36 min-h-[36px] flex-1 resize-none bg-transparent py-2 text-sm leading-snug outline-none placeholder:text-muted-foreground/45 placeholder:text-[13.5px] placeholder:font-light disabled:opacity-50"
          />

          {/* Right Side: Submit Arrow Button */}
          <button
            type="submit"
            disabled={!input.trim() || disabled}
            className={cn(
              "flex size-8 shrink-0 items-center justify-center rounded-full transition-all cursor-pointer outline-none",
              input.trim() && !disabled
                ? "bg-foreground text-background hover:opacity-90 active:scale-95 shadow-2xs"
                : "bg-muted/60 text-muted-foreground/35 cursor-not-allowed dark:bg-[#2c2c2c] dark:text-zinc-600"
            )}
            aria-label="Send message"
          >
            <CornerDownLeft className="size-4" strokeWidth={1.5} />
          </button>
        </form>
      </div>
    </div>
  )
}

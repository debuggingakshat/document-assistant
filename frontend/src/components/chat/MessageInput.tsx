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
    id: "gemini-3.5-flash-lite",
    name: "Gemini 3.5 Flash Lite",
    tag: "Recommended",
  },
  {
    id: "gemini-3-flash-preview",
    name: "Gemini 3 Flash",
    tag: "Flagship",
  },
  {
    id: "gemini-flash-lite-latest",
    name: "Gemini Flash Lite",
    tag: "Fastest",
  },
  {
    id: "gemini-2.0-flash",
    name: "Gemini 2.0 Flash",
    tag: "High Speed",
  },
  {
    id: "gemini-2.5-flash",
    name: "Gemini 2.5 Flash",
    tag: "Balanced",
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
      const saved = localStorage.getItem("selected_llm_model")
      if (saved && FREE_GEMINI_MODELS.some((m) => m.id === saved)) {
        return saved
      }
    }
    return "gemini-3.5-flash-lite"
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

  // Listen for smart research prompt chip clicks (Option B: Populate & Edit Editor)
  useEffect(() => {
    function handlePopulateInput(e: Event) {
      const customEvent = e as CustomEvent<{ text: string }>
      const newText = customEvent.detail?.text || ""
      if (!newText) return
      setInput(newText)
      setTimeout(() => {
        const el = textareaRef.current
        if (el) {
          el.focus()
          el.setSelectionRange(newText.length, newText.length)
          el.style.height = "auto"
          const nextHeight = Math.min(el.scrollHeight, 140)
          el.style.height = `${Math.max(nextHeight, 36)}px`
        }
      }, 50)
    }

    window.addEventListener("meridian_populate_input", handlePopulateInput)
    return () => {
      window.removeEventListener("meridian_populate_input", handlePopulateInput)
    }
  }, [])

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
              className="w-72 p-1.5 rounded-2xl border border-zinc-200 bg-white shadow-xl dark:border-[#333333] dark:bg-[#212121] dark:text-[#ececec]"
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
                      "flex items-center justify-between gap-2 rounded-xl px-2.5 py-1.5 cursor-pointer transition-colors",
                      isSelected
                        ? "bg-accent text-accent-foreground font-medium"
                        : "hover:bg-muted/70 dark:hover:bg-[#2c2c2c]"
                    )}
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <img
                        src="/gemini-logo.png"
                        alt="Gemini"
                        className="size-3.5 object-contain shrink-0"
                      />
                      <span className="text-xs font-medium text-foreground truncate">
                        {m.name}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-muted text-muted-foreground whitespace-nowrap">
                        {m.tag}
                      </span>
                      {isSelected ? (
                        <Check className="size-3.5 text-primary shrink-0" />
                      ) : (
                        <span className="size-3.5 shrink-0" />
                      )}
                    </div>
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

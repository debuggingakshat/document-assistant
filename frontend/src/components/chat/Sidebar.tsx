import { useEffect, useMemo, useState, type KeyboardEvent, type MouseEvent } from "react"
import { Link, useNavigate } from "react-router-dom"
import {
  Archive,
  ArchiveRestore,
  Check,
  FolderArchive,
  LogOut,
  MessageCircle,
  MessageSquare,
  MoreHorizontal,
  PanelLeftClose,
  PanelLeftOpen,
  Pencil,
  Pin,
  Plus,
  Search,
  SquarePen,
  Trash2,
  X,
} from "lucide-react"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import {
  deleteThread,
  listThreads,
  updateThread,
  type Thread,
} from "@/lib/api"
import { useAuth } from "@/lib/auth"
import { cn } from "@/lib/utils"

interface SidebarProps {
  activeThreadId?: string
  isCollapsed?: boolean
  onToggleCollapse?: () => void
}


function formatRelativeTime(dateStr?: string): string {
  if (!dateStr) return ""
  const d = new Date(dateStr)
  if (isNaN(d.getTime())) return ""
  const now = new Date()
  const diffSec = Math.floor((now.getTime() - d.getTime()) / 1000)
  if (diffSec < 60) return "now"
  const diffMin = Math.floor(diffSec / 60)
  if (diffMin < 60) return `${diffMin}m`
  const diffHours = Math.floor(diffMin / 60)
  if (diffHours < 24) return `${diffHours}h`
  const diffDays = Math.floor(diffHours / 24)
  if (diffDays === 1) return "1d"
  if (diffDays < 7) return `${diffDays}d`
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" })
}

export function Sidebar({
  activeThreadId,
  isCollapsed = false,
  onToggleCollapse,
}: SidebarProps) {
  const navigate = useNavigate()
  const { user, signOut } = useAuth()

  const [threads, setThreads] = useState<Thread[]>([])
  const [archivedThreads, setArchivedThreads] = useState<Thread[]>([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState("")

  // Local active thread tracker synchronized with background thread creation & resets
  const [localActiveId, setLocalActiveId] = useState<string | undefined>(activeThreadId)

  useEffect(() => {
    setLocalActiveId(activeThreadId)
  }, [activeThreadId])

  const effectiveActiveThreadId = localActiveId ?? activeThreadId

  // Collapsed rail popover states
  const [railSearchOpen, setRailSearchOpen] = useState(false)
  const [railSearchQuery, setRailSearchQuery] = useState("")
  const [railPinOpen, setRailPinOpen] = useState(false)
  const [railRecentOpen, setRailRecentOpen] = useState(false)
  const [isEdgeHovered, setIsEdgeHovered] = useState(false)

  // Inline rename state
  const [editingThreadId, setEditingThreadId] = useState<string | null>(null)
  const [editTitle, setEditTitle] = useState("")
  const [savingEdit, setSavingEdit] = useState(false)
  const [deletingThreadId, setDeletingThreadId] = useState<string | null>(null)
  // Delete confirmation states (Big Tech pattern: ask every time vs never ask again)
  const [threadPendingDelete, setThreadPendingDelete] = useState<Thread | null>(null)
  const [dontAskAgainDelete, setDontAskAgainDelete] = useState<boolean>(false)
  const [skipDeleteConfirm, setSkipDeleteConfirm] = useState<boolean>(() => {
    if (typeof window !== "undefined") {
      return localStorage.getItem("meridian_skip_delete_confirm") === "true"
    }
    return false
  })

  // Archived dialog state
  const [showArchivedDialog, setShowArchivedDialog] = useState(false)
  const [loadingArchived, setLoadingArchived] = useState(false)

  // Filtered threads for collapsed rail popovers
  const railSearchResults = useMemo(() => {
    if (!railSearchQuery.trim()) return threads.slice(0, 10)
    const q = railSearchQuery.toLowerCase()
    return threads.filter((t) =>
      (t.title || "Untitled Analysis").toLowerCase().includes(q)
    )
  }, [threads, railSearchQuery])

  const recentTenThreads = useMemo(() => threads.slice(0, 10), [threads])

  // Resizable sidebar width with localStorage persistence (clamped 240px - 500px, default 280px)
  const [sidebarWidth, setSidebarWidth] = useState<number>(() => {
    if (typeof window !== "undefined") {
      const saved = localStorage.getItem("sidebar_width")
      if (saved) {
        const parsed = parseInt(saved, 10)
        if (!isNaN(parsed) && parsed >= 200 && parsed <= 500) {
          return parsed
        }
      }
    }
    return 280
  })
  const [isResizing, setIsResizing] = useState(false)

  // Drag-to-resize listener with snap-to-collapse
  useEffect(() => {
    if (!isResizing) return

    function handleMouseMove(e: globalThis.MouseEvent) {
      // If user drags much slimmer (< 150px), snap-close the sidebar
      if (e.clientX < 150) {
        setIsResizing(false)
        if (onToggleCollapse) {
          onToggleCollapse()
        }
        return
      }

      // Otherwise clamp width between 200px and 500px
      const newWidth = Math.min(Math.max(e.clientX, 200), 500)
      setSidebarWidth(newWidth)
    }

    function handleMouseUp(e: globalThis.MouseEvent) {
      setIsResizing(false)
      if (e.clientX < 150) {
        if (onToggleCollapse) {
          onToggleCollapse()
        }
      } else {
        const finalWidth = Math.min(Math.max(e.clientX, 200), 500)
        setSidebarWidth(finalWidth)
        localStorage.setItem("sidebar_width", String(finalWidth))
      }
    }

    document.body.style.cursor = "col-resize"
    document.body.style.userSelect = "none"

    window.addEventListener("mousemove", handleMouseMove)
    window.addEventListener("mouseup", handleMouseUp)

    return () => {
      document.body.style.cursor = ""
      document.body.style.userSelect = ""
      window.removeEventListener("mousemove", handleMouseMove)
      window.removeEventListener("mouseup", handleMouseUp)
    }
  }, [isResizing, onToggleCollapse])

  function handleStartResize(e: MouseEvent) {
    e.preventDefault()
    setIsResizing(true)
  }

  function handleResetResize() {
    setSidebarWidth(280)
    localStorage.setItem("sidebar_width", "280")
  }

  // Listen for real-time auto-generated thread title updates & stream completions
  useEffect(() => {
    function handleThreadTitleUpdate(e: Event) {
      const customEvent = e as CustomEvent<{ threadId: string; title: string }>
      if (!customEvent.detail) return
      const { threadId, title } = customEvent.detail
      setThreads((prev) =>
        prev.map((t) => (t.id === threadId ? { ...t, title } : t))
      )
    }

    function handleStreamFinished(e: Event) {
      const customEvent = e as CustomEvent<{ threadId?: string }>
      const targetTid = customEvent.detail?.threadId
      if (!targetTid) return
      // Re-fetch active threads so newly generated title in Supabase is immediately visible in the sidebar
      listThreads(false).then((activeList) => {
        setThreads(activeList)
      }).catch(() => {})
    }

    window.addEventListener("thread_title_updated", handleThreadTitleUpdate)
    window.addEventListener("meridian_stream_finished", handleStreamFinished)
    return () => {
      window.removeEventListener("thread_title_updated", handleThreadTitleUpdate)
      window.removeEventListener("meridian_stream_finished", handleStreamFinished)
    }
  }, [])

  // Fetch active and archived threads once on initial mount
  useEffect(() => {
    let isMounted = true

    async function loadThreads() {
      try {
        const [activeList, archivedList] = await Promise.all([
          listThreads(false),
          listThreads(true),
        ])
        if (isMounted) {
          setThreads(activeList)
          setArchivedThreads(archivedList)
          setLoading(false)
        }
      } catch {
        if (isMounted) setLoading(false)
      }
    }

    void loadThreads()

    return () => {
      isMounted = false
    }
  }, [])

  // Listen for newly created threads and draft reset events
  useEffect(() => {
    function handleThreadCreated(e: Event) {
      const newThread = (e as CustomEvent<Thread>).detail
      if (newThread && newThread.id) {
        setThreads((prev) => [newThread, ...prev.filter((t) => t.id !== newThread.id)])
        setLocalActiveId(newThread.id)
      }
    }

    function handleResetToDraft() {
      setLocalActiveId(undefined)
    }

    window.addEventListener("meridian_thread_created", handleThreadCreated)
    window.addEventListener("meridian_reset_to_draft", handleResetToDraft)
    return () => {
      window.removeEventListener("meridian_thread_created", handleThreadCreated)
      window.removeEventListener("meridian_reset_to_draft", handleResetToDraft)
    }
  }, [])

  // Filter & bucket threads by timeframe
  const filteredThreads = useMemo(() => {
    if (!searchQuery.trim()) return threads
    const q = searchQuery.toLowerCase()
    return threads.filter((t) =>
      (t.title || "Untitled Analysis").toLowerCase().includes(q)
    )
  }, [threads, searchQuery])

  const { pinnedThreads, todayThreads, weekThreads, olderThreads } = useMemo(() => {
    const now = new Date()
    const pinned: Thread[] = []
    const today: Thread[] = []
    const week: Thread[] = []
    const older: Thread[] = []

    for (const t of filteredThreads) {
      if (t.is_pinned) {
        pinned.push(t)
        continue
      }

      const d = new Date(t.created_at || t.updated_at)
      const diffMs = now.getTime() - d.getTime()
      const diffDays = diffMs / (1000 * 60 * 60 * 24)

      if (diffDays < 1 && d.getDate() === now.getDate()) {
        today.push(t)
      } else if (diffDays < 7) {
        week.push(t)
      } else {
        older.push(t)
      }
    }

    return {
      pinnedThreads: pinned,
      todayThreads: today,
      weekThreads: week,
      olderThreads: older,
    }
  }, [filteredThreads])

  function handleNewChat() {
    setLocalActiveId(undefined)
    window.dispatchEvent(new CustomEvent("meridian_reset_to_draft"))
    window.dispatchEvent(new CustomEvent("meridian_rotate_prompts"))
    navigate("/", { replace: true })
    if (typeof window !== "undefined") {
      window.history.replaceState(null, "", "/")
    }
  }

  function handleStartRename(e: MouseEvent, thread: Thread) {
    e.preventDefault()
    e.stopPropagation()
    setEditingThreadId(thread.id)
    setEditTitle(thread.title || "")
  }

  function handleCancelRename(e?: MouseEvent) {
    if (e) {
      e.preventDefault()
      e.stopPropagation()
    }
    setEditingThreadId(null)
    setEditTitle("")
  }

  async function handleSaveRename(e: MouseEvent | KeyboardEvent, threadId: string) {
    e.preventDefault()
    e.stopPropagation()
    const trimmed = editTitle.trim()
    if (!trimmed || savingEdit) return

    setSavingEdit(true)
    try {
      const updated = await updateThread(threadId, { title: trimmed })
      setThreads((prev) => prev.map((t) => (t.id === threadId ? updated : t)))
      setArchivedThreads((prev) =>
        prev.map((t) => (t.id === threadId ? updated : t))
      )
      setEditingThreadId(null)
      setEditTitle("")
    } catch {
      // Failed to rename
    } finally {
      setSavingEdit(false)
    }
  }

  async function handleTogglePin(e: MouseEvent, thread: Thread) {
    e.preventDefault()
    e.stopPropagation()
    const nextPinned = !thread.is_pinned

    // Optimistic local update
    setThreads((prev) =>
      prev.map((t) => (t.id === thread.id ? { ...t, is_pinned: nextPinned } : t))
    )

    try {
      const updated = await updateThread(thread.id, { is_pinned: nextPinned })
      setThreads((prev) =>
        prev.map((t) => (t.id === thread.id ? updated : t))
      )
    } catch {
      // Revert on error
      setThreads((prev) =>
        prev.map((t) =>
          t.id === thread.id ? { ...t, is_pinned: thread.is_pinned } : t
        )
      )
    }
  }

  async function handleToggleArchive(e: MouseEvent, thread: Thread) {
    e.preventDefault()
    e.stopPropagation()
    const nextArchived = !thread.is_archived

    if (nextArchived) {
      // Moving from active to archived
      setThreads((prev) => prev.filter((t) => t.id !== thread.id))
      setArchivedThreads((prev) => [{ ...thread, is_archived: true }, ...prev])
    } else {
      // Restoring from archived to active
      setArchivedThreads((prev) => prev.filter((t) => t.id !== thread.id))
      setThreads((prev) => [{ ...thread, is_archived: false }, ...prev])
    }

    try {
      await updateThread(thread.id, { is_archived: nextArchived })
      if (nextArchived && effectiveActiveThreadId === thread.id) {
        navigate("/")
      }
    } catch {
      // Re-fetch to ensure sync on error
      const [activeList, archivedList] = await Promise.all([
        listThreads(false),
        listThreads(true),
      ])
      setThreads(activeList)
      setArchivedThreads(archivedList)
    }
  }

  function handleRequestDelete(e: MouseEvent, thread: Thread) {
    e.preventDefault()
    e.stopPropagation()

    // If user previously selected "Don't ask again", bypass modal and perform 0ms instant delete
    if (skipDeleteConfirm || localStorage.getItem("meridian_skip_delete_confirm") === "true") {
      void executeOptimisticDelete(thread.id)
      return
    }

    setThreadPendingDelete(thread)
    setDontAskAgainDelete(false)
  }

  async function executeOptimisticDelete(threadId: string) {
    if (deletingThreadId) return

    // 1. Snapshot previous state for instant rollback in case of network failure
    const prevThreads = threads
    const prevArchived = archivedThreads

    // 2. 0ms Optimistic Eviction: Immediately remove from UI
    setThreads((prev) => prev.filter((t) => t.id !== threadId))
    setArchivedThreads((prev) => prev.filter((t) => t.id !== threadId))

    // 3. If deleting currently active thread, immediately reset to fresh draft
    if (effectiveActiveThreadId === threadId) {
      navigate("/")
      if (typeof window !== "undefined") {
        window.dispatchEvent(new CustomEvent("meridian_reset_to_draft"))
      }
    }

    // 4. Background Server Deletion (async non-blocking)
    setDeletingThreadId(threadId)
    try {
      await deleteThread(threadId)
    } catch {
      // Rollback on network failure
      setThreads(prevThreads)
      setArchivedThreads(prevArchived)
    } finally {
      setDeletingThreadId(null)
    }
  }

  async function handleRefreshArchived() {
    setLoadingArchived(true)
    try {
      const list = await listThreads(true)
      setArchivedThreads(list)
    } finally {
      setLoadingArchived(false)
    }
  }

  const userInitials = user?.email ? user.email.slice(0, 2).toUpperCase() : "AN"

  // ---------------------------------------------------------------------------
  // Collapsed Rail View (w-14 / 56px)
  // ---------------------------------------------------------------------------
  if (isCollapsed) {
    return (
      <aside className="relative flex h-screen w-14 shrink-0 flex-col justify-between border-r border-border/80 bg-sidebar py-3 transition-all select-none">
        {/* Edge hover/drag sensor: when user hovers mouse near the border to drag open */}
        <div
          onMouseEnter={() => setIsEdgeHovered(true)}
          onMouseLeave={() => setIsEdgeHovered(false)}
          onClick={onToggleCollapse}
          className="group/edge absolute -right-2 top-0 z-30 h-full w-4 cursor-pointer flex items-center justify-center"
          title="Click to open sidebar (⌘B)"
        >
          <div
            className={cn(
              "h-12 w-0.5 rounded-full transition-all duration-200",
              isEdgeHovered ? "bg-muted-foreground/40 opacity-100" : "bg-transparent opacity-0"
            )}
          />
        </div>

        {/* Top Icons */}
        <div className="flex flex-col items-center">
          {/* Logo Emblem Button (switches to PanelLeftOpen on logo hover OR border hover) */}
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                type="button"
                onClick={onToggleCollapse}
                className={cn(
                  "group relative flex size-9 items-center justify-center rounded-xl text-muted-foreground transition-all hover:bg-muted/70 hover:text-foreground cursor-pointer outline-none",
                  isEdgeHovered && "bg-muted/80 text-foreground ring-1 ring-border shadow-xs"
                )}
              >
                {/* Logo emblem - visible by default, smooth fade-out on hover or edge hover */}
                <div
                  className={cn(
                    "absolute inset-0 flex items-center justify-center transition-all duration-200",
                    isEdgeHovered
                      ? "opacity-0 scale-90"
                      : "opacity-100 scale-100 group-hover:opacity-0 group-hover:scale-90"
                  )}
                >
                  <img
                    src="/meridian-emblem-light.png"
                    alt="Meridian Research"
                    className="size-7.5 object-contain dark:hidden"
                  />
                  <img
                    src="/meridian-emblem-dark.png"
                    alt="Meridian Research"
                    className="size-7.5 object-contain hidden dark:block"
                  />
                </div>

                {/* Open sidebar icon - reveals smoothly on hover or edge hover */}
                <div
                  className={cn(
                    "absolute inset-0 flex items-center justify-center transition-all duration-200",
                    isEdgeHovered
                      ? "opacity-100 scale-100"
                      : "opacity-0 scale-90 group-hover:opacity-100 group-hover:scale-100"
                  )}
                >
                  <PanelLeftOpen className="size-4 text-foreground" />
                </div>
                <span className="sr-only">Expand sidebar (⌘B)</span>
              </button>
            </TooltipTrigger>
            <TooltipContent side="right">Expand sidebar (⌘B)</TooltipContent>
          </Tooltip>

          {/* Action icons: Plus, Search, Pin, Recent evenly spaced with slight distance from logo */}
          <div className="mt-4 flex flex-col items-center gap-2">
            {/* New Thread Button - SquarePen icon matching utility suite */}
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  onClick={() => void handleNewChat()}
                  className="group relative flex size-9 items-center justify-center rounded-xl text-muted-foreground transition-all hover:bg-muted/70 hover:text-foreground cursor-pointer outline-none"
                  aria-label="New research thread"
                >
                  <SquarePen className="size-4" />
                </button>
              </TooltipTrigger>
              <TooltipContent side="right">New thread</TooltipContent>
            </Tooltip>
            {/* 1. Search Popover */}
            <Popover open={railSearchOpen} onOpenChange={setRailSearchOpen}>
              <Tooltip open={railSearchOpen ? false : undefined}>
                <TooltipTrigger asChild>
                  <PopoverTrigger asChild>
                    <button
                      type="button"
                      className={cn(
                        "group relative flex size-9 items-center justify-center rounded-xl text-muted-foreground transition-all hover:bg-muted/70 hover:text-foreground cursor-pointer outline-none",
                        railSearchOpen && "bg-muted text-foreground"
                      )}
                      aria-label="Search conversations"
                    >
                      <Search className="size-4" />
                    </button>
                  </PopoverTrigger>
                </TooltipTrigger>
                <TooltipContent side="right">Search</TooltipContent>
              </Tooltip>
              <PopoverContent
                side="right"
                align="start"
                sideOffset={12}
                className="w-80 p-3"
              >
                <div className="flex items-center gap-2 border-b border-border/70 pb-2 px-1">
                  <Search className="size-3.5 text-muted-foreground shrink-0" />
                  <input
                    type="text"
                    placeholder="Search conversations..."
                    value={railSearchQuery}
                    onChange={(e) => setRailSearchQuery(e.target.value)}
                    className="w-full bg-transparent text-xs text-foreground placeholder:text-muted-foreground/70 outline-none"
                    autoFocus
                  />
                  {railSearchQuery && (
                    <button
                      type="button"
                      onClick={() => setRailSearchQuery("")}
                      className="text-muted-foreground hover:text-foreground cursor-pointer p-0.5"
                    >
                      <X className="size-3" />
                    </button>
                  )}
                </div>

                <div className="pt-2">
                  <div className="flex items-center justify-between px-2 pb-1.5 text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">
                    <span>{railSearchQuery.trim() ? "Search Results" : "Recent"}</span>
                    <span className="font-mono text-[9px]">{railSearchResults.length}</span>
                  </div>
                  <div className="flex flex-col gap-0.5 max-h-72 overflow-y-auto">
                    {railSearchResults.length === 0 ? (
                      <div className="py-6 text-center text-xs text-muted-foreground">
                        No conversations found
                      </div>
                    ) : (
                      railSearchResults.map((t) => {
                        const isActive = t.id === effectiveActiveThreadId
                        return (
                          <button
                            key={t.id}
                            type="button"
                            onClick={() => {
                              navigate(`/chat/${t.id}`)
                              setRailSearchOpen(false)
                            }}
                            className={cn(
                              "group flex w-full items-center justify-between gap-2 rounded-xl px-2.5 py-2 text-left text-xs transition-colors cursor-pointer",
                              isActive
                                ? "bg-accent text-accent-foreground font-medium"
                                : "text-foreground hover:bg-muted/70 dark:hover:bg-[#2c2c2c]"
                            )}
                          >
                            <div className="flex items-center gap-2 min-w-0 flex-1">
                              <MessageSquare className="size-3.5 shrink-0 text-muted-foreground group-hover:text-foreground" />
                              <span className="truncate">{t.title || "Untitled Analysis"}</span>
                            </div>
                            <div className="flex items-center gap-1.5 shrink-0">
                              <span className="text-[10px] text-muted-foreground font-mono">
                                {formatRelativeTime(t.created_at || t.updated_at)}
                              </span>
                            </div>
                          </button>
                        )
                      })
                    )}
                  </div>
                </div>
              </PopoverContent>
            </Popover>

            {/* 2. Pin Popover */}
            <Popover open={railPinOpen} onOpenChange={setRailPinOpen}>
              <Tooltip open={railPinOpen ? false : undefined}>
                <TooltipTrigger asChild>
                  <PopoverTrigger asChild>
                    <button
                      type="button"
                      className={cn(
                        "group relative flex size-9 items-center justify-center rounded-xl text-muted-foreground transition-all hover:bg-muted/70 hover:text-foreground cursor-pointer outline-none",
                        railPinOpen && "bg-muted text-foreground"
                      )}
                      aria-label="Pinned conversations"
                    >
                      <Pin className="size-4" />
                    </button>
                  </PopoverTrigger>
                </TooltipTrigger>
                <TooltipContent side="right">Pinned</TooltipContent>
              </Tooltip>
              <PopoverContent
                side="right"
                align="start"
                sideOffset={12}
                className="w-80 p-3"
              >
                <div className="flex items-center justify-between border-b border-border/70 pb-2 px-1">
                  <div className="flex items-center gap-2">
                    <Pin className="size-3.5 text-foreground" />
                    <span className="text-xs font-semibold text-foreground">Pinned Conversations</span>
                  </div>
                  <Badge variant="secondary" className="text-[10px] px-1.5 py-0 h-4 font-mono">
                    {pinnedThreads.length}
                  </Badge>
                </div>

                <div className="pt-2">
                  <div className="flex flex-col gap-0.5 max-h-72 overflow-y-auto">
                    {pinnedThreads.length === 0 ? (
                      <div className="py-8 px-4 text-center">
                        <Pin className="size-6 text-muted-foreground/40 mx-auto mb-2" />
                        <p className="text-xs font-medium text-foreground">No pinned conversations</p>
                        <p className="text-[11px] text-muted-foreground mt-0.5">
                          Pin threads from the full sidebar to access them quickly here.
                        </p>
                      </div>
                    ) : (
                      pinnedThreads.map((t) => {
                        const isActive = t.id === effectiveActiveThreadId
                        return (
                          <button
                            key={t.id}
                            type="button"
                            onClick={() => {
                              navigate(`/chat/${t.id}`)
                              setRailPinOpen(false)
                            }}
                            className={cn(
                              "group flex w-full items-center justify-between gap-2 rounded-xl px-2.5 py-2 text-left text-xs transition-colors cursor-pointer",
                              isActive
                                ? "bg-accent text-accent-foreground font-medium"
                                : "text-foreground hover:bg-muted/70 dark:hover:bg-[#2c2c2c]"
                            )}
                          >
                            <div className="flex items-center gap-2 min-w-0 flex-1">
                              <Pin className="size-3.5 shrink-0 text-muted-foreground group-hover:text-foreground" />
                              <span className="truncate">{t.title || "Untitled Analysis"}</span>
                            </div>
                            <span className="text-[10px] text-muted-foreground font-mono shrink-0">
                              {formatRelativeTime(t.created_at || t.updated_at)}
                            </span>
                          </button>
                        )
                      })
                    )}
                  </div>
                </div>
              </PopoverContent>
            </Popover>

            {/* 3. Recent Conversations Popover (10 most recent conversations without opening sidebar) */}
            <Popover open={railRecentOpen} onOpenChange={setRailRecentOpen}>
              <Tooltip open={railRecentOpen ? false : undefined}>
                <TooltipTrigger asChild>
                  <PopoverTrigger asChild>
                    <button
                      type="button"
                      className={cn(
                        "group relative flex size-9 items-center justify-center rounded-xl text-muted-foreground transition-all hover:bg-muted/70 hover:text-foreground cursor-pointer outline-none",
                        railRecentOpen && "bg-muted text-foreground"
                      )}
                      aria-label="Recent conversations"
                    >
                      <MessageCircle className="size-4" />
                    </button>
                  </PopoverTrigger>
                </TooltipTrigger>
                <TooltipContent side="right">Recents</TooltipContent>
              </Tooltip>
              <PopoverContent
                side="right"
                align="start"
                sideOffset={12}
                className="w-52 p-2"
              >
                <div className="border-b border-border/70 pb-1.5 px-1.5">
                  <span className="text-xs font-semibold text-foreground">Recents</span>
                </div>

                <div className="pt-1.5">
                  <div className="flex flex-col gap-0.5 max-h-80 overflow-y-auto">
                    {recentTenThreads.length === 0 ? (
                      <div className="py-6 px-2 text-center">
                        <p className="text-xs font-medium text-foreground">No recent conversations</p>
                        <p className="text-[11px] text-muted-foreground mt-0.5">
                          Click + above to start a research thread.
                        </p>
                      </div>
                    ) : (
                      recentTenThreads.map((t) => {
                        const isActive = t.id === effectiveActiveThreadId
                        return (
                          <button
                            key={t.id}
                            type="button"
                            onClick={() => {
                              navigate(`/chat/${t.id}`)
                              setRailRecentOpen(false)
                            }}
                            className={cn(
                              "group flex w-full items-center justify-between gap-1.5 rounded-lg px-2 py-1.5 text-left text-xs transition-colors cursor-pointer",
                              isActive
                                ? "bg-accent text-accent-foreground font-medium"
                                : "text-foreground hover:bg-muted/70 dark:hover:bg-[#2c2c2c]"
                            )}
                          >
                            <span className="truncate min-w-0 flex-1">{t.title || "Untitled Analysis"}</span>
                            <div className="flex items-center gap-1 shrink-0 ml-1">
                              <span className="text-[10px] text-muted-foreground font-mono">
                                {formatRelativeTime(t.created_at || t.updated_at)}
                              </span>
                            </div>
                          </button>
                        )
                      })
                    )}
                  </div>
                </div>
              </PopoverContent>
            </Popover>
          </div>
        </div>

        {/* Bottom User Avatar */}
        <div className="flex flex-col items-center gap-2">
          {archivedThreads.length > 0 && (
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  onClick={() => setShowArchivedDialog(true)}
                  className="text-muted-foreground hover:text-foreground cursor-pointer"
                >
                  <Archive className="size-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="right">
                Archived chats ({archivedThreads.length})
              </TooltipContent>
            </Tooltip>
          )}

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon-sm" className="rounded-lg p-0">
                <Avatar className="size-7">
                  <AvatarFallback className="text-[10px] bg-primary/10 text-primary">
                    {userInitials}
                  </AvatarFallback>
                </Avatar>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent side="right" align="end" className="w-56">
              <DropdownMenuLabel className="font-normal">
                <div className="flex flex-col space-y-1">
                  <p className="text-xs font-semibold text-foreground truncate">
                    {user?.email}
                  </p>
                  <p className="text-[10px] text-muted-foreground">
                    Equity Research Analyst
                  </p>
                </div>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onClick={() => {
                  const current = localStorage.getItem("meridian_skip_delete_confirm") === "true"
                  if (current) {
                    localStorage.removeItem("meridian_skip_delete_confirm")
                    setSkipDeleteConfirm(false)
                  } else {
                    localStorage.setItem("meridian_skip_delete_confirm", "true")
                    setSkipDeleteConfirm(true)
                  }
                }}
                className="cursor-pointer gap-2.5 rounded-xl px-2.5 py-2 text-xs font-medium text-zinc-800 transition-colors hover:bg-zinc-100 dark:text-[#ececec] dark:hover:bg-[#2c2c2c]"
              >
                <Trash2 className="size-3.5 opacity-80" />
                <div className="flex flex-1 items-center justify-between">
                  <span>Confirm deletions</span>
                  <span className="text-[10px] text-muted-foreground font-mono">
                    {!skipDeleteConfirm ? "Always" : "Never"}
                  </span>
                </div>
              </DropdownMenuItem>
              <DropdownMenuSeparator className="my-1 -mx-1 h-px bg-zinc-200 dark:bg-[#333333]" />
              <DropdownMenuItem
                onClick={() => void signOut()}
                className="text-destructive focus:text-destructive"
              >
                <LogOut className="mr-2 size-3.5" />
                <span>Sign out</span>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </aside>
    )
  }

  // ---------------------------------------------------------------------------
  // Full Expanded Sidebar View (Resizable width)
  // ---------------------------------------------------------------------------
  return (
    <>
      <aside
        style={{ width: `${sidebarWidth}px` }}
        className={cn(
          "relative flex h-screen shrink-0 flex-col justify-between border-r border-border/80 bg-sidebar select-none",
          isResizing ? "transition-none" : "transition-[width] duration-150"
        )}
      >
        {/* Draggable Resize Handle */}
        <div
          role="separator"
          aria-orientation="vertical"
          onMouseDown={handleStartResize}
          onDoubleClick={handleResetResize}
          title="Drag to resize sidebar (double-click to reset)"
          className={cn(
            "group/resizer absolute -right-1 top-0 z-30 h-full w-2 cursor-col-resize select-none",
            "after:absolute after:inset-y-0 after:left-1 after:w-0.5 after:transition-colors",
            isResizing
              ? "after:bg-primary"
              : "hover:after:bg-primary/50 after:bg-transparent"
          )}
        />

        {/* Top Workspace Header */}
        <div>
          <div className="flex h-14 items-center justify-between border-b border-border/80 pl-4 pr-3">
            {/* Prominent non-clickable logo with full emblem and name */}
            <div className="flex items-center shrink-0 select-none pointer-events-none">
              <img
                src="/meridian-logo-light.png"
                alt="Meridian Research"
                className="h-8.5 w-auto object-contain dark:hidden"
              />
              <img
                src="/meridian-logo-dark.png"
                alt="Meridian Research"
                className="h-8.5 w-auto object-contain hidden dark:block"
              />
            </div>

            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon-xs"
                  onClick={onToggleCollapse}
                  className="ml-auto shrink-0 text-muted-foreground hover:text-foreground cursor-pointer"
                >
                  <PanelLeftClose className="size-3.5" />
                  <span className="sr-only">Collapse sidebar (⌘B)</span>
                </Button>
              </TooltipTrigger>
              <TooltipContent side="right">Collapse sidebar (⌘B)</TooltipContent>
            </Tooltip>
          </div>

          {/* Action Controls: New Chat + Search */}
          <div className="p-3 space-y-2">
            <Button
              variant="outline"
              onClick={() => void handleNewChat()}
              className="w-full justify-start gap-2.5 rounded-xl border border-border/80 bg-card text-foreground shadow-2xs hover:bg-muted/70 hover:text-foreground cursor-pointer h-9 px-3 text-xs font-medium transition-colors"
            >
              <Plus className="size-4 text-muted-foreground" />
              <span>New Research Thread</span>
            </Button>

            {/* Thread Search Filter */}
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search conversations..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="h-8 w-full rounded-xl border border-border/70 bg-card/60 pl-8 pr-3 text-xs text-foreground placeholder:text-muted-foreground/60 transition-colors focus:border-foreground/30 focus:bg-card focus:outline-none"
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => setSearchQuery("")}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground cursor-pointer"
                >
                  <X className="size-3" />
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Chronological + Pinned Thread List */}
        <ScrollArea className="flex-1 px-3 w-full min-w-0">
          {loading ? (
            <div className="space-y-2 py-4">
              <div className="h-8 animate-pulse rounded-lg bg-muted/60" />
              <div className="h-8 animate-pulse rounded-lg bg-muted/40" />
              <div className="h-8 animate-pulse rounded-lg bg-muted/20" />
            </div>
          ) : filteredThreads.length === 0 ? (
            <div className="py-8 text-center text-xs text-muted-foreground">
              {searchQuery ? "No matching conversations" : "No conversations yet"}
            </div>
          ) : (
            <div className="space-y-4 py-1">
              {/* Pinned Threads Group */}
              {pinnedThreads.length > 0 && (
                <div>
                  <div className="flex items-center gap-1.5 px-2 pb-1 text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">
                    <Pin className="size-2.5 fill-current opacity-70" />
                    <span>Pinned</span>
                  </div>
                  <div className="space-y-0.5">
                    {pinnedThreads.map((t) => renderThreadItem(t))}
                  </div>
                </div>
              )}

              {/* Today Group */}
              {todayThreads.length > 0 && (
                <div>
                  <p className="px-2 pb-1 text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">
                    Today
                  </p>
                  <div className="space-y-0.5">
                    {todayThreads.map((t) => renderThreadItem(t))}
                  </div>
                </div>
              )}

              {/* Previous 7 Days Group */}
              {weekThreads.length > 0 && (
                <div>
                  <p className="px-2 pb-1 text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">
                    Previous 7 Days
                  </p>
                  <div className="space-y-0.5">
                    {weekThreads.map((t) => renderThreadItem(t))}
                  </div>
                </div>
              )}

              {/* Older Group */}
              {olderThreads.length > 0 && (
                <div>
                  <p className="px-2 pb-1 text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">
                    Older Filings
                  </p>
                  <div className="space-y-0.5">
                    {olderThreads.map((t) => renderThreadItem(t))}
                  </div>
                </div>
              )}
            </div>
          )}
        </ScrollArea>

        {/* Archived Conversations Link & User Footer */}
        <div className="border-t border-border/80 bg-sidebar p-3 space-y-2">
          {archivedThreads.length > 0 && (
            <button
              type="button"
              onClick={() => {
                void handleRefreshArchived()
                setShowArchivedDialog(true)
              }}
              className="flex w-full items-center justify-between rounded-xl border border-border/60 bg-card/40 px-2.5 py-1.5 text-xs text-muted-foreground transition-colors hover:bg-card hover:text-foreground cursor-pointer"
            >
              <div className="flex items-center gap-2">
                <FolderArchive className="size-3.5" />
                <span>Archived Chats</span>
              </div>
              <Badge variant="muted" className="h-4 px-1.5 font-mono text-[9px]">
                {archivedThreads.length}
              </Badge>
            </button>
          )}

          {/* Analyst Profile Dropdown */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button
                type="button"
                className="flex w-full items-center justify-between rounded-xl border border-border/70 bg-card/70 p-2 text-left shadow-2xs transition-colors hover:bg-card hover:border-border cursor-pointer outline-none"
              >
                <div className="flex min-w-0 items-center gap-2.5">
                  <Avatar className="size-7">
                    <AvatarFallback className="text-[10px] bg-primary/10 text-primary">
                      {userInitials}
                    </AvatarFallback>
                  </Avatar>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-semibold text-foreground">
                      {user?.email}
                    </p>
                    <p className="text-[10px] text-muted-foreground">
                      Equity Research Analyst
                    </p>
                  </div>
                </div>
                <MoreHorizontal className="size-3.5 text-muted-foreground" />
              </button>
            </DropdownMenuTrigger>

            <DropdownMenuContent
              side="top"
              align="center"
              sideOffset={8}
              className="w-56 mb-1 rounded-2xl border border-zinc-200 bg-white p-1.5 text-zinc-900 shadow-xl dark:border-[#333333] dark:bg-[#212121] dark:text-[#ececec] dark:shadow-2xl dark:shadow-black/80"
            >
              <DropdownMenuLabel>
                <span className="block text-xs font-semibold text-foreground truncate">
                  {user?.email}
                </span>
                <span className="block text-[10px] text-muted-foreground font-normal">
                  Internal Analyst Account
                </span>
              </DropdownMenuLabel>
              <DropdownMenuSeparator className="my-1 -mx-1 h-px bg-zinc-200 dark:bg-[#333333]" />
              <DropdownMenuItem
                onClick={() => void signOut()}
                className="cursor-pointer gap-2.5 rounded-xl px-2.5 py-2 text-xs font-medium text-red-600 hover:bg-red-500/10 dark:text-[#ef4444] dark:hover:bg-red-500/15 dark:hover:text-[#f87171]"
              >
                <LogOut className="size-3.5" />
                <span>Log out</span>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </aside>

      {/* Archived Conversations Modal */}
      <Dialog open={showArchivedDialog} onOpenChange={setShowArchivedDialog}>
        <DialogContent className="max-w-md rounded-2xl p-5">
          <DialogHeader>
            <div className="flex items-center gap-2">
              <FolderArchive className="size-4 text-primary" />
              <DialogTitle className="text-sm font-semibold">
                Archived Conversations
              </DialogTitle>
            </div>
            <DialogDescription className="text-xs">
              Discussions here are removed from your active sidebar. You can
              restore or permanently delete them at any time.
            </DialogDescription>
          </DialogHeader>

          <div className="max-h-72 overflow-y-auto space-y-1.5 my-2 pr-1">
            {loadingArchived ? (
              <div className="py-6 text-center text-xs text-muted-foreground animate-pulse">
                Loading archives...
              </div>
            ) : archivedThreads.length === 0 ? (
              <div className="py-6 text-center text-xs text-muted-foreground">
                No archived conversations found.
              </div>
            ) : (
              archivedThreads.map((thread) => (
                <div
                  key={thread.id}
                  className="flex items-center justify-between gap-2 rounded-xl border border-border/70 bg-card/60 p-2 text-xs transition-colors hover:bg-card"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium text-foreground">
                      {thread.title || "Untitled Analysis"}
                    </p>
                    <p className="text-[10px] text-muted-foreground">
                      {new Date(thread.created_at || thread.updated_at).toLocaleDateString()}
                    </p>
                  </div>
                  <div className="flex items-center gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={(e) => void handleToggleArchive(e, thread)}
                      className="h-7 gap-1 px-2 text-[11px] hover:bg-accent"
                      title="Restore to active conversations"
                    >
                      <ArchiveRestore className="size-3" />
                      <span>Restore</span>
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={(e) => handleRequestDelete(e, thread)}
                      className="h-7 px-2 text-[11px] text-destructive hover:bg-destructive/10"
                      title="Delete permanently"
                    >
                      <Trash2 className="size-3" />
                    </Button>
                  </div>
                </div>
              ))
            )}
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowArchivedDialog(false)}
              className="w-full sm:w-auto text-xs"
            >
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Modal (Big Tech Pattern: Ask Every Time vs Never Ask Again) */}
      <Dialog
        open={!!threadPendingDelete}
        onOpenChange={(open) => {
          if (!open) setThreadPendingDelete(null)
        }}
      >
        <DialogContent className="max-w-sm rounded-2xl p-5 border border-zinc-200 bg-white text-zinc-900 shadow-2xl dark:border-[#333333] dark:bg-[#1f1f1f] dark:text-[#ececec]">
          <DialogHeader className="gap-1.5">
            <div className="flex items-center gap-2">
              <div className="flex size-8 shrink-0 items-center justify-center rounded-xl bg-red-500/10 text-red-600 dark:text-red-400">
                <Trash2 className="size-4" />
              </div>
              <DialogTitle className="text-sm font-semibold">
                Delete conversation?
              </DialogTitle>
            </div>
            <DialogDescription className="text-xs text-muted-foreground pt-1 leading-relaxed">
              Are you sure you want to delete{" "}
              <span className="font-semibold text-foreground">
                "{threadPendingDelete?.title || "Untitled Analysis"}"
              </span>
              ? This conversation and its verified citations will be permanently removed.
            </DialogDescription>
          </DialogHeader>

          {/* "Don't ask me again" Checkbox */}
          <div className="my-2 rounded-xl border border-border/60 bg-muted/30 p-2.5 transition-colors hover:bg-muted/50">
            <label className="flex items-center gap-2.5 text-xs text-muted-foreground cursor-pointer select-none">
              <input
                type="checkbox"
                checked={dontAskAgainDelete}
                onChange={(e) => setDontAskAgainDelete(e.target.checked)}
                className="size-4 rounded border-border accent-primary cursor-pointer"
              />
              <span className="font-medium text-foreground text-[11.5px]">
                Don't ask me again on this device
              </span>
            </label>
          </div>

          <DialogFooter className="flex items-center gap-2 sm:justify-end pt-1">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setThreadPendingDelete(null)}
              className="text-xs rounded-xl"
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => {
                if (!threadPendingDelete) return
                const targetId = threadPendingDelete.id

                if (dontAskAgainDelete) {
                  localStorage.setItem("meridian_skip_delete_confirm", "true")
                  setSkipDeleteConfirm(true)
                }

                setThreadPendingDelete(null)
                void executeOptimisticDelete(targetId)
              }}
              className="text-xs rounded-xl bg-red-600 hover:bg-red-700 text-white font-medium"
            >
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )

  // ---------------------------------------------------------------------------
  // Sub-renderer for individual thread row
  // ---------------------------------------------------------------------------
  function renderThreadItem(thread: Thread) {
    const isActive = thread.id === effectiveActiveThreadId
    const isEditing = thread.id === editingThreadId

    if (isEditing) {
      return (
        <div
          key={thread.id}
          className="flex items-center gap-1.5 rounded-lg border border-primary/40 bg-card p-1.5 shadow-2xs"
        >
          <input
            type="text"
            value={editTitle}
            onChange={(e) => setEditTitle(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") void handleSaveRename(e, thread.id)
              if (e.key === "Escape") handleCancelRename()
            }}
            autoFocus
            disabled={savingEdit}
            className="min-w-0 flex-1 bg-transparent px-1.5 text-xs text-foreground outline-none"
          />
          <button
            type="button"
            onClick={(e) => void handleSaveRename(e, thread.id)}
            disabled={savingEdit || !editTitle.trim()}
            className="rounded p-1 text-muted-foreground hover:text-foreground cursor-pointer"
            title="Save"
          >
            <Check className="size-3 text-emerald-500" />
          </button>
          <button
            type="button"
            onClick={handleCancelRename}
            disabled={savingEdit}
            className="rounded p-1 text-muted-foreground hover:text-foreground cursor-pointer"
            title="Cancel"
          >
            <X className="size-3" />
          </button>
        </div>
      )
    }

    return (
      <div
        key={thread.id}
        className={cn(
          "group relative flex items-center justify-between gap-1.5 rounded-lg px-2.5 py-1.5 text-xs transition-colors w-full min-w-0 overflow-hidden",
          isActive
            ? "bg-accent font-medium text-accent-foreground shadow-2xs"
            : "text-muted-foreground hover:bg-muted/70 hover:text-foreground"
        )}
      >
        <Link
          to={`/chat/${thread.id}`}
          className="flex min-w-0 flex-1 items-center gap-2 overflow-hidden"
        >
          <MessageSquare
            className={cn(
              "size-3.5 shrink-0 transition-colors",
              isActive ? "text-primary" : "opacity-60 group-hover:opacity-100"
            )}
          />
          <span className="truncate min-w-0 flex-1 block">
            {thread.title || "Untitled Analysis"}
          </span>
        </Link>

        {/* Right-hand Action Area: 3 dots menu and active white dot */}
        <div className="flex shrink-0 items-center gap-1 ml-auto pl-1">
          <div className="relative flex size-6 shrink-0 items-center justify-center">
            {/* Thread Actions Dropdown Menu (Glitch-free popper anchor with solid charcoal styling) */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation()
                  }}
                  className={cn(
                    "flex size-6 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-opacity hover:bg-muted hover:text-foreground cursor-pointer outline-none",
                    // Visible on group hover, when menu is open, or on focus
                    "opacity-0 group-hover:opacity-100 data-[state=open]:opacity-100 focus:opacity-100"
                  )}
                  title="Thread options"
                >
                  <MoreHorizontal className="size-3.5" />
                </button>
              </DropdownMenuTrigger>

              <DropdownMenuContent
                side="bottom"
                align="end"
                sideOffset={6}
                className="w-48 rounded-2xl border border-zinc-200 bg-white p-1.5 text-zinc-900 shadow-xl dark:border-[#333333] dark:bg-[#212121] dark:text-[#ececec] dark:shadow-2xl dark:shadow-black/80"
              >
                <DropdownMenuItem
                  onClick={(e) => handleStartRename(e, thread)}
                  className="cursor-pointer gap-2.5 rounded-xl px-2.5 py-2 text-xs font-medium text-zinc-800 transition-colors hover:bg-zinc-100 hover:text-zinc-950 dark:text-[#ececec] dark:hover:bg-[#2c2c2c] dark:hover:text-white"
                >
                  <Pencil className="size-3.5 opacity-80" />
                  <span>Rename</span>
                </DropdownMenuItem>

                <DropdownMenuItem
                  onClick={(e) => void handleTogglePin(e, thread)}
                  className="cursor-pointer gap-2.5 rounded-xl px-2.5 py-2 text-xs font-medium text-zinc-800 transition-colors hover:bg-zinc-100 hover:text-zinc-950 dark:text-[#ececec] dark:hover:bg-[#2c2c2c] dark:hover:text-white"
                >
                  <Pin
                    className={cn(
                      "size-3.5 opacity-80",
                      thread.is_pinned && "fill-current text-primary"
                    )}
                  />
                  <span>{thread.is_pinned ? "Unpin" : "Pin"}</span>
                </DropdownMenuItem>

                <DropdownMenuSeparator className="my-1 -mx-1 h-px bg-zinc-200 dark:bg-[#333333]" />

                <DropdownMenuItem
                  onClick={(e) => void handleToggleArchive(e, thread)}
                  className="cursor-pointer gap-2.5 rounded-xl px-2.5 py-2 text-xs font-medium text-zinc-800 transition-colors hover:bg-zinc-100 hover:text-zinc-950 dark:text-[#ececec] dark:hover:bg-[#2c2c2c] dark:hover:text-white"
                >
                  <Archive className="size-3.5 opacity-80" />
                  <span>Archive</span>
                </DropdownMenuItem>

                <DropdownMenuItem
                  onClick={(e) => handleRequestDelete(e, thread)}
                  className="cursor-pointer gap-2.5 rounded-xl px-2.5 py-2 text-xs font-medium text-red-600 transition-colors hover:bg-red-500/10 hover:text-red-700 dark:text-[#ef4444] dark:hover:bg-red-500/15 dark:hover:text-[#f87171]"
                >
                  <Trash2 className="size-3.5" />
                  <span>Delete</span>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>

            {/* Active indicator white dot: centered in the 24px box, visible when active and not hovering */}
            {isActive && !isEditing && (
              <span className="pointer-events-none absolute size-1.5 rounded-full bg-primary transition-opacity group-hover:opacity-0" />
            )}
          </div>
        </div>
      </div>
    )
  }
}

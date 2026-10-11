import { useEffect, useState, type KeyboardEvent, type MouseEvent } from "react"
import { Building2, Check, LogOut, MessageSquare, Pencil, Plus, Trash2, X } from "lucide-react"
import { Link, useNavigate } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { createThread, deleteThread, listThreads, updateThread, type Thread } from "@/lib/api"
import { useAuth } from "@/lib/auth"
import { cn } from "@/lib/utils"

interface SidebarProps {
  activeThreadId?: string
}

export function Sidebar({ activeThreadId }: SidebarProps) {
  const [threads, setThreads] = useState<Thread[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [editingThreadId, setEditingThreadId] = useState<string | null>(null)
  const [editTitle, setEditTitle] = useState("")
  const [savingEdit, setSavingEdit] = useState(false)
  const [deletingThreadId, setDeletingThreadId] = useState<string | null>(null)

  const { user, signOut } = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    let isMounted = true
    listThreads()
      .then((data) => {
        if (isMounted) {
          setThreads(data)
          setLoading(false)
        }
      })
      .catch(() => {
        if (isMounted) {
          setLoading(false)
        }
      })

    return () => {
      isMounted = false
    }
  }, [activeThreadId])

  async function handleNewChat() {
    if (creating) return
    setCreating(true)
    try {
      const newThread = await createThread()
      setThreads((prev) => [newThread, ...prev])
      navigate(`/chat/${newThread.id}`)
    } catch (err) {
      console.error("Failed to create thread", err)
    } finally {
      setCreating(false)
    }
  }

  function handleStartRename(e: MouseEvent, thread: Thread) {
    e.preventDefault()
    e.stopPropagation()
    setEditingThreadId(thread.id)
    setEditTitle(thread.title || "Untitled Analysis")
  }

  function handleCancelRename(e?: MouseEvent) {
    if (e) {
      e.preventDefault()
      e.stopPropagation()
    }
    setEditingThreadId(null)
    setEditTitle("")
  }

  async function handleSaveRename(e?: MouseEvent | KeyboardEvent, threadId?: string) {
    if (e) {
      e.preventDefault()
      e.stopPropagation()
    }
    const targetId = threadId || editingThreadId
    const trimmed = editTitle.trim()
    if (!targetId || !trimmed || savingEdit) return

    setSavingEdit(true)
    try {
      const updated = await updateThread(targetId, trimmed)
      setThreads((prev) =>
        prev.map((t) => (t.id === targetId ? { ...t, title: updated.title } : t))
      )
      setEditingThreadId(null)
      setEditTitle("")
    } catch (err) {
      console.error("Failed to rename thread", err)
    } finally {
      setSavingEdit(false)
    }
  }

  async function handleDeleteThread(e: MouseEvent, threadId: string) {
    e.preventDefault()
    e.stopPropagation()
    if (deletingThreadId) return

    const confirmed = window.confirm("Are you sure you want to delete this research thread?")
    if (!confirmed) return

    setDeletingThreadId(threadId)
    try {
      await deleteThread(threadId)
      setThreads((prev) => prev.filter((t) => t.id !== threadId))
      if (activeThreadId === threadId) {
        navigate("/", { replace: true })
      }
    } catch (err) {
      console.error("Failed to delete thread", err)
    } finally {
      setDeletingThreadId(null)
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>, threadId: string) {
    if (e.key === "Enter") {
      void handleSaveRename(e, threadId)
    } else if (e.key === "Escape") {
      handleCancelRename()
    }
  }

  const userInitials = (user?.email?.slice(0, 2) || "AN").toUpperCase()

  return (
    <aside className="flex h-screen w-68 shrink-0 flex-col border-r border-border/80 bg-sidebar text-sidebar-foreground">
      {/* Brand Header */}
      <div className="flex h-14 items-center justify-between border-b border-border/80 px-4">
        <Link to="/" className="flex items-center gap-2.5 font-medium">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-foreground text-background shadow-xs">
            <Building2 className="h-4 w-4" />
          </div>
          <div className="flex flex-col">
            <span className="text-xs font-semibold leading-tight text-foreground">
              Document Assistant
            </span>
            <span className="text-[10px] text-muted-foreground">
              SEC Analyst Workspace
            </span>
          </div>
        </Link>
      </div>

      {/* New Conversation Button */}
      <div className="p-3">
        <Button
          onClick={() => void handleNewChat()}
          disabled={creating}
          variant="outline"
          className="w-full justify-between rounded-xl border border-border bg-card/80 px-3 py-2 text-xs font-medium shadow-2xs hover:bg-accent hover:text-accent-foreground"
        >
          <div className="flex items-center gap-2">
            <Plus className="h-3.5 w-3.5 text-muted-foreground" />
            <span>{creating ? "Creating..." : "New Research Thread"}</span>
          </div>
          <kbd className="rounded border border-border/60 bg-muted px-1.5 py-0.5 font-mono text-[9px] text-muted-foreground">
            ⌘N
          </kbd>
        </Button>
      </div>

      {/* Conversations List */}
      <div className="flex-1 overflow-y-auto px-2.5 py-1">
        <div className="flex items-center justify-between px-2 pb-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/80">
          <span>Recent Filings</span>
          <span className="font-mono text-[9px]">{threads.length}</span>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-10 text-xs text-muted-foreground">
            <div className="flex items-center gap-2">
              <span className="h-1.5 w-1.5 animate-ping rounded-full bg-primary" />
              <span>Loading threads...</span>
            </div>
          </div>
        ) : threads.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border/70 p-4 text-center">
            <p className="text-xs font-medium text-foreground">No conversations</p>
            <p className="mt-1 text-[11px] text-muted-foreground">
              Start a new thread to begin asking questions.
            </p>
          </div>
        ) : (
          <div className="space-y-1">
            {threads.map((thread) => {
              const isActive = thread.id === activeThreadId
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
                      onKeyDown={(e) => handleKeyDown(e, thread.id)}
                      autoFocus
                      disabled={savingEdit}
                      className="min-w-0 flex-1 bg-transparent px-1.5 text-xs text-foreground outline-none"
                    />
                    <button
                      type="button"
                      onClick={(e) => void handleSaveRename(e, thread.id)}
                      disabled={savingEdit || !editTitle.trim()}
                      className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-40"
                      title="Save (Enter)"
                    >
                      <Check className="h-3 w-3 text-emerald-600 dark:text-emerald-400" />
                    </button>
                    <button
                      type="button"
                      onClick={handleCancelRename}
                      disabled={savingEdit}
                      className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                      title="Cancel (Esc)"
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </div>
                )
              }

              return (
                <div
                  key={thread.id}
                  className={cn(
                    "group relative flex items-center gap-2 rounded-lg px-2.5 py-2 text-xs transition-colors",
                    isActive
                      ? "bg-accent font-medium text-accent-foreground shadow-2xs"
                      : "text-muted-foreground hover:bg-muted/70 hover:text-foreground"
                  )}
                >
                  <Link
                    to={`/chat/${thread.id}`}
                    className="flex min-w-0 flex-1 items-center gap-2"
                  >
                    <MessageSquare
                      className={cn(
                        "h-3.5 w-3.5 shrink-0 transition-colors",
                        isActive ? "text-primary" : "opacity-60 group-hover:opacity-100"
                      )}
                    />
                    <span className="truncate">
                      {thread.title || "Untitled Analysis"}
                    </span>
                  </Link>

                  {/* Thread Action Buttons (Rename & Delete) */}
                  <div className="hidden items-center gap-0.5 group-hover:flex">
                    <button
                      type="button"
                      onClick={(e) => handleStartRename(e, thread)}
                      className="rounded p-1 text-muted-foreground opacity-70 transition-opacity hover:bg-muted hover:text-foreground hover:opacity-100"
                      title="Rename thread"
                    >
                      <Pencil className="h-3 w-3" />
                      <span className="sr-only">Rename</span>
                    </button>
                    <button
                      type="button"
                      onClick={(e) => void handleDeleteThread(e, thread.id)}
                      disabled={deletingThreadId === thread.id}
                      className="rounded p-1 text-muted-foreground opacity-70 transition-opacity hover:bg-destructive/10 hover:text-destructive hover:opacity-100 disabled:opacity-40"
                      title="Delete thread"
                    >
                      <Trash2 className="h-3 w-3" />
                      <span className="sr-only">Delete</span>
                    </button>
                  </div>

                  {isActive && !isEditing && (
                    <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-primary group-hover:hidden" />
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Analyst Profile Footer */}
      <div className="border-t border-border/80 bg-sidebar p-3">
        <div className="flex items-center justify-between rounded-xl border border-border/60 bg-card/60 p-2 shadow-2xs">
          <div className="flex min-w-0 items-center gap-2.5">
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-primary/10 font-mono text-[11px] font-semibold text-primary">
              {userInitials}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-xs font-medium leading-tight text-foreground">
                {user?.email}
              </p>
              <p className="text-[10px] text-muted-foreground">
                Research Analyst
              </p>
            </div>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => void signOut()}
            className="h-7 w-7 shrink-0 p-0 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
            title="Sign out"
          >
            <LogOut className="h-3.5 w-3.5" />
            <span className="sr-only">Sign out</span>
          </Button>
        </div>
      </div>
    </aside>
  )
}

import { useEffect, useState } from "react"
import { Outlet, useParams } from "react-router-dom"
import { Sidebar } from "@/components/chat/Sidebar"

export interface ChatLayoutContext {
  isSidebarCollapsed: boolean
  toggleSidebar: () => void
}

export function ChatLayout() {
  const { threadId } = useParams<{ threadId?: string }>()
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(() => {
    if (typeof window !== "undefined") {
      return localStorage.getItem("sidebar_collapsed") === "true"
    }
    return false
  })

  function toggleSidebar() {
    setIsSidebarCollapsed((prev) => {
      const next = !prev
      localStorage.setItem("sidebar_collapsed", String(next))
      return next
    })
  }

  // Keyboard shortcut: Cmd + B to toggle sidebar
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "b") {
        e.preventDefault()
        toggleSidebar()
      }
    }
    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [])

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background">
      <Sidebar
        activeThreadId={threadId}
        isCollapsed={isSidebarCollapsed}
        onToggleCollapse={toggleSidebar}
      />
      <main className="flex flex-1 overflow-hidden">
        <Outlet context={{ isSidebarCollapsed, toggleSidebar } satisfies ChatLayoutContext} />
      </main>
    </div>
  )
}

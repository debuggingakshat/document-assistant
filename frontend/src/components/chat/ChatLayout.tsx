import { Outlet, useParams } from "react-router-dom"
import { Sidebar } from "@/components/chat/Sidebar"

export function ChatLayout() {
  const { threadId } = useParams<{ threadId?: string }>()

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background">
      <Sidebar activeThreadId={threadId} />
      <main className="flex flex-1 overflow-hidden">
        <Outlet />
      </main>
    </div>
  )
}

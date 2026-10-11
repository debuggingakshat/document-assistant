import { Navigate, useParams } from "react-router-dom"
import { ChatArea } from "@/components/chat/ChatArea"

export function ChatPage() {
  const { threadId } = useParams<{ threadId: string }>()

  if (!threadId) {
    return <Navigate to="/" replace />
  }

  return <ChatArea threadId={threadId} />
}

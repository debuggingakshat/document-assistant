import { useParams } from "react-router-dom"
import { ChatArea } from "@/components/chat/ChatArea"

export function ChatPage() {
  const { threadId } = useParams<{ threadId?: string }>()

  return <ChatArea threadId={threadId} />
}

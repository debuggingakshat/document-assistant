import { useEffect, useState } from "react"
import { useParams } from "react-router-dom"
import { ChatArea } from "@/components/chat/ChatArea"

export function ChatPage() {
  const { threadId } = useParams<{ threadId?: string }>()
  const [draftSessionId, setDraftSessionId] = useState<number>(() => Date.now())

  // Force atomic remount of ChatArea whenever an explicit new draft session is triggered
  useEffect(() => {
    function handleDraftReset() {
      setDraftSessionId(Date.now())
    }
    window.addEventListener("meridian_reset_to_draft", handleDraftReset)
    return () => window.removeEventListener("meridian_reset_to_draft", handleDraftReset)
  }, [])

  // Explicit key guarantees React wipes all turn/stream state upon new thread creation
  const areaKey = threadId ? `thread-${threadId}` : `draft-${draftSessionId}`

  return <ChatArea key={areaKey} threadId={threadId} />
}

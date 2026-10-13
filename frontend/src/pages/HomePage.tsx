import { useEffect, useState } from "react"
import { Plus } from "lucide-react"
import { useNavigate } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { createThread, listThreads } from "@/lib/api"

export function HomePage() {
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    let isMounted = true

    listThreads()
      .then((threads) => {
        if (!isMounted) return
        if (threads.length > 0) {
          navigate(`/chat/${threads[0].id}`, { replace: true })
        } else {
          setLoading(false)
        }
      })
      .catch(() => {
        if (isMounted) setLoading(false)
      })

    return () => {
      isMounted = false
    }
  }, [navigate])

  async function handleStartNew() {
    setCreating(true)
    try {
      const newThread = await createThread()
      navigate(`/chat/${newThread.id}`)
    } catch (err) {
      console.error("Failed to create thread", err)
      setCreating(false)
    }
  }

  if (loading) {
    return (
      <div className="flex flex-1 items-center justify-center text-xs text-muted-foreground">
        Loading workspace...
      </div>
    )
  }

  return (
    <div className="flex flex-1 flex-col items-center justify-center p-8 text-center bg-background select-none">
      <div className="flex items-center justify-center">
        <img
          src="/meridian-logo-light.png"
          alt="Meridian Research"
          className="h-12 w-auto object-contain dark:hidden"
        />
        <img
          src="/meridian-logo-dark.png"
          alt="Meridian Research"
          className="h-12 w-auto object-contain hidden dark:block"
        />
      </div>
      <h1 className="mt-3 text-base font-semibold tracking-wide text-foreground">
        Document Assistant
      </h1>
      <p className="mt-1.5 max-w-sm text-xs text-muted-foreground">
        Your AI research partner for financial disclosures and SEC filings.
        Start a new conversation to begin analyzing 10-K and 10-Q reports.
      </p>

      <Button
        onClick={() => void handleStartNew()}
        disabled={creating}
        className="mt-6 gap-2"
      >
        <Plus className="h-4 w-4" />
        <span>{creating ? "Creating conversation..." : "Start New Analysis"}</span>
      </Button>
    </div>
  )
}

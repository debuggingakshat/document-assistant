import { useState, type FormEvent } from "react"
import { Building2 } from "lucide-react"
import { Link, useLocation, useNavigate } from "react-router-dom"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useAuth } from "@/lib/auth"
import { supabase } from "@/lib/supabase"

export function LoginPage() {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const { user } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  if (user) {
    const from = (location.state as { from?: { pathname?: string } })?.from?.pathname || "/"
    navigate(from, { replace: true })
    return null
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)

    try {
      const { error: signInError } = await supabase.auth.signInWithPassword({
        email,
        password,
      })

      if (signInError) {
        setError(signInError.message)
        return
      }

      const from = (location.state as { from?: { pathname?: string } })?.from?.pathname || "/"
      navigate(from, { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to sign in")
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-screen w-full items-center justify-center bg-background px-4">
      <Card className="w-full max-w-sm rounded-2xl border border-border/80 bg-card shadow-sm">
        <CardHeader className="space-y-3 pb-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-foreground text-background shadow-xs">
            <Building2 className="h-5 w-5" />
          </div>
          <div>
            <CardTitle className="text-lg font-semibold tracking-tight text-foreground">
              Sign in to Document Assistant
            </CardTitle>
            <CardDescription className="text-xs text-muted-foreground mt-0.5">
              SEC filing research & analysis platform for analysts
            </CardDescription>
          </div>
        </CardHeader>
        <form onSubmit={handleSubmit}>
          <CardContent className="space-y-4">
            {error && (
              <div className="rounded-xl border border-destructive/20 bg-destructive/10 p-3 text-xs text-destructive">
                {error}
              </div>
            )}
            <div className="space-y-1.5">
              <Label htmlFor="email" className="text-xs font-medium">Email address</Label>
              <Input
                id="email"
                type="email"
                placeholder="analyst@meridianresearch.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
                disabled={submitting}
                className="h-9 rounded-lg text-sm"
              />
            </div>
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <Label htmlFor="password" className="text-xs font-medium">Password</Label>
              </div>
              <Input
                id="password"
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
                disabled={submitting}
                className="h-9 rounded-lg text-sm"
              />
            </div>
          </CardContent>
          <CardFooter className="flex flex-col gap-3 pt-2">
            <Button
              type="submit"
              className="w-full h-9 rounded-lg font-medium text-xs shadow-xs"
              disabled={submitting}
            >
              {submitting ? "Authenticating..." : "Sign in to workspace"}
            </Button>
            <p className="text-center text-xs text-muted-foreground">
              Don&apos;t have an account?{" "}
              <Link
                to="/signup"
                className="font-medium text-foreground underline underline-offset-4 hover:text-primary"
              >
                Create one
              </Link>
            </p>
          </CardFooter>
        </form>
      </Card>
    </div>
  )
}

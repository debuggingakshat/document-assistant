import { useState, type FormEvent } from "react"
import { Building2 } from "lucide-react"
import { Link, useNavigate } from "react-router-dom"
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

export function SignUpPage() {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const { user } = useAuth()
  const navigate = useNavigate()

  if (user) {
    navigate("/", { replace: true })
    return null
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSuccessMessage(null)

    if (password !== confirmPassword) {
      setError("Passwords do not match")
      return
    }

    if (password.length < 6) {
      setError("Password must be at least 6 characters")
      return
    }

    setSubmitting(true)

    try {
      const { data, error: signUpError } = await supabase.auth.signUp({
        email,
        password,
      })

      if (signUpError) {
        setError(signUpError.message)
        return
      }

      if (data.session) {
        navigate("/", { replace: true })
      } else {
        setSuccessMessage(
          "Account created! Please check your email to confirm your account before signing in."
        )
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to sign up")
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
              Create Analyst Account
            </CardTitle>
            <CardDescription className="text-xs text-muted-foreground mt-0.5">
              Access the Document Assistant financial research workspace
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
            {successMessage && (
              <div className="rounded-xl border border-primary/20 bg-primary/10 p-3 text-xs text-foreground">
                {successMessage}
              </div>
            )}
            <div className="space-y-1.5">
              <Label htmlFor="email" className="text-xs font-medium">Work email</Label>
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
              <Label htmlFor="password" className="text-xs font-medium">Password</Label>
              <Input
                id="password"
                type="password"
                placeholder="At least 6 characters"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="new-password"
                disabled={submitting}
                className="h-9 rounded-lg text-sm"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="confirm-password" className="text-xs font-medium">Confirm password</Label>
              <Input
                id="confirm-password"
                type="password"
                placeholder="••••••••"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                autoComplete="new-password"
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
              {submitting ? "Creating account..." : "Register account"}
            </Button>
            <p className="text-center text-xs text-muted-foreground">
              Already have an account?{" "}
              <Link
                to="/login"
                className="font-medium text-foreground underline underline-offset-4 hover:text-primary"
              >
                Sign in
              </Link>
            </p>
          </CardFooter>
        </form>
      </Card>
    </div>
  )
}

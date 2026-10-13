/**
 * Utilities for formatting message dates and timestamps.
 */

export function formatMessageTime(isoString?: string): string {
  if (!isoString) return ""
  try {
    const d = new Date(isoString)
    if (isNaN(d.getTime())) return ""
    return d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })
  } catch {
    return ""
  }
}

export function formatMessageDate(isoString?: string): string {
  if (!isoString) return ""
  try {
    const d = new Date(isoString)
    if (isNaN(d.getTime())) return ""
    const now = new Date()

    // Same day check
    if (
      d.getDate() === now.getDate() &&
      d.getMonth() === now.getMonth() &&
      d.getFullYear() === now.getFullYear()
    ) {
      return "Today"
    }

    // Yesterday check
    const yesterday = new Date()
    yesterday.setDate(now.getDate() - 1)
    if (
      d.getDate() === yesterday.getDate() &&
      d.getMonth() === yesterday.getMonth() &&
      d.getFullYear() === yesterday.getFullYear()
    ) {
      return "Yesterday"
    }

    // Same year check
    if (d.getFullYear() === now.getFullYear()) {
      return d.toLocaleDateString([], {
        weekday: "short",
        month: "short",
        day: "numeric",
      })
    }

    return d.toLocaleDateString([], {
      weekday: "short",
      month: "short",
      day: "numeric",
      year: "numeric",
    })
  } catch {
    return ""
  }
}

export function formatFullDateTime(isoString?: string): string {
  if (!isoString) return ""
  try {
    const d = new Date(isoString)
    if (isNaN(d.getTime())) return ""
    return d.toLocaleString([], {
      weekday: "long",
      month: "long",
      day: "numeric",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
      second: "2-digit",
    })
  } catch {
    return ""
  }
}

export function isDifferentDay(dateStr1?: string, dateStr2?: string): boolean {
  if (!dateStr1 || !dateStr2) return false
  try {
    const d1 = new Date(dateStr1)
    const d2 = new Date(dateStr2)
    return (
      d1.getFullYear() !== d2.getFullYear() ||
      d1.getMonth() !== d2.getMonth() ||
      d1.getDate() !== d2.getDate()
    )
  } catch {
    return false
  }
}

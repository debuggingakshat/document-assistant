import React, { useMemo, useState } from "react"
import { Check, Copy, FileSpreadsheet } from "lucide-react"
import { cn } from "@/lib/utils"

interface FinancialTableProps {
  rawMarkdownTable: string
  renderInlineFormatted: (text: string) => React.ReactNode
  tableIndex?: number
}

interface ParsedTable {
  headers: string[]
  alignments: Array<"left" | "center" | "right">
  rows: string[][]
}

export function FinancialTable({
  rawMarkdownTable,
  renderInlineFormatted,
  tableIndex = 1,
}: FinancialTableProps) {
  const [copied, setCopied] = useState(false)

  const parsed = useMemo<ParsedTable | null>(() => {
    const lines = rawMarkdownTable
      .trim()
      .split("\n")
      .map((l) => l.trim())
      .filter((l) => l.length > 0)

    if (lines.length < 2) return null

    const headerLine = lines[0]
    const sepLine = lines[1]
    const dataLines = lines.slice(2)

    // Split by pipe and remove edge empty parts
    const splitRow = (rowStr: string) => {
      const trimmed = rowStr.replace(/^\|/, "").replace(/\|$/, "")
      return trimmed.split("|").map((c) => c.trim())
    }

    const headers = splitRow(headerLine)
    const seps = splitRow(sepLine)

    const alignments: Array<"left" | "center" | "right"> = seps.map((s) => {
      const hasLeftColon = s.startsWith(":")
      const hasRightColon = s.endsWith(":")
      if (hasLeftColon && hasRightColon) return "center"
      if (hasRightColon) return "right"
      return "left"
    })

    const rows: string[][] = []
    for (const dl of dataLines) {
      // Skip lines that look like separator duplicates
      if (/^[\s:|-]+$/.test(dl.replace(/\|/g, ""))) continue
      const cells = splitRow(dl)
      // Pad or truncate to match headers length
      while (cells.length < headers.length) {
        cells.push("")
      }
      rows.push(cells.slice(0, headers.length))
    }

    return { headers, alignments, rows }
  }, [rawMarkdownTable])

  if (!parsed || parsed.headers.length === 0) {
    return (
      <pre className="my-2 overflow-x-auto rounded-lg bg-muted p-3 font-mono text-xs">
        {rawMarkdownTable}
      </pre>
    )
  }

  const { headers, alignments, rows } = parsed

  // Copy table as clean TSV (Tab-Separated Values) for direct paste into Excel / Sheets
  async function handleCopyTable() {
    try {
      const headerRow = headers.join("\t")
      const dataRows = rows.map((r) => r.join("\t")).join("\n")
      const tsvContent = `${headerRow}\n${dataRows}`

      await navigator.clipboard.writeText(tsvContent)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Fallback if clipboard API is restricted
    }
  }

  // Detect numeric / currency / percentage content to apply tabular numbers font
  const isNumericValue = (val: string) => {
    const clean = val.replace(/\*\*/g, "").replace(/\*/g, "").trim()
    return /^[\+\-]?[\$€£¥]?\s*\d+(?:,\d{3})*(?:\.\d+)?%?$/.test(clean)
  }

  return (
    <div className="my-4 overflow-hidden rounded-xl border border-border/80 bg-card shadow-xs transition-all">
      {/* Top Table Utility Toolbar */}
      <div className="flex items-center justify-between border-b border-border/60 bg-muted/50 px-3.5 py-2 text-xs">
        <div className="flex items-center gap-2 text-muted-foreground">
          <FileSpreadsheet className="size-3.5 text-primary shrink-0" />
          <span className="font-semibold text-foreground text-[11.5px]">
            Financial Table {tableIndex > 1 ? `#${tableIndex}` : ""}
          </span>
          <span className="font-mono text-[10px] text-muted-foreground/80">
            ({rows.length} rows · {headers.length} cols)
          </span>
        </div>

        <button
          type="button"
          onClick={handleCopyTable}
          className="inline-flex items-center gap-1.5 rounded-md border border-border/70 bg-card px-2 py-1 text-[11px] font-medium text-muted-foreground transition-all hover:bg-muted hover:text-foreground cursor-pointer shadow-2xs"
          title="Copy table formatted for Excel or Google Sheets"
        >
          {copied ? (
            <>
              <Check className="size-3 text-emerald-500" />
              <span className="text-emerald-600 dark:text-emerald-400 font-medium">
                Copied TSV
              </span>
            </>
          ) : (
            <>
              <Copy className="size-3" />
              <span>Copy Table</span>
            </>
          )}
        </button>
      </div>

      {/* Horizontal Scroll Table Wrapper */}
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-border/70 text-left text-[12.5px] border-collapse">
          <thead>
            <tr className="bg-muted/70 divide-x divide-border/40">
              {headers.map((header, colIdx) => {
                const align = alignments[colIdx] || "left"
                const isFY = /FY\d{4}|Q[1-4]\s*\d{4}|\d{4}/i.test(header)

                return (
                  <th
                    key={colIdx}
                    scope="col"
                    className={cn(
                      "px-3.5 py-2.5 font-mono text-[11px] font-semibold text-foreground tracking-tight whitespace-nowrap",
                      align === "right" && "text-right",
                      align === "center" && "text-center",
                      align === "left" && "text-left"
                    )}
                  >
                    {isFY ? (
                      <span className="rounded bg-primary/10 text-primary px-1.5 py-0.5 font-bold">
                        {renderInlineFormatted(header)}
                      </span>
                    ) : (
                      renderInlineFormatted(header)
                    )}
                  </th>
                )
              })}
            </tr>
          </thead>

          <tbody className="divide-y divide-border/50">
            {rows.map((row, rowIdx) => {
              const firstCellClean = (row[0] || "").replace(/\*\*/g, "").toLowerCase()
              const isTotalRow =
                firstCellClean.includes("total") ||
                firstCellClean.includes("consolidated") ||
                firstCellClean.includes("net income") ||
                firstCellClean.includes("operating income")

              return (
                <tr
                  key={rowIdx}
                  className={cn(
                    "divide-x divide-border/30 transition-colors",
                    isTotalRow
                      ? "bg-muted/60 font-semibold border-t-2 border-border/80 text-foreground"
                      : "odd:bg-card even:bg-muted/15 hover:bg-muted/30"
                  )}
                >
                  {row.map((cell, colIdx) => {
                    const align = alignments[colIdx] || "left"
                    const isNum = isNumericValue(cell)

                    return (
                      <td
                        key={colIdx}
                        className={cn(
                          "px-3.5 py-2 whitespace-nowrap text-foreground/90",
                          isNum && "font-mono tabular-nums text-[12px]",
                          align === "right" && "text-right",
                          align === "center" && "text-center",
                          align === "left" && "text-left",
                          isTotalRow && "font-semibold text-foreground"
                        )}
                      >
                        {renderInlineFormatted(cell)}
                      </td>
                    )
                  })}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// Tremor Raw BarList (https://tremor.so/docs/visualizations/bar-list, Apache-2.0 copy-source), gold fill from the theme.
import * as React from "react"
import { cn } from "@/lib/utils"
export interface Bar { key?: string; name: string; value: number; sub?: string }
export function BarList({ data, className }: { data: Bar[]; className?: string }) {
  const max = Math.max(1, ...data.map(d => d.value))
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      {data.map(d => (
        <div key={d.key ?? d.name} className="flex items-center gap-3">
          <div className="relative h-8 flex-1 overflow-hidden rounded-md bg-muted/40">
            <div className="absolute inset-y-0 left-0 rounded-md bg-primary/25 transition-all duration-700" style={{ width: Math.max(2, (d.value / max) * 100) + "%" }} />
            <span className="relative z-10 flex h-full items-center px-3 text-sm capitalize text-foreground">{d.name}{d.sub && <span className="ml-2 text-xs text-muted-foreground">{d.sub}</span>}</span>
          </div>
          <span className="w-10 text-right font-serif text-xl tabular-nums text-primary">{d.value}</span>
        </div>))}
    </div>)
}

// Tremor Raw Tracker (https://tremor.so/docs/visualizations/tracker, Apache-2.0 copy-source), Tooltip swapped for the native title.
import * as React from "react"
import { cn } from "@/lib/utils"
export interface TrackerBlockProps { key?: string | number; color?: string; tooltip?: string; hoverEffect?: boolean; defaultBackgroundColor?: string }
export const Tracker = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement> & { data: TrackerBlockProps[] }>(({ data = [], className, ...p }, ref) => (
  <div ref={ref} className={cn("group flex h-10 w-full items-center gap-[3px]", className)} {...p}>
    {data.map((b, i) => <div key={b.key ?? i} title={b.tooltip} className="size-full min-w-1 flex-1 rounded-[3px] transition-opacity hover:opacity-70" style={{ background: b.color }} />)}
  </div>))
Tracker.displayName = "Tracker"

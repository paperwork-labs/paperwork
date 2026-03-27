import * as React from "react"
import {
  Area,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import { STAGE_HEX, type StageKey } from "@/constants/chart"
import { cn } from "@/lib/utils"

interface StageChartExampleProps {
  stage: StageKey
  className?: string
}

type DataPoint = {
  day: number
  price: number
  sma150: number
}

const generateStageData = (stage: StageKey): DataPoint[] => {
  const data: DataPoint[] = []
  const days = 60

  for (let i = 0; i < days; i++) {
    let price: number
    let sma150: number

    switch (stage) {
      case "1A":
        // Deep decline, price well below falling SMA150
        sma150 = 100 - i * 0.3
        price = sma150 - 15 + Math.sin(i * 0.3) * 3
        break
      case "1B":
        // Basing, price approaching SMA150 from below
        sma150 = 70 + i * 0.1
        price = 65 + i * 0.15 + Math.sin(i * 0.4) * 2
        break
      case "2A":
        // Breakout! Price crosses above SMA150 with momentum
        sma150 = 72 + i * 0.2
        price = 70 + i * 0.5 + Math.sin(i * 0.3) * 2
        break
      case "2B":
        // Confirmed uptrend, orderly advance
        sma150 = 80 + i * 0.3
        price = 85 + i * 0.35 + Math.sin(i * 0.25) * 3
        break
      case "2C":
        // Extended, price far above SMA150
        sma150 = 90 + i * 0.25
        price = 100 + i * 0.4 + Math.sin(i * 0.2) * 4
        break
      case "3A":
        // Topping, momentum slowing
        sma150 = 110 + i * 0.1
        price = 115 + Math.sin(i * 0.15) * 5 - i * 0.05
        break
      case "3B":
        // Distribution, price testing SMA150
        sma150 = 112 - i * 0.05
        price = 110 - i * 0.1 + Math.sin(i * 0.3) * 4
        break
      case "4A":
        // Breakdown begins, price below SMA150
        sma150 = 108 - i * 0.15
        price = 105 - i * 0.3 + Math.sin(i * 0.25) * 3
        break
      case "4B":
        // Confirmed downtrend
        sma150 = 100 - i * 0.25
        price = 95 - i * 0.4 + Math.sin(i * 0.2) * 2
        break
      case "4C":
        // Capitulation, steep decline
        sma150 = 90 - i * 0.35
        price = 80 - i * 0.6 + Math.sin(i * 0.15) * 3
        break
      default:
        sma150 = 100
        price = 100
    }

    data.push({
      day: i + 1,
      price: Math.max(price, 10),
      sma150: Math.max(sma150, 10),
    })
  }

  return data
}

const stageDescriptions: Record<StageKey, string> = {
  "1A": "Deep decline - Price well below falling SMA150",
  "1B": "Basing - Price consolidating, approaching SMA150",
  "2A": "Breakout - Price crosses above SMA150 with volume",
  "2B": "Confirmed advance - Orderly uptrend above SMA150",
  "2C": "Extended - Price stretched far above SMA150",
  "3A": "Topping - Momentum slowing, price near SMA150",
  "3B": "Distribution - Price testing SMA150 from above",
  "4A": "Breakdown - Price drops below SMA150",
  "4B": "Confirmed decline - Orderly downtrend below SMA150",
  "4C": "Capitulation - Steep decline, price far below SMA150",
}

export function StageChartExample({ stage, className }: StageChartExampleProps) {
  const data = React.useMemo(() => generateStageData(stage), [stage])
  const stageColorTuple = STAGE_HEX[stage]
  const stageColor = stageColorTuple?.[0] ?? "#718096"

  return (
    <div className={cn("rounded-lg border border-border bg-card p-4", className)}>
      <div className="mb-2 flex items-center justify-between">
        <span
          className="rounded px-2 py-0.5 text-sm font-semibold text-white"
          style={{ backgroundColor: stageColor }}
        >
          Stage {stage}
        </span>
        <span className="text-xs text-muted-foreground">
          {stageDescriptions[stage]}
        </span>
      </div>
      <div className="h-40">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 5, right: 5, left: -20, bottom: 5 }}>
            <defs>
              <linearGradient id={`gradient-${stage}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor={stageColor} stopOpacity={0.3} />
                <stop offset="95%" stopColor={stageColor} stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis
              dataKey="day"
              tick={{ fontSize: 10 }}
              tickLine={false}
              axisLine={false}
              interval="preserveStartEnd"
            />
            <YAxis
              tick={{ fontSize: 10 }}
              tickLine={false}
              axisLine={false}
              domain={["auto", "auto"]}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "hsl(var(--card))",
                border: "1px solid hsl(var(--border))",
                borderRadius: "6px",
                fontSize: "12px",
              }}
              formatter={(value) => {
                const num = typeof value === "number" ? value : 0
                return num.toFixed(1)
              }}
              labelFormatter={(label) => `Day ${label}`}
            />
            <Area
              type="monotone"
              dataKey="price"
              stroke={stageColor}
              strokeWidth={2}
              fill={`url(#gradient-${stage})`}
              name="Price"
            />
            <Line
              type="monotone"
              dataKey="sma150"
              stroke="hsl(var(--muted-foreground))"
              strokeWidth={1.5}
              strokeDasharray="4 4"
              dot={false}
              name="SMA150"
            />
            <ReferenceLine
              y={data[Math.floor(data.length / 2)].sma150}
              stroke="hsl(var(--muted-foreground))"
              strokeOpacity={0.3}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-2 flex items-center justify-center gap-4 text-xs text-muted-foreground">
        <span className="flex items-center gap-1">
          <span
            className="inline-block h-2 w-4 rounded-sm"
            style={{ backgroundColor: stageColor }}
          />
          Price
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-0.5 w-4 border-t-2 border-dashed border-muted-foreground" />
          SMA150
        </span>
      </div>
    </div>
  )
}

interface StageChartGridProps {
  stages?: StageKey[]
  className?: string
}

export function StageChartGrid({
  stages = ["1A", "1B", "2A", "2B", "2C", "3A", "3B", "4A", "4B", "4C"],
  className,
}: StageChartGridProps) {
  return (
    <div className={cn("grid gap-4 sm:grid-cols-2 lg:grid-cols-3", className)}>
      {stages.map((stage) => (
        <StageChartExample key={stage} stage={stage} />
      ))}
    </div>
  )
}

interface InteractiveStageExplorerProps {
  className?: string
}

export function InteractiveStageExplorer({ className }: InteractiveStageExplorerProps) {
  const [selectedStage, setSelectedStage] = React.useState<StageKey>("2A")
  const stages: StageKey[] = ["1A", "1B", "2A", "2B", "2C", "3A", "3B", "4A", "4B", "4C"]

  return (
    <div className={cn("rounded-xl border border-border bg-card p-4", className)}>
      <h4 className="mb-3 text-sm font-medium">Interactive Stage Explorer</h4>
      <div className="mb-4 flex flex-wrap gap-2">
        {stages.map((stage) => {
          const colorTuple = STAGE_HEX[stage]
          const bgColor = colorTuple?.[0]
          return (
            <button
              key={stage}
              type="button"
              onClick={() => setSelectedStage(stage)}
              className={cn(
                "rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
                selectedStage === stage
                  ? "text-white"
                  : "bg-muted text-muted-foreground hover:bg-muted/80"
              )}
              style={{
                backgroundColor: selectedStage === stage ? bgColor : undefined,
              }}
            >
              {stage}
            </button>
          )
        })}
      </div>
      <StageChartExample stage={selectedStage} />
    </div>
  )
}

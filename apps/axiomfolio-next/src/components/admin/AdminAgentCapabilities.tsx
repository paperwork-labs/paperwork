import * as React from "react"
import {
  Activity,
  BarChart3,
  Database,
  FileCode,
  Globe,
  Briefcase,
  TrendingUp,
} from "lucide-react"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"

export interface Capability {
  name: string
  description: string
  risk: "safe" | "moderate"
}

export interface CapabilityGroup {
  title: string
  icon: React.ElementType
  description: string
  capabilities: Capability[]
}

export const CAPABILITY_GROUPS: CapabilityGroup[] = [
  {
    title: "Market Insights",
    icon: TrendingUp,
    description: "Analyze market breadth, sectors, and trading opportunities",
    capabilities: [
      {
        name: "get_stage_distribution",
        description: "Stock count by stage (1A-4C), bullish/bearish breadth",
        risk: "safe",
      },
      {
        name: "get_sector_strength",
        description: "Rank sectors by % in constructive stages",
        risk: "safe",
      },
      {
        name: "get_top_scans",
        description: "Top stocks passing scan filters, ranked by RS",
        risk: "safe",
      },
      {
        name: "get_regime",
        description: "Current market regime (R1-R5) with all inputs",
        risk: "safe",
      },
      {
        name: "get_regime_history",
        description: "Regime changes and volatility over time",
        risk: "safe",
      },
    ],
  },
  {
    title: "Portfolio",
    icon: Briefcase,
    description: "View positions, P&L, and portfolio risk",
    capabilities: [
      {
        name: "get_portfolio_summary",
        description: "Risk metrics, sector allocation, P&L",
        risk: "safe",
      },
      {
        name: "get_position_details",
        description: "Position details with current stage and indicators",
        risk: "safe",
      },
      {
        name: "get_activity",
        description: "Recent trades and portfolio activity",
        risk: "safe",
      },
      {
        name: "get_exit_alerts",
        description: "Positions in warning stages needing review",
        risk: "safe",
      },
    ],
  },
  {
    title: "Market Data",
    icon: BarChart3,
    description: "Access price data, indicators, and universe",
    capabilities: [
      {
        name: "get_market_snapshot",
        description: "Stage, RSI, MACD, MAs for any symbol",
        risk: "safe",
      },
      {
        name: "get_tracked_universe",
        description: "All tracked symbols with sources",
        risk: "safe",
      },
      {
        name: "get_constituents",
        description: "S&P 500, NASDAQ-100, Russell 2000 members",
        risk: "safe",
      },
    ],
  },
  {
    title: "System Operations",
    icon: Activity,
    description: "Monitor health and run maintenance tasks",
    capabilities: [
      {
        name: "check_health",
        description: "Composite health across all dimensions",
        risk: "safe",
      },
      {
        name: "list_jobs",
        description: "Recent job runs with status",
        risk: "safe",
      },
      {
        name: "backfill_stale_daily",
        description: "Backfill missing price data",
        risk: "moderate",
      },
      {
        name: "recompute_indicators",
        description: "Recalculate stages and indicators",
        risk: "moderate",
      },
      {
        name: "compute_regime",
        description: "Compute daily market regime",
        risk: "moderate",
      },
      {
        name: "refresh_index_constituents",
        description: "Update index membership lists",
        risk: "moderate",
      },
    ],
  },
  {
    title: "Database",
    icon: Database,
    description: "Query and explore the database schema",
    capabilities: [
      {
        name: "describe_tables",
        description: "List tables or describe columns",
        risk: "safe",
      },
      {
        name: "query_database",
        description: "Run read-only SQL queries",
        risk: "safe",
      },
    ],
  },
  {
    title: "Codebase",
    icon: FileCode,
    description: "Read and explore backend code",
    capabilities: [
      {
        name: "read_file",
        description: "Read files from backend/ directory",
        risk: "safe",
      },
      {
        name: "list_files",
        description: "List files in a directory",
        risk: "safe",
      },
    ],
  },
  {
    title: "External",
    icon: Globe,
    description: "Web search and notifications",
    capabilities: [
      {
        name: "web_search",
        description: "Search the web for information",
        risk: "safe",
      },
      {
        name: "browse_url",
        description: "Fetch content from a URL",
        risk: "safe",
      },
      {
        name: "send_alert",
        description: "Send Discord notification",
        risk: "moderate",
      },
    ],
  },
]

const AdminAgentCapabilities: React.FC = () => {
  const totalCapabilities = CAPABILITY_GROUPS.reduce(
    (sum, g) => sum + g.capabilities.length,
    0
  )

  return (
    <div className="flex flex-col gap-6">
      <header>
        <h1 className="text-xl font-semibold tracking-tight text-foreground">
          Agent Capabilities
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {totalCapabilities} tools available across {CAPABILITY_GROUPS.length}{" "}
          categories. Admin-only access.
        </p>
      </header>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {CAPABILITY_GROUPS.map((group) => {
          const Icon = group.icon
          return (
            <Card key={group.title} className="flex flex-col">
              <CardHeader className="pb-3">
                <div className="flex items-center gap-2">
                  <Icon className="size-5 text-primary" aria-hidden />
                  <CardTitle className="text-base">{group.title}</CardTitle>
                </div>
                <CardDescription className="text-xs">
                  {group.description}
                </CardDescription>
              </CardHeader>
              <CardContent className="flex-1 pt-0">
                <ul className="space-y-2">
                  {group.capabilities.map((cap) => (
                    <li
                      key={cap.name}
                      className="flex items-start gap-2 text-sm"
                    >
                      <Badge
                        variant={
                          cap.risk === "safe" ? "secondary" : "outline"
                        }
                        className="mt-0.5 shrink-0 text-[10px] capitalize"
                      >
                        {cap.risk}
                      </Badge>
                      <div className="min-w-0">
                        <code className="text-xs font-medium text-primary">
                          {cap.name}
                        </code>
                        <p className="text-xs text-muted-foreground">
                          {cap.description}
                        </p>
                      </div>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )
        })}
      </div>
    </div>
  )
}

export default AdminAgentCapabilities

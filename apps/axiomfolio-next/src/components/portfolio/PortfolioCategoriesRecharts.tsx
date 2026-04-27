"use client";

import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { formatMoney } from "@/utils/format";

export type CategoryRowLite = {
  name: string;
  target_allocation_pct?: number | null;
  actual_allocation_pct?: number;
  total_value?: number;
};

const COLORS_DEFAULT = [
  "#3B82F6",
  "#10B981",
  "#F59E0B",
  "#EF4444",
  "#8B5CF6",
  "#EC4899",
  "#14B8A6",
  "#F97316",
];

export function AllocationChart({
  categories,
  currency,
  colors = COLORS_DEFAULT,
}: {
  categories: CategoryRowLite[];
  currency: string;
  colors?: string[];
}) {
  const data = categories
    .filter((c) => (c.total_value ?? 0) > 0)
    .map((c) => ({
      name: c.name,
      value: Number(c.total_value ?? 0),
      target: Number(c.target_allocation_pct ?? 0),
      actual: Number(c.actual_allocation_pct ?? 0),
    }));

  if (data.length === 0) return null;

  return (
    <Card className="gap-0 py-0">
      <CardContent className="pt-6">
        <p className="mb-3 font-medium text-foreground">Allocation Overview</p>
        <div className="flex flex-wrap items-center gap-6">
          <div className="h-[200px] w-[200px] shrink-0">
            <ResponsiveContainer>
              <PieChart>
                <Pie data={data} dataKey="value" nameKey="name" innerRadius={50} outerRadius={80} paddingAngle={2}>
                  {data.map((_, i) => (
                    <Cell key={i} fill={colors[i % colors.length]} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(value) => formatMoney(Number(value ?? 0), currency, { maximumFractionDigits: 0 })}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="flex min-w-0 flex-1 flex-col gap-1">
            {data.map((d, i) => (
              <div key={d.name} className="flex flex-wrap items-center justify-between gap-2 text-sm">
                <div className="flex items-center gap-2">
                  <span
                    className="size-2.5 shrink-0 rounded-full"
                    style={{ backgroundColor: colors[i % colors.length] }}
                    aria-hidden
                  />
                  <span>{d.name}</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="font-mono text-muted-foreground">{d.actual.toFixed(1)}%</span>
                  {d.target > 0 ? (
                    <span
                      className={cn(
                        "font-mono text-xs",
                        Math.abs(d.actual - d.target) > 5
                          ? "text-[rgb(var(--status-danger)/1)]"
                          : "text-muted-foreground",
                      )}
                    >
                      target {d.target}%
                    </span>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export function RebalancePreviewPies({
  categories,
  colors = COLORS_DEFAULT,
}: {
  categories: CategoryRowLite[];
  colors?: string[];
}) {
  return (
    <div className="mb-4 flex flex-wrap items-start gap-6">
      <div className="flex flex-col items-center gap-1">
        <span className="text-xs font-bold text-muted-foreground">CURRENT</span>
        <div className="h-[120px] w-[120px]">
          <ResponsiveContainer>
            <PieChart>
              <Pie
                data={categories
                  .filter((c) => (c.actual_allocation_pct ?? 0) > 0)
                  .map((c) => ({ name: c.name, value: Number(c.actual_allocation_pct ?? 0) }))}
                dataKey="value"
                innerRadius={30}
                outerRadius={50}
                paddingAngle={2}
              >
                {categories.map((_, i) => (
                  <Cell key={i} fill={colors[i % colors.length]} />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>
      <div className="flex flex-col items-center gap-1">
        <span className="text-xs font-bold text-muted-foreground">TARGET</span>
        <div className="h-[120px] w-[120px]">
          <ResponsiveContainer>
            <PieChart>
              <Pie
                data={categories
                  .filter((c) => (c.target_allocation_pct ?? 0) > 0)
                  .map((c) => ({ name: c.name, value: Number(c.target_allocation_pct ?? 0) }))}
                dataKey="value"
                innerRadius={30}
                outerRadius={50}
                paddingAngle={2}
              >
                {categories.map((_, i) => (
                  <Cell key={i} fill={colors[i % colors.length]} />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

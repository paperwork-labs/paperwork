import type { LucideIcon } from "lucide-react";
import {
  LayoutDashboard,
  Shield,
  Rocket,
  Target,
  Boxes,
  BookOpen,
  Sparkles,
  GitBranch,
  Kanban,
  Workflow,
  Receipt,
  Users,
  MessageSquare,
} from "lucide-react";

export type NavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
  /** Pending founder-only items (Conversations nav — data from founder-actions sync until PR E) */
  pendingBadge?: { count: number; hasCritical: boolean } | null;
  /** Static sidebar count; always rendered including 0 (PR N wires Expenses) */
  staticPendingCount?: number;
};

export type NavGroup = {
  label: string | null;
  items: NavItem[];
};

export function buildNavGroups(
  founderPending: { count: number; hasCritical: boolean } | null,
  expensesPending: { count: number; hasCritical: boolean } | null
): NavGroup[] {
  return [
    {
      label: null,
      items: [{ href: "/admin", label: "Overview", icon: LayoutDashboard }],
    },
    {
      label: "Trackers",
      items: [
        { href: "/admin/tasks", label: "Tasks (company)", icon: Target },
        { href: "/admin/products", label: "Products", icon: Boxes },
        { href: "/admin/sprints", label: "Sprints", icon: Rocket },
        { href: "/admin/workstreams", label: "Workstreams", icon: Kanban },
        { href: "/admin/pr-pipeline", label: "PR pipeline", icon: GitBranch },
        {
          href: "/admin/expenses",
          label: "Expenses",
          icon: Receipt,
          pendingBadge: expensesPending,
        },
      ],
    },
    {
      label: "Operations",
      items: [
        { href: "/admin/runbook", label: "Runbook", icon: BookOpen },
      ],
    },
    {
      label: "Architecture",
      items: [
        { href: "/admin/architecture", label: "Architecture", icon: Workflow },
        { href: "/admin/docs", label: "Docs", icon: BookOpen },
        { href: "/admin/infrastructure", label: "Infrastructure", icon: Shield },
      ],
    },
    {
      label: "Brain",
      items: [
        { href: "/admin/brain/personas", label: "People", icon: Users },
        {
          href: "/admin/brain/conversations",
          label: "Conversations",
          icon: MessageSquare,
          pendingBadge: founderPending,
        },
        {
          href: "/admin/brain/self-improvement",
          label: "Self-improvement",
          icon: Sparkles,
        },
      ],
    },
  ];
}

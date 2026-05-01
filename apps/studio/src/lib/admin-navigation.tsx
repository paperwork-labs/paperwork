import type { LucideIcon } from "lucide-react";
import {
  LayoutDashboard,
  Shield,
  Target,
  ListChecks,
  Boxes,
  BookOpen,
  Sparkles,
  Kanban,
  Workflow,
  Receipt,
  Users,
  MessageSquare,
  Calendar as CalendarIcon,
  UserCircle2,
  KeyRound,
  Building2,
  FileText,
  Network,
  Bot,
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
      label: "Money",
      items: [
        {
          href: "/admin/expenses",
          label: "Expenses",
          icon: Receipt,
          pendingBadge: expensesPending,
        },
        { href: "/admin/vendors", label: "Vendors", icon: Building2 },
        { href: "/admin/bills", label: "Bills", icon: FileText },
      ],
    },
    {
      label: "Trackers",
      items: [
        { href: "/admin/tasks", label: "Tasks (company)", icon: ListChecks },
        { href: "/admin/goals", label: "Goals", icon: Target },
        { href: "/admin/calendar", label: "Calendar", icon: CalendarIcon },
        { href: "/admin/products", label: "Products", icon: Boxes },
        { href: "/admin/workstreams", label: "Workstreams", icon: Kanban },
      ],
    },
    {
      label: "Operations",
      items: [
        { href: "/admin/runbook", label: "Runbook", icon: BookOpen },
      ],
    },
    {
      label: "Trust",
      items: [
        { href: "/admin/circles", label: "Circles", icon: UserCircle2 },
        { href: "/admin/delegated", label: "Delegated access", icon: KeyRound },
      ],
    },
    {
      label: "Architecture",
      items: [
        { href: "/admin/architecture", label: "Architecture", icon: Workflow },
        { href: "/admin/docs", label: "Docs", icon: BookOpen },
        { href: "/admin/docs/graph", label: "Knowledge Graph", icon: Network },
        { href: "/admin/infrastructure", label: "Infrastructure", icon: Shield },
      ],
    },
    {
      label: "Brain",
      items: [
        { href: "/admin/autopilot", label: "Autopilot", icon: Bot },
        { href: "/admin/people", label: "People", icon: Users },
        {
          href: "/admin/conversations",
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

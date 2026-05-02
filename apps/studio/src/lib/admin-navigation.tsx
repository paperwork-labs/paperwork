import type { LucideIcon } from "lucide-react";
import {
  LayoutDashboard,
  Shield,
  Target,
  Boxes,
  BookOpen,
  Sparkles,
  Kanban,
  Workflow,
  Receipt,
  Users,
  MessageSquare,
  Building2,
  FileText,
  Bot,
  ClipboardCheck,
} from "lucide-react";

export type NavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
  /** Pending founder-only items (Conversations nav — data from founder-actions sync until PR E) */
  pendingBadge?: { count: number; hasCritical: boolean } | null;
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
      label: "Brain",
      items: [
        {
          href: "/admin/conversations",
          label: "Conversations",
          icon: MessageSquare,
          pendingBadge: founderPending,
        },
        { href: "/admin/autopilot", label: "Autopilot", icon: Bot },
        { href: "/admin/people", label: "People", icon: Users },
        {
          href: "/admin/brain/self-improvement",
          label: "Self-improvement",
          icon: Sparkles,
        },
      ],
    },
    {
      label: null,
      items: [
        { href: "/admin/workstreams", label: "Epics", icon: Kanban },
        { href: "/admin/products", label: "Products", icon: Boxes },
        { href: "/admin/goals", label: "Goals", icon: Target },
      ],
    },
    {
      label: "SYSTEMS",
      items: [
        { href: "/admin/architecture", label: "Architecture", icon: Workflow },
        { href: "/admin/infrastructure", label: "Infrastructure", icon: Shield },
        {
          href: "/admin/docs/day-0-founder-actions",
          label: "Day-0 checklist",
          icon: ClipboardCheck,
        },
      ],
    },
    {
      label: null,
      items: [{ href: "/admin/docs", label: "Docs", icon: BookOpen }],
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
  ];
}

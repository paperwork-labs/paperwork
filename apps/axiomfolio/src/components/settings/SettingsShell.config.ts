import type { SettingsCluster } from "@paperwork-labs/ui";
import {
  Activity,
  Bell,
  ClipboardList,
  Cpu,
  Database,
  KeyRound,
  Link2,
  Lock,
  ShieldAlert,
  Sliders,
  User,
} from "lucide-react";

/** AxiomFolio settings nav — passed to `SettingsShell` from `@paperwork-labs/ui`. */
export const AXIOMFOLIO_SETTINGS_CLUSTERS: readonly SettingsCluster[] = [
  {
    id: "account",
    label: "Account",
    items: [
      { to: "/settings/profile", label: "Profile", icon: User },
      { to: "/settings/preferences", label: "Preferences", icon: Sliders },
      { to: "/settings/notifications", label: "Notifications", icon: Bell },
    ],
  },
  {
    id: "connections",
    label: "Connections",
    items: [
      { to: "/settings/connections", label: "Brokers", icon: Link2 },
      {
        to: "/settings/connections/historical-import",
        label: "Historical import",
        icon: Database,
      },
    ],
  },
  {
    id: "trading",
    label: "Trading",
    items: [{ to: "/settings/account-risk", label: "Account risk", icon: ShieldAlert }],
  },
  {
    id: "ai",
    label: "AI",
    items: [
      { to: "/settings/ai-keys", label: "AI keys", icon: KeyRound },
      { to: "/settings/mcp", label: "MCP tokens", icon: KeyRound },
    ],
  },
  {
    id: "privacy",
    label: "Privacy",
    items: [{ to: "/settings/data-privacy", label: "Data privacy", icon: Lock }],
  },
  {
    id: "admin",
    label: "Admin",
    adminOnly: true,
    items: [
      { to: "/system-status", label: "System Status", icon: Activity },
      { to: "/settings/users", label: "Users", icon: User },
      { to: "/settings/admin/agent", label: "Agent", icon: Cpu },
      { to: "/settings/admin/picks", label: "Picks validator", icon: ClipboardList },
    ],
  },
];

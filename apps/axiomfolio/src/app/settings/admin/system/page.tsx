import { redirect } from "next/navigation";

/** Legacy Vite path `/settings/admin/system` — canonical Next route is `/system-status`. */
export default function SettingsAdminSystemRedirectPage() {
  redirect("/system-status");
}

import { redirect } from "next/navigation";

/** Legacy Vite path `/settings/admin/users` — canonical Next route is `/settings/users`. */
export default function SettingsAdminUsersRedirectPage() {
  redirect("/settings/users");
}

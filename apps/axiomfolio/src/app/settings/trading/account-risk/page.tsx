import { redirect } from "next/navigation";

/** Legacy Vite canonical path; app IA uses `/settings/account-risk`. */
export default function SettingsTradingAccountRiskRedirectPage() {
  redirect("/settings/account-risk");
}

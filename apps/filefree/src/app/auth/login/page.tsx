import { redirect } from "next/navigation";

/** WS-13: primary consumer sign-in is Clerk at `/sign-in`. Legacy UI: `legacy-login-page.tsx`. */
export default function LoginPage() {
  redirect("/sign-in");
}

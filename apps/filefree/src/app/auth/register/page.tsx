import { redirect } from "next/navigation";

/** WS-13: primary consumer sign-up is Clerk at `/sign-up`. Legacy UI: `legacy-register-page.tsx`. */
export default function RegisterPage() {
  redirect("/sign-up");
}

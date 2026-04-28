import { redirect } from "next/navigation";

/** Bookmark-compat redirect — consumer sign-up is Clerk at `/sign-up`. */
export default function RegisterPage() {
  redirect("/sign-up");
}

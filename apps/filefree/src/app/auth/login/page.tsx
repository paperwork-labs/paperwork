import { redirect } from "next/navigation";

/** Bookmark-compat redirect — consumer sign-in is Clerk at `/sign-in`. */
export default function LoginPage() {
  redirect("/sign-in");
}

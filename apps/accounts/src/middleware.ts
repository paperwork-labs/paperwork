import { clerkMiddleware } from "@paperwork-labs/auth-clerk/server/clerk";

/**
 * Primary Clerk host: Clerk session propagation only. Entire surface is public
 * (/, /sign-in, /sign-up, /api/health) — no Basic Auth or route guards.
 */
export default clerkMiddleware(() => {
  // Intentionally empty: no `auth().protect()` or custom redirects.
});

export const config = {
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
  ],
};

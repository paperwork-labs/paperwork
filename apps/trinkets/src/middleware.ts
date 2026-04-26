import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";

/**
 * Trinkets: Clerk session for SSO-ready surfaces. No legacy cookie or admin/Basic
 * composition — the app is a public utility shell; sign-in/sign-up and `/` are
 * public. Future protected routes can add `auth().protect()` or a matcher
 * following the LaunchFree/Studio pattern.
 */
const isPublicRoute = createRouteMatcher([
  "/",
  "/sign-in(.*)",
  "/sign-up(.*)",
  "/api/health",
  "/api/health/(.*)",
]);

export default clerkMiddleware(async (_auth, request) => {
  if (isPublicRoute(request)) {
    return;
  }
});

export const config = {
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
  ],
};

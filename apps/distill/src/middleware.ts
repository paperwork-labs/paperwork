import {
  clerkMiddleware,
  createRouteMatcher,
} from "@paperwork-labs/auth-clerk/server/clerk";

/**
 * Distill: Clerk SSO only (no legacy session / Basic Auth). `/dashboard` requires
 * a Clerk session; the page may still redirect when `DISTILL_DASHBOARD_ENABLED` is
 * unset outside development (feature gate).
 */
const isDashboardRoute = createRouteMatcher(["/dashboard(.*)"]);

export default clerkMiddleware(async (auth, request) => {
  if (!isDashboardRoute(request)) {
    return;
  }

  const { userId, redirectToSignIn } = await auth();
  if (!userId) {
    return redirectToSignIn({ returnBackUrl: request.url });
  }
});

export const config = {
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
  ],
};

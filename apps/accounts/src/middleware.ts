import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";

const isPublicRoute = createRouteMatcher([
  "/",
  "/sign-in(.*)",
  "/sign-up(.*)",
  "/api/health",
  "/api/health/(.*)",
]);

/**
 * Primary Clerk host: public landing + embedded sign-in/up. Protected routes can
 * be added later with auth().protect() or an expanded matcher.
 */
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

"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LogOut, Menu, X } from "lucide-react";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useUser } from "@clerk/nextjs";

import { Button } from "@paperwork-labs/ui";
import { useAuthStore } from "@/stores/auth-store";
import { useLogout } from "@/hooks/use-auth";

const HIDE_NAV_PREFIXES = ["/auth", "/sign-in", "/sign-up"];

export function Nav() {
  const pathname = usePathname();
  const { isAuthenticated, isLoading, user } = useAuthStore();
  const { isLoaded: clerkLoaded, isSignedIn, user: clerkUser } = useUser();
  const logout = useLogout();
  const [mobileOpen, setMobileOpen] = useState(false);

  if (HIDE_NAV_PREFIXES.some((p) => pathname.startsWith(p))) return null;

  const authLoading = isLoading || !clerkLoaded;
  const loggedIn = isAuthenticated || Boolean(isSignedIn);
  const displayUser =
    user ??
    (clerkUser
      ? {
          email: clerkUser.primaryEmailAddress?.emailAddress ?? "",
          full_name: clerkUser.fullName ?? undefined,
        }
      : null);

  return (
    <nav className="fixed top-0 z-50 w-full border-b border-border/40 bg-background/80 backdrop-blur-lg">
      <div className="mx-auto flex h-14 max-w-5xl items-center justify-between px-4">
        <Link href="/" className="flex items-center gap-1.5">
          <span className="text-lg font-bold tracking-tight">
            File
            <span className="bg-gradient-to-r from-violet-500 to-purple-600 bg-clip-text text-transparent">
              Free
            </span>
          </span>
        </Link>

        {/* Desktop */}
        <div className="hidden items-center gap-3 sm:flex">
          <NavLinks
            loggedIn={loggedIn}
            isLoading={authLoading}
            user={displayUser}
            logout={logout}
          />
        </div>

        {/* Mobile toggle */}
        <button
          className="sm:hidden text-muted-foreground hover:text-foreground"
          onClick={() => setMobileOpen(!mobileOpen)}
          aria-label={mobileOpen ? "Close menu" : "Open menu"}
        >
          {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>

      {/* Mobile drawer */}
      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            className="flex flex-col gap-3 border-t border-border/40 bg-background px-4 pb-4 pt-3 sm:hidden"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.2 }}
          >
            <NavLinks
              loggedIn={loggedIn}
              isLoading={authLoading}
              user={displayUser}
              logout={logout}
              mobile
              onNavigate={() => setMobileOpen(false)}
            />
          </motion.div>
        )}
      </AnimatePresence>
    </nav>
  );
}

function NavLinks({
  loggedIn,
  isLoading,
  user,
  logout,
  mobile,
  onNavigate,
}: {
  loggedIn: boolean;
  isLoading: boolean;
  user: { full_name?: string; email: string } | null;
  logout: ReturnType<typeof useLogout>;
  mobile?: boolean;
  onNavigate?: () => void;
}) {
  if (isLoading) return null;

  const linkClass = mobile
    ? "text-sm text-muted-foreground hover:text-foreground transition"
    : "text-sm text-muted-foreground hover:text-foreground transition";

  if (loggedIn && user) {
    const initial = (user.full_name?.[0] ?? user.email[0] ?? "U").toUpperCase();

    return (
      <>
        <Link href="/demo" className={linkClass} onClick={onNavigate}>
          Demo
        </Link>
        <Link href="/file" className={linkClass} onClick={onNavigate}>
          File Taxes
        </Link>
        <div className={`flex items-center gap-2 ${mobile ? "mt-1" : ""}`}>
          <Link
            href="/file"
            className="flex h-7 w-7 items-center justify-center rounded-full bg-violet-600 text-xs font-semibold text-white"
            onClick={onNavigate}
          >
            {initial}
          </Link>
          <button
            onClick={() => {
              logout.mutate();
              onNavigate?.();
            }}
            className="text-sm text-muted-foreground hover:text-foreground transition flex items-center gap-1"
          >
            <LogOut className="h-3.5 w-3.5" />
            Sign out
          </button>
        </div>
      </>
    );
  }

  return (
    <>
      <Link href="/demo" className={linkClass} onClick={onNavigate}>
        Demo
      </Link>
      <Link href="/pricing" className={linkClass} onClick={onNavigate}>
        Pricing
      </Link>
      <Link href="/sign-in" className={linkClass} onClick={onNavigate}>
        Sign in
      </Link>
      <Button asChild size="sm" className="bg-gradient-to-r from-violet-600 to-purple-600 text-white border-0 hover:from-violet-500 hover:to-purple-500">
        <Link href="/sign-up" onClick={onNavigate}>
          Sign up free
        </Link>
      </Button>
    </>
  );
}

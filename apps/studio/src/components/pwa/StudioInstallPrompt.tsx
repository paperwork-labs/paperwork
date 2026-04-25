"use client";

// Track M.7 — Studio-flavoured wrapper around @paperwork-labs/pwa.
//
// Studio ships with Tailwind + shadcn already, so we give
// `<InstallPrompt>` a render override that uses our own Button +
// motion primitives. That keeps the shared package lightweight while
// letting Studio feel native.

import { InstallPrompt } from "@paperwork-labs/pwa";

export function StudioInstallPrompt() {
  return (
    <InstallPrompt
      appName="Paperwork Studio"
      // Distinct dismissKey so AxiomFolio's dismissal doesn't silence
      // Studio's prompt (and vice versa) when they share a hostname.
      dismissKey="studio:pwa_install_dismissed_until"
      render={({ appName, isIosSafari, isPrompting, install, dismiss }) => (
        <aside
          role="dialog"
          aria-labelledby="studio-pwa-install-title"
          aria-describedby="studio-pwa-install-body"
          className="pointer-events-none fixed inset-x-0 bottom-0 z-50 mx-auto max-w-md px-4 pb-[calc(env(safe-area-inset-bottom)+1rem)] sm:inset-auto sm:right-4 sm:bottom-4 sm:left-auto sm:mx-0 sm:px-0 sm:pb-0"
        >
          <div className="pointer-events-auto rounded-xl border border-border bg-popover p-4 text-popover-foreground shadow-xl backdrop-blur-sm">
            <div className="flex items-start gap-3">
              <div className="min-w-0 flex-1">
                <p
                  id="studio-pwa-install-title"
                  className="text-sm font-semibold text-foreground"
                >
                  Install {appName}
                </p>
                <p
                  id="studio-pwa-install-body"
                  className="mt-1 text-xs text-muted-foreground"
                >
                  {isIosSafari
                    ? "Tap Share, then Add to Home Screen for a faster, full-screen command center."
                    : "Faster, full-screen, one-click access to your command center from the dock."}
                </p>
                {!isIosSafari && (
                  <div className="mt-3 flex items-center gap-2">
                    <button
                      type="button"
                      onClick={install}
                      disabled={isPrompting}
                      className="inline-flex h-8 items-center rounded-md bg-foreground px-3 text-xs font-medium text-background transition hover:bg-foreground/90 disabled:opacity-60"
                    >
                      {isPrompting ? "Installing…" : "Install app"}
                    </button>
                    <button
                      type="button"
                      onClick={dismiss}
                      className="inline-flex h-8 items-center rounded-md px-3 text-xs text-muted-foreground transition hover:text-foreground"
                    >
                      Not now
                    </button>
                  </div>
                )}
              </div>
              <button
                type="button"
                aria-label="Dismiss install prompt"
                onClick={dismiss}
                className="-mt-1 -mr-1 text-muted-foreground hover:text-foreground"
              >
                ×
              </button>
            </div>
          </div>
        </aside>
      )}
    />
  );
}

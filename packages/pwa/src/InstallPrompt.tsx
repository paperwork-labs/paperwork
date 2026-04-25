// Track M.7 — framework-free install affordance.
//
// The AxiomFolio version leaned on framer-motion + shadcn Button +
// Tailwind. For the shared package we trade gloss for portability:
// vanilla React + inline semantic classes via a consumer-provided
// ``classNameOverrides`` prop. Studio and AxiomFolio can both wrap
// this with their own styled Button if they want richer motion.
//
// The visibility rules (session gate, iOS detection, installed guard)
// come from ``usePWAInstallable`` and are identical to the origin.

import { useState } from "react";
import type { ReactElement } from "react";

import type { UsePWAInstallableOptions } from "./usePWAInstallable";
import { usePWAInstallable } from "./usePWAInstallable";

export interface InstallPromptProps extends UsePWAInstallableOptions {
  /** App name shown in the prompt title (e.g. "AxiomFolio", "Paperwork Studio"). */
  appName: string;
  /**
   * Force visibility regardless of session/dismissal gating. Used for
   * Storybook, tests, and operator "what would this look like?" toggles.
   */
  forceVisible?: boolean;
  /** Escape hatch for host-specific styling. */
  className?: string;
  /**
   * Optional render override — consuming apps with their own Button /
   * Card / motion primitives can hand in a renderer and use our hook
   * as-is. Returns null when the prompt should stay hidden.
   */
  render?: (state: {
    appName: string;
    isIosSafari: boolean;
    isPrompting: boolean;
    install: () => Promise<void>;
    dismiss: () => void;
  }) => ReactElement | null;
}

const baseAside: React.CSSProperties = {
  position: "fixed",
  zIndex: 50,
  insetInlineStart: 0,
  insetInlineEnd: 0,
  bottom: "calc(env(safe-area-inset-bottom, 0px) + 1rem)",
  marginInline: "auto",
  maxWidth: "28rem",
  padding: "0 1rem",
  pointerEvents: "none",
};

const baseCard: React.CSSProperties = {
  pointerEvents: "auto",
  borderRadius: "12px",
  border: "1px solid rgba(0,0,0,0.1)",
  background: "var(--popover, #ffffff)",
  color: "var(--popover-foreground, #111827)",
  padding: "1rem",
  boxShadow: "0 10px 30px rgba(0,0,0,0.12)",
  display: "flex",
  gap: "0.75rem",
  alignItems: "flex-start",
};

const baseButton: React.CSSProperties = {
  padding: "0.375rem 0.75rem",
  borderRadius: "8px",
  border: "1px solid transparent",
  cursor: "pointer",
  fontSize: "0.875rem",
};

export function InstallPrompt(props: InstallPromptProps): ReactElement | null {
  const { appName, forceVisible, className, render, ...hookOptions } = props;
  const { canPrompt, isIosSafari, promptInstall, dismiss } =
    usePWAInstallable(hookOptions);
  const [isPrompting, setIsPrompting] = useState(false);

  const visible = forceVisible ?? canPrompt;
  if (!visible) return null;

  const handleInstall = async () => {
    if (isPrompting) return;
    setIsPrompting(true);
    try {
      const outcome = await promptInstall();
      if (outcome === "unavailable") dismiss();
    } finally {
      setIsPrompting(false);
    }
  };

  if (render) {
    return render({
      appName,
      isIosSafari,
      isPrompting,
      install: handleInstall,
      dismiss,
    });
  }

  return (
    <aside
      role="dialog"
      aria-labelledby="pwa-install-title"
      aria-describedby="pwa-install-body"
      className={className}
      style={baseAside}
    >
      <div style={baseCard}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <p
            id="pwa-install-title"
            style={{ margin: 0, fontSize: "0.875rem", fontWeight: 600 }}
          >
            Install {appName}
          </p>
          <p
            id="pwa-install-body"
            style={{
              margin: "0.25rem 0 0",
              fontSize: "0.75rem",
              opacity: 0.75,
            }}
          >
            {isIosSafari
              ? "Tap Share, then 'Add to Home Screen' for a faster, full-screen experience."
              : "Faster, full-screen, and quicker access from your dock."}
          </p>
          {!isIosSafari && (
            <div style={{ marginTop: "0.75rem", display: "flex", gap: "0.5rem" }}>
              <button
                type="button"
                onClick={handleInstall}
                disabled={isPrompting}
                style={{
                  ...baseButton,
                  background: "var(--primary, #111827)",
                  color: "var(--primary-foreground, #ffffff)",
                }}
              >
                {isPrompting ? "Installing…" : "Install app"}
              </button>
              <button
                type="button"
                onClick={dismiss}
                style={{
                  ...baseButton,
                  background: "transparent",
                  color: "inherit",
                  opacity: 0.7,
                }}
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
          style={{
            ...baseButton,
            background: "transparent",
            color: "inherit",
            opacity: 0.6,
            padding: "0.25rem 0.5rem",
          }}
        >
          ×
        </button>
      </div>
    </aside>
  );
}

export default InstallPrompt;

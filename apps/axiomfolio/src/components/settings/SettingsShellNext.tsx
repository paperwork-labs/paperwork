"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import {
  SettingsShell as BaseSettingsShell,
  type SettingsShellProps as BaseProps,
} from "@paperwork-labs/ui";

export type SettingsShellNextProps = Omit<BaseProps, "pathname" | "LinkComponent">;

/**
 * Next.js bridge over the framework-agnostic `SettingsShell`. Provides
 * `pathname` from `usePathname()` and Next's `Link` so the underlying shell
 * stays purity-clean.
 */
export function SettingsShell(props: SettingsShellNextProps) {
  const pathname = usePathname();
  return <BaseSettingsShell {...props} pathname={pathname ?? ""} LinkComponent={Link} />;
}

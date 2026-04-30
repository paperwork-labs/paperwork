import type { ReactNode } from "react";

export type HqPageContainerProps = {
  variant?: "narrow" | "default" | "wide" | "full";
  children: ReactNode;
  className?: string;
};

const MAX_W: Record<NonNullable<HqPageContainerProps["variant"]>, string> = {
  narrow: "max-w-[640px]",
  default: "max-w-[960px]",
  wide: "max-w-[1200px]",
  full: "max-w-full",
};

/** Centers admin page content with a consistent horizontal rhythm. */
export function HqPageContainer({
  variant = "default",
  children,
  className = "",
}: HqPageContainerProps) {
  return (
    <div className={`mx-auto w-full px-6 ${MAX_W[variant]} ${className}`.trim()}>
      {children}
    </div>
  );
}

"use client";

import * as React from "react";
import { ClippedWordmark } from "@paperwork-labs/ui";

const STORAGE_KEY = "pwl-clipped-wordmark-session";

export function SessionClippedWordmark({
  surface,
  className,
}: {
  surface: "light" | "dark";
  className?: string;
}): React.ReactElement {
  const [playEntrance, setPlayEntrance] = React.useState(false);
  const [hydrated, setHydrated] = React.useState(false);

  React.useEffect(() => {
    const seen = window.sessionStorage.getItem(STORAGE_KEY);
    if (!seen) {
      window.sessionStorage.setItem(STORAGE_KEY, "1");
      setPlayEntrance(true);
    }
    setHydrated(true);
  }, []);

  if (!hydrated) {
    return (
      <ClippedWordmark animated={false} surface={surface} className={className} />
    );
  }

  return (
    <ClippedWordmark
      key={playEntrance ? "play" : "static"}
      animated={playEntrance}
      surface={surface}
      className={className}
    />
  );
}

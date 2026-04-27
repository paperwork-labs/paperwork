"use client";

import dynamic from "next/dynamic";

const PortfolioOptionsClient = dynamic(
  () => import("@/components/portfolio/PortfolioOptionsClient"),
  { ssr: false },
);

export function PortfolioOptionsLazy() {
  return <PortfolioOptionsClient />;
}

"use client";

import { useEffect } from "react";
import { initObservability } from "@paperwork/observability";

export function ObservabilityBootstrap(props: {
  brainUrl: string;
  brainToken: string;
  env: "production" | "preview";
}) {
  useEffect(() => {
    initObservability({
      product: "studio",
      brainUrl: props.brainUrl,
      brainToken: props.brainToken,
      env: props.env,
    });
  }, [props.brainToken, props.brainUrl, props.env]);

  return null;
}

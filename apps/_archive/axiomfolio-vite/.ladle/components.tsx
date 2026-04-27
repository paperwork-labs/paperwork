import React from "react";
import { ColorModeProvider } from "../src/theme/colorMode";

export const Provider = ({ children }: { children: React.ReactNode }) => {
  return <ColorModeProvider>{children}</ColorModeProvider>;
};

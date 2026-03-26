import React from "react";

import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

type Props = Omit<React.ComponentProps<typeof Card>, "children"> & {
  bodyProps?: React.ComponentProps<typeof CardContent>;
  children: React.ReactNode;
};

export default function AppCard({ children, bodyProps, className, ...props }: Props) {
  const { className: bodyClassName, ...restBody } = bodyProps ?? {};

  return (
    <Card
      className={cn(
        "gap-0 border border-border py-0 shadow-[0_18px_55px_rgba(0,0,0,0.22)] ring-0",
        className
      )}
      {...props}
    >
      <CardContent className={cn("py-6", bodyClassName)} {...restBody}>
        {children}
      </CardContent>
    </Card>
  );
}

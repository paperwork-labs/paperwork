import React from "react";

import { Card, CardContent, type CardProps } from "@/components/ui/card";
import { cn } from "@/lib/utils";

type Props = Omit<CardProps, "children" | "variant" | "size"> & {
  bodyProps?: React.ComponentProps<typeof CardContent>;
  children: React.ReactNode;
};

export default function AppCard({ children, bodyProps, className, ...props }: Props) {
  const { className: bodyClassName, ...restBody } = bodyProps ?? {};

  return (
    <Card
      variant="elevated"
      size="none"
      className={className}
      {...props}
    >
      <CardContent className={cn("py-6", bodyClassName)} {...restBody}>
        {children}
      </CardContent>
    </Card>
  );
}

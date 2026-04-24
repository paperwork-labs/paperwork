import React from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

interface EmptyStateProps {
  icon?: React.ElementType;
  title: string;
  description?: string;
  action?: { label: string; onClick: () => void };
  secondaryAction?: { label: string; onClick: () => void };
}

const EmptyState: React.FC<EmptyStateProps> = ({
  icon: Icon,
  title,
  description,
  action,
  secondaryAction,
}) => {
  return (
    <Card className="border-0 bg-transparent py-0 shadow-none ring-0">
      <CardContent className="px-0 py-12 text-center">
        <div className="flex flex-col items-center gap-3">
          {Icon ? <Icon className="size-10 text-muted-foreground" aria-hidden /> : null}
          <h2 className="font-heading text-base font-medium text-foreground">{title}</h2>
          {description ? (
            <p className="max-w-3xl text-sm text-muted-foreground">{description}</p>
          ) : null}
          <div className="flex flex-col items-center gap-2">
            {action ? (
              <Button type="button" onClick={action.onClick}>
                {action.label}
              </Button>
            ) : null}
            {secondaryAction ? (
              <Button type="button" variant="ghost" onClick={secondaryAction.onClick}>
                {secondaryAction.label}
              </Button>
            ) : null}
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default EmptyState;

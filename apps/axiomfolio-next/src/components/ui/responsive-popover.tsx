/**
 * `ResponsivePopover` — Radix Popover on >=768px, Vaul bottom-sheet drawer
 * on <768px.
 *
 * Use this for popovers whose content is non-trivial on a phone: filter
 * panels, multi-input edit forms, or settings menus surfaced from a table
 * row. For chart tooltips and command palettes, prefer their own dedicated
 * mobile UX.
 */
import * as React from "react";
import * as PopoverPrimitive from "@radix-ui/react-popover";
import { Drawer as VaulDrawer } from "vaul";

import { cn } from "@/lib/utils";
import { useIsDesktop } from "@/hooks/useMediaQuery";

type Variant = "desktop" | "mobile";

const ResponsivePopoverContext = React.createContext<Variant>("desktop");

function useVariant(): Variant {
  return React.useContext(ResponsivePopoverContext);
}

interface ResponsivePopoverProps
  extends React.ComponentProps<typeof PopoverPrimitive.Root> {
  variant?: Variant;
}

function ResponsivePopover({
  variant: forcedVariant,
  children,
  ...props
}: ResponsivePopoverProps) {
  const isDesktop = useIsDesktop();
  const variant: Variant = forcedVariant ?? (isDesktop ? "desktop" : "mobile");

  if (variant === "desktop") {
    return (
      <ResponsivePopoverContext.Provider value="desktop">
        <PopoverPrimitive.Root data-slot="responsive-popover" {...props}>
          {children}
        </PopoverPrimitive.Root>
      </ResponsivePopoverContext.Provider>
    );
  }

  return (
    <ResponsivePopoverContext.Provider value="mobile">
      <VaulDrawer.Root data-slot="responsive-popover" {...props}>
        {children}
      </VaulDrawer.Root>
    </ResponsivePopoverContext.Provider>
  );
}

function ResponsivePopoverTrigger(
  props: React.ComponentProps<typeof PopoverPrimitive.Trigger>,
) {
  const variant = useVariant();
  if (variant === "desktop") {
    return (
      <PopoverPrimitive.Trigger
        data-slot="responsive-popover-trigger"
        {...props}
      />
    );
  }
  return (
    <VaulDrawer.Trigger data-slot="responsive-popover-trigger" {...props} />
  );
}

function ResponsivePopoverAnchor(
  props: React.ComponentProps<typeof PopoverPrimitive.Anchor>,
) {
  const variant = useVariant();
  if (variant === "desktop") {
    return (
      <PopoverPrimitive.Anchor
        data-slot="responsive-popover-anchor"
        {...props}
      />
    );
  }
  // Vaul has no anchor concept; render children unchanged.
  return <>{props.children}</>;
}

interface ResponsivePopoverContentProps
  extends React.ComponentProps<typeof PopoverPrimitive.Content> {
  /** Hide the drag handle on mobile. Defaults to visible. */
  showDragHandle?: boolean;
}

function ResponsivePopoverContent({
  className,
  children,
  align = "center",
  side = "bottom",
  sideOffset = 4,
  showDragHandle = true,
  ...props
}: ResponsivePopoverContentProps) {
  const variant = useVariant();

  if (variant === "desktop") {
    return (
      <PopoverPrimitive.Portal>
        <PopoverPrimitive.Content
          data-slot="responsive-popover-content"
          align={align}
          side={side}
          sideOffset={sideOffset}
          className={cn(
            "z-50 w-72 rounded-md border border-border bg-popover p-4 text-popover-foreground shadow-md outline-none",
            "data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95",
            "data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95",
            "motion-reduce:animate-none motion-reduce:transition-none",
            className,
          )}
          {...props}
        >
          {children}
        </PopoverPrimitive.Content>
      </PopoverPrimitive.Portal>
    );
  }

  return (
    <VaulDrawer.Portal>
      <VaulDrawer.Overlay
        className="fixed inset-0 z-50 bg-black/40 motion-reduce:transition-none"
      />
      <VaulDrawer.Content
        data-slot="responsive-popover-content"
        className={cn(
          "fixed inset-x-0 bottom-0 z-50 mt-24 flex max-h-[85dvh] flex-col rounded-t-xl bg-popover text-popover-foreground ring-1 ring-foreground/10 outline-none",
          "motion-reduce:transition-none",
          className,
        )}
      >
        {showDragHandle ? (
          <div
            aria-hidden
            className="mx-auto mt-2 mb-1 h-1.5 w-12 shrink-0 rounded-full bg-muted-foreground/40"
          />
        ) : null}
        <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-4">
          {children}
        </div>
      </VaulDrawer.Content>
    </VaulDrawer.Portal>
  );
}

function ResponsivePopoverClose(
  props: React.ComponentProps<typeof PopoverPrimitive.Close>,
) {
  const variant = useVariant();
  if (variant === "desktop") {
    return (
      <PopoverPrimitive.Close data-slot="responsive-popover-close" {...props} />
    );
  }
  return <VaulDrawer.Close data-slot="responsive-popover-close" {...props} />;
}

export {
  ResponsivePopover,
  ResponsivePopoverAnchor,
  ResponsivePopoverClose,
  ResponsivePopoverContent,
  ResponsivePopoverTrigger,
};

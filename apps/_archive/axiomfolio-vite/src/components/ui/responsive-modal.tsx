/**
 * `ResponsiveModal` — Radix Dialog on >=768px, Vaul bottom-sheet drawer on <768px.
 *
 * Mirrors the surface area of `components/ui/dialog.tsx` so consumers can
 * swap `import { Dialog, DialogContent, ... } from "@/components/ui/dialog"`
 * for the responsive variant without changing call sites.
 *
 * Notes:
 *   - The desktop/mobile primitive is decided once at mount via
 *     `useIsDesktop()`. We do NOT remount mid-session on resize because
 *     Radix and Vaul don't share state and tearing would close the modal.
 *   - Drag-to-dismiss is provided by Vaul's default `dismissible` behavior.
 *   - `prefers-reduced-motion` suppresses entrance/exit animations on both
 *     primitives via Tailwind `motion-reduce:*` utilities.
 */
import * as React from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { Drawer as VaulDrawer } from "vaul";
import { XIcon } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { useIsDesktop } from "@/hooks/useMediaQuery";

type Variant = "desktop" | "mobile";

const ResponsiveModalContext = React.createContext<Variant>("desktop");

function useVariant(): Variant {
  return React.useContext(ResponsiveModalContext);
}

interface ResponsiveModalProps
  extends React.ComponentProps<typeof DialogPrimitive.Root> {
  /**
   * Force a specific primitive regardless of viewport. Useful for stories,
   * tests, or surfaces where a designer has chosen a fixed treatment.
   */
  variant?: Variant;
}

function ResponsiveModal({
  variant: forcedVariant,
  children,
  ...props
}: ResponsiveModalProps) {
  const isDesktop = useIsDesktop();
  const variant: Variant = forcedVariant ?? (isDesktop ? "desktop" : "mobile");

  if (variant === "desktop") {
    return (
      <ResponsiveModalContext.Provider value="desktop">
        <DialogPrimitive.Root data-slot="responsive-modal" {...props}>
          {children}
        </DialogPrimitive.Root>
      </ResponsiveModalContext.Provider>
    );
  }

  return (
    <ResponsiveModalContext.Provider value="mobile">
      <VaulDrawer.Root data-slot="responsive-modal" {...props}>
        {children}
      </VaulDrawer.Root>
    </ResponsiveModalContext.Provider>
  );
}

function ResponsiveModalTrigger(
  props: React.ComponentProps<typeof DialogPrimitive.Trigger>,
) {
  const variant = useVariant();
  if (variant === "desktop") {
    return <DialogPrimitive.Trigger data-slot="responsive-modal-trigger" {...props} />;
  }
  return <VaulDrawer.Trigger data-slot="responsive-modal-trigger" {...props} />;
}

function ResponsiveModalClose(
  props: React.ComponentProps<typeof DialogPrimitive.Close>,
) {
  const variant = useVariant();
  if (variant === "desktop") {
    return <DialogPrimitive.Close data-slot="responsive-modal-close" {...props} />;
  }
  return <VaulDrawer.Close data-slot="responsive-modal-close" {...props} />;
}

function ResponsiveModalPortal(
  props: React.ComponentProps<typeof DialogPrimitive.Portal>,
) {
  const variant = useVariant();
  if (variant === "desktop") {
    return <DialogPrimitive.Portal data-slot="responsive-modal-portal" {...props} />;
  }
  return <VaulDrawer.Portal data-slot="responsive-modal-portal" {...props} />;
}

function ResponsiveModalOverlay({
  className,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Overlay>) {
  const variant = useVariant();
  if (variant === "desktop") {
    return (
      <DialogPrimitive.Overlay
        data-slot="responsive-modal-overlay"
        className={cn(
          "fixed inset-0 isolate z-50 bg-black/10 duration-100 supports-backdrop-filter:backdrop-blur-xs",
          "data-[state=open]:animate-in data-[state=open]:fade-in-0",
          "data-[state=closed]:animate-out data-[state=closed]:fade-out-0",
          "motion-reduce:animate-none motion-reduce:transition-none",
          className,
        )}
        {...props}
      />
    );
  }
  return (
    <VaulDrawer.Overlay
      data-slot="responsive-modal-overlay"
      className={cn(
        "fixed inset-0 z-50 bg-black/40 motion-reduce:transition-none",
        className,
      )}
      {...props}
    />
  );
}

interface ResponsiveModalContentProps
  extends React.ComponentProps<typeof DialogPrimitive.Content> {
  showCloseButton?: boolean;
  /**
   * On mobile, render the drag handle at the top of the sheet. Defaults to
   * true. Set false for content that should not feel dismissible (e.g. a
   * required-acknowledgement step).
   */
  showDragHandle?: boolean;
}

function ResponsiveModalContent({
  className,
  children,
  showCloseButton = true,
  showDragHandle = true,
  ...props
}: ResponsiveModalContentProps) {
  const variant = useVariant();

  if (variant === "desktop") {
    return (
      <ResponsiveModalPortal>
        <ResponsiveModalOverlay />
        <DialogPrimitive.Content
          data-slot="responsive-modal-content"
          className={cn(
            "fixed top-1/2 left-1/2 z-50 grid w-full max-w-[calc(100%-2rem)] -translate-x-1/2 -translate-y-1/2 gap-6 rounded-xl bg-popover p-6 text-sm text-popover-foreground ring-1 ring-foreground/10 duration-100 outline-none sm:max-w-md",
            "data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95",
            "data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95",
            "motion-reduce:animate-none motion-reduce:transition-none",
            className,
          )}
          {...props}
        >
          {children}
          {showCloseButton && (
            <DialogPrimitive.Close data-slot="responsive-modal-close" asChild>
              <Button
                variant="ghost"
                className="absolute top-4 right-4"
                size="icon-sm"
              >
                <XIcon />
                <span className="sr-only">Close</span>
              </Button>
            </DialogPrimitive.Close>
          )}
        </DialogPrimitive.Content>
      </ResponsiveModalPortal>
    );
  }

  return (
    <ResponsiveModalPortal>
      <ResponsiveModalOverlay />
      <VaulDrawer.Content
        data-slot="responsive-modal-content"
        className={cn(
          "fixed inset-x-0 bottom-0 z-50 mt-24 flex max-h-[90dvh] flex-col rounded-t-xl bg-popover text-popover-foreground ring-1 ring-foreground/10 outline-none",
          "motion-reduce:transition-none",
          className,
        )}
        {...props}
      >
        {showDragHandle ? (
          <div
            aria-hidden
            className="mx-auto mt-2 mb-1 h-1.5 w-12 shrink-0 rounded-full bg-muted-foreground/40"
          />
        ) : null}
        <div className="flex min-h-0 flex-1 flex-col gap-6 overflow-y-auto p-6 pt-4">
          {children}
        </div>
      </VaulDrawer.Content>
    </ResponsiveModalPortal>
  );
}

function ResponsiveModalHeader({
  className,
  ...props
}: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="responsive-modal-header"
      className={cn("flex flex-col gap-2", className)}
      {...props}
    />
  );
}

function ResponsiveModalFooter({
  className,
  showCloseButton = false,
  children,
  ...props
}: React.ComponentProps<"div"> & { showCloseButton?: boolean }) {
  return (
    <div
      data-slot="responsive-modal-footer"
      className={cn(
        "flex flex-col-reverse gap-2 sm:flex-row sm:justify-end",
        className,
      )}
      {...props}
    >
      {children}
      {showCloseButton && (
        <ResponsiveModalClose asChild>
          <Button variant="outline">Close</Button>
        </ResponsiveModalClose>
      )}
    </div>
  );
}

function ResponsiveModalTitle({
  className,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Title>) {
  const variant = useVariant();
  if (variant === "desktop") {
    return (
      <DialogPrimitive.Title
        data-slot="responsive-modal-title"
        className={cn("font-heading leading-none font-medium", className)}
        {...props}
      />
    );
  }
  return (
    <VaulDrawer.Title
      data-slot="responsive-modal-title"
      className={cn("font-heading leading-none font-medium", className)}
      {...props}
    />
  );
}

function ResponsiveModalDescription({
  className,
  ...props
}: React.ComponentProps<typeof DialogPrimitive.Description>) {
  const variant = useVariant();
  if (variant === "desktop") {
    return (
      <DialogPrimitive.Description
        data-slot="responsive-modal-description"
        className={cn(
          "text-sm text-muted-foreground *:[a]:underline *:[a]:underline-offset-3 *:[a]:hover:text-foreground",
          className,
        )}
        {...props}
      />
    );
  }
  return (
    <VaulDrawer.Description
      data-slot="responsive-modal-description"
      className={cn(
        "text-sm text-muted-foreground *:[a]:underline *:[a]:underline-offset-3 *:[a]:hover:text-foreground",
        className,
      )}
      {...props}
    />
  );
}

export {
  ResponsiveModal,
  ResponsiveModalClose,
  ResponsiveModalContent,
  ResponsiveModalDescription,
  ResponsiveModalFooter,
  ResponsiveModalHeader,
  ResponsiveModalOverlay,
  ResponsiveModalPortal,
  ResponsiveModalTitle,
  ResponsiveModalTrigger,
};

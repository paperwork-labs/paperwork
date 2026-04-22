import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Lock } from 'lucide-react';
import hotToast from 'react-hot-toast';

type UpgradePromptEvent = {
  message?: string;
  path?: string | null;
};

// Custom toast rendered so the "View plans" CTA navigates via SPA route
// instead of forcing the user to copy/paste a URL. react-hot-toast's
// `icon`-string API is insufficient for an embedded link, so we use the
// render-function form instead.
export const useUpgradePrompt = (): void => {
  useEffect(() => {
    const handler = (event: Event) => {
      const detail = (event as CustomEvent<UpgradePromptEvent>).detail;
      const message = detail?.message ?? 'This action requires a higher tier.';

      hotToast.custom(
        (t) =>
          React.createElement(
            'div',
            {
              className:
                'flex items-start gap-3 rounded-md border border-border bg-background p-3 text-sm shadow-lg ring-1 ring-foreground/5',
              role: 'status',
              'aria-live': 'polite',
            },
            React.createElement(Lock, {
              className: 'mt-0.5 size-4 text-[rgb(var(--status-warning)/1)]',
              'aria-hidden': true,
            }),
            React.createElement(
              'div',
              { className: 'flex flex-col gap-2' },
              React.createElement('span', { className: 'text-foreground' }, message),
              React.createElement(
                'div',
                { className: 'flex items-center gap-2' },
                React.createElement(
                  Link,
                  {
                    to: '/pricing',
                    className:
                      'rounded-md bg-primary px-2 py-1 text-xs font-medium text-primary-foreground hover:bg-primary/90',
                    onClick: () => hotToast.dismiss(t.id),
                  },
                  'View plans',
                ),
                React.createElement(
                  'button',
                  {
                    type: 'button',
                    className: 'text-xs text-muted-foreground hover:text-foreground',
                    onClick: () => hotToast.dismiss(t.id),
                  },
                  'Dismiss',
                ),
              ),
            ),
          ),
        { duration: 6000 },
      );
    };
    window.addEventListener('billing:upgrade-required', handler);
    return () => window.removeEventListener('billing:upgrade-required', handler);
  }, []);
};

export default useUpgradePrompt;

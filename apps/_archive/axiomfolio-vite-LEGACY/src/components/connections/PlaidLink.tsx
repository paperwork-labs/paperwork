/**
 * PlaidLink — Button wrapping the Plaid Link SDK for the
 * `broker.plaid_investments` Pro-tier feature.
 *
 * Flow:
 *
 *   1. Mint a link_token via POST /plaid/link_token (mutation #1).
 *   2. Pass the link_token to <usePlaidLink>.
 *   3. When the user finishes Link, call POST /plaid/exchange
 *      with the returned public_token (mutation #2).
 *   4. Invalidate the TanStack Query caches the rest of the app
 *      reads from (`['accounts']`, `['portfolio']`,
 *      `['connectionsHealth']`, `['plaidConnections']`) so the tile
 *      flips to "Connected" and the Overview tab shows the new
 *      positions after the next sync.
 *
 * Explicit states (per `.cursor/rules/no-silent-fallback.mdc`):
 *
 *   - idle        — button visible with "Connect with Plaid"
 *   - preparing   — link_token mutation in-flight
 *   - link-ready  — Plaid Link SDK ready; user in modal
 *   - exchanging  — public_token exchange in-flight
 *   - success     — cache invalidation queued; brief confirmation
 *   - error       — non-blank error message with retry
 *
 * We never render "$0.00" for aggregator-sourced holdings: cost basis
 * is absent from Plaid. Downstream tables display "—" with a tooltip.
 */

import React from 'react';
import { usePlaidLink } from 'react-plaid-link';
import type {
  PlaidLinkOnSuccess,
  PlaidLinkOnSuccessMetadata,
  PlaidLinkOnExit,
  PlaidLinkError,
  PlaidLinkOnExitMetadata,
} from 'react-plaid-link';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { AlertCircle, CheckCircle2, Loader2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { plaidApi } from '@/services/plaid';

export type PlaidLinkStatus =
  | 'idle'
  | 'preparing'
  | 'link-ready'
  | 'exchanging'
  | 'success'
  | 'error';

export interface PlaidLinkProps {
  /** Optional label override (e.g. "Reconnect" for stale state). */
  label?: string;
  /** Called after a successful exchange, after cache invalidation. */
  onConnected?: (connectionId: number, institutionName: string) => void;
  /** Optional analytics handler — called on each status transition. */
  onStatusChange?: (status: PlaidLinkStatus) => void;
  /** When true, the button is disabled (e.g. feature not configured). */
  disabled?: boolean;
}

/**
 * Invalidate every cache key the user-facing portfolio surface reads
 * after a successful Plaid link. Keeping this list short-but-complete
 * matters: a silent miss here is exactly the class of bug
 * `no-silent-fallback.mdc` targets — the user would click "Connect",
 * see no accounts, and conclude the product is broken.
 */
function cacheKeysToInvalidate(): readonly string[] {
  return [
    'accounts',
    'portfolio',
    'connectionsHealth',
    'plaidConnections',
    'brokerAccounts',
  ] as const;
}

const PlaidLink: React.FC<PlaidLinkProps> = ({
  label,
  onConnected,
  onStatusChange,
  disabled,
}) => {
  const queryClient = useQueryClient();

  const [status, setStatus] = React.useState<PlaidLinkStatus>('idle');
  const [errorMessage, setErrorMessage] = React.useState<string | null>(null);
  const [linkToken, setLinkToken] = React.useState<string | null>(null);

  const updateStatus = React.useCallback(
    (next: PlaidLinkStatus) => {
      setStatus(next);
      onStatusChange?.(next);
    },
    [onStatusChange],
  );

  const linkTokenMutation = useMutation({
    mutationFn: async () => plaidApi.createLinkToken(),
    onMutate: () => {
      setErrorMessage(null);
      updateStatus('preparing');
    },
    onSuccess: (data) => {
      setLinkToken(data.link_token);
      updateStatus('link-ready');
    },
    onError: (err: unknown) => {
      const detail = extractErrorMessage(
        err,
        'Could not start Plaid Link. Please try again.',
      );
      setErrorMessage(detail);
      updateStatus('error');
    },
  });

  const exchangeMutation = useMutation({
    mutationFn: async (args: {
      public_token: string;
      metadata: Record<string, unknown>;
    }) => plaidApi.exchangePublicToken(args),
    onMutate: () => {
      updateStatus('exchanging');
    },
    onSuccess: async (data) => {
      await Promise.all(
        cacheKeysToInvalidate().map((key) =>
          queryClient.invalidateQueries({ queryKey: [key] }),
        ),
      );
      updateStatus('success');
      setLinkToken(null);
      onConnected?.(data.connection_id, data.institution_name);
    },
    onError: (err: unknown) => {
      const detail = extractErrorMessage(
        err,
        'Plaid linked your account but we could not save it. Please retry.',
      );
      setErrorMessage(detail);
      updateStatus('error');
    },
  });

  const onSuccess: PlaidLinkOnSuccess = React.useCallback(
    (publicToken: string, metadata: PlaidLinkOnSuccessMetadata) => {
      exchangeMutation.mutate({
        public_token: publicToken,
        metadata: metadata as unknown as Record<string, unknown>,
      });
    },
    [exchangeMutation],
  );

  const onExit: PlaidLinkOnExit = React.useCallback(
    (
      plaidError: PlaidLinkError | null,
      _metadata: PlaidLinkOnExitMetadata,
    ) => {
      // User closed the modal without completing link. If they hit an
      // actual error (not a benign cancel), surface it — do NOT swallow.
      if (plaidError) {
        setErrorMessage(
          plaidError.display_message ||
            plaidError.error_message ||
            'Plaid Link was cancelled due to an error.',
        );
        updateStatus('error');
        return;
      }
      setLinkToken(null);
      updateStatus('idle');
    },
    [updateStatus],
  );

  const { open, ready } = usePlaidLink({
    token: linkToken,
    onSuccess,
    onExit,
  });

  // Auto-open Link once the SDK reports ready with a fresh token. This
  // is the documented pattern from plaid.com/docs/link.
  React.useEffect(() => {
    if (status === 'link-ready' && ready && linkToken) {
      open();
    }
  }, [status, ready, linkToken, open]);

  const handleClick = () => {
    if (status === 'preparing' || status === 'exchanging') return;
    linkTokenMutation.mutate();
  };

  const isBusy = status === 'preparing' || status === 'exchanging';

  const buttonLabel = (() => {
    if (status === 'preparing') return 'Preparing Plaid…';
    if (status === 'exchanging') return 'Saving connection…';
    if (status === 'success') return 'Connected';
    return label ?? 'Connect with Plaid';
  })();

  return (
    <div className="flex flex-col gap-2">
      <Button
        type="button"
        onClick={handleClick}
        disabled={disabled || isBusy}
        aria-busy={isBusy}
        aria-label={buttonLabel}
      >
        {isBusy ? (
          <Loader2 className="mr-2 size-4 animate-spin" aria-hidden />
        ) : status === 'success' ? (
          <CheckCircle2
            className="mr-2 size-4 text-emerald-600"
            aria-hidden
          />
        ) : null}
        {buttonLabel}
      </Button>
      {status === 'error' && errorMessage ? (
        <div
          role="alert"
          className="flex flex-row items-start gap-2 text-sm text-destructive"
        >
          <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden />
          <span>{errorMessage}</span>
        </div>
      ) : null}
    </div>
  );
};

/**
 * Pull a human-readable message out of a TanStack Query error without
 * leaking PII, access tokens, or internal SQL. We accept axios-style
 * `response.data.detail` first, then generic Error.message.
 */
function extractErrorMessage(err: unknown, fallback: string): string {
  if (err == null) return fallback;
  const anyErr = err as {
    response?: { data?: { detail?: unknown; message?: unknown } };
    message?: unknown;
  };
  const detail = anyErr.response?.data?.detail;
  if (typeof detail === 'string' && detail.trim().length > 0) {
    return detail;
  }
  if (detail && typeof detail === 'object') {
    const displayMessage = (detail as { display_message?: unknown })
      .display_message;
    if (typeof displayMessage === 'string' && displayMessage.trim().length > 0) {
      return displayMessage;
    }
    const errorMessage = (detail as { error?: unknown }).error;
    if (typeof errorMessage === 'string' && errorMessage.trim().length > 0) {
      return errorMessage;
    }
  }
  const message = (anyErr as { message?: unknown }).message;
  if (typeof message === 'string' && message.trim().length > 0) {
    return message;
  }
  return fallback;
}

export default PlaidLink;

import { useCallback } from 'react';

type StatusResponse = {
  job_state?: string;
  connected?: boolean;
  job_error?: string;
  last_error?: string;
  accounts?: unknown[];
};

export interface UseConnectJobPollOptions {
  /** Initial poll interval in ms (default 1000). Grows via exponential backoff. */
  initialIntervalMs?: number;
  /** Max interval between polls in ms (default 5000). */
  maxIntervalMs?: number;
  /** Max total polling duration in ms (default 60000 = 60s). */
  maxDurationMs?: number;
}

export interface UseConnectJobPollResult {
  poll: (
    jobId: string,
    statusApi: (jobId?: string) => Promise<StatusResponse>,
    options?: { isIbkr?: boolean }
  ) => Promise<{ success: boolean; error?: string }>;
}

/**
 * Polls a connect job status API until success, error, or timeout.
 * Uses exponential backoff: 1s -> 1.5s -> 2.25s -> ... capped at maxIntervalMs.
 */
export function useConnectJobPoll(
  options: UseConnectJobPollOptions = {}
): UseConnectJobPollResult {
  const {
    initialIntervalMs = 1000,
    maxIntervalMs = 5000,
    maxDurationMs = 60_000,
  } = options;

  const poll = useCallback(
    async (
      jobId: string,
      statusApi: (jobId?: string) => Promise<StatusResponse>,
      opts?: { isIbkr?: boolean }
    ): Promise<{ success: boolean; error?: string }> => {
      const startTime = Date.now();
      let interval = initialIntervalMs;

      while (Date.now() - startTime < maxDurationMs) {
        try {
          const st = await statusApi(jobId);
          if (st?.job_state === 'success' || st?.connected) {
            return { success: true };
          }
          if (opts?.isIbkr && (Array.isArray(st?.accounts) && st.accounts.length > 0)) {
            return { success: true };
          }
          if (st?.job_state === 'error') {
            const errMsg = st?.job_error || st?.last_error || 'Connection failed';
            return { success: false, error: errMsg };
          }
        } catch (e) {
          const errMsg = e instanceof Error ? e.message : String(e);
          return { success: false, error: errMsg };
        }
        await new Promise((r) => setTimeout(r, interval));
        interval = Math.min(interval * 1.5, maxIntervalMs);
      }
      return { success: false, error: 'Connection timed out' };
    },
    [initialIntervalMs, maxIntervalMs, maxDurationMs]
  );

  return { poll };
}

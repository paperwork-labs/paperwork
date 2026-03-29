/**
 * Retry helpers for portal automation — transient network/UI flakes.
 */

export interface RetryOptions {
  maxRetries: number;
  baseDelayMs: number;
  maxDelayMs: number;
}

const DEFAULT_RETRY_OPTIONS: RetryOptions = {
  maxRetries: 3,
  baseDelayMs: 500,
  maxDelayMs: 30_000,
};

export function sleep(ms: number): Promise<void> {
  if (!Number.isFinite(ms) || ms < 0) {
    throw new RangeError(`sleep: ms must be a non-negative finite number, got ${ms}`);
  }
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

/**
 * Runs `fn` until it succeeds or `maxRetries` retries are exhausted.
 * Total attempts = 1 + maxRetries (first try plus retries).
 */
export async function withRetry<T>(
  fn: () => Promise<T>,
  options?: Partial<RetryOptions>
): Promise<T> {
  const opts: RetryOptions = { ...DEFAULT_RETRY_OPTIONS, ...options };

  if (opts.maxRetries < 0 || !Number.isInteger(opts.maxRetries)) {
    throw new RangeError(
      `withRetry: maxRetries must be a non-negative integer, got ${opts.maxRetries}`
    );
  }
  if (opts.baseDelayMs < 0 || !Number.isFinite(opts.baseDelayMs)) {
    throw new RangeError(
      `withRetry: baseDelayMs must be non-negative finite, got ${opts.baseDelayMs}`
    );
  }
  if (opts.maxDelayMs < opts.baseDelayMs || !Number.isFinite(opts.maxDelayMs)) {
    throw new RangeError(
      `withRetry: maxDelayMs must be >= baseDelayMs and finite, got ${opts.maxDelayMs}`
    );
  }

  let lastError: unknown;

  for (let attempt = 0; attempt <= opts.maxRetries; attempt += 1) {
    try {
      return await fn();
    } catch (error) {
      lastError = error;
      if (attempt === opts.maxRetries) {
        break;
      }
      const backoff = Math.min(
        opts.baseDelayMs * 2 ** attempt,
        opts.maxDelayMs
      );
      await sleep(backoff);
    }
  }

  if (lastError instanceof Error) {
    const wrapped = new Error(
      `withRetry: failed after ${opts.maxRetries + 1} attempt(s): ${lastError.message}`
    );
    wrapped.cause = lastError;
    throw wrapped;
  }

  throw new Error(
    `withRetry: failed after ${opts.maxRetries + 1} attempt(s): ${String(lastError)}`
  );
}

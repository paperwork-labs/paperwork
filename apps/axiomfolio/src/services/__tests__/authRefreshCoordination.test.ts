import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  readRecentBroadcastToken,
  releaseRefreshLock,
  resetAuthRefreshCoordinationForTests,
  tryAcquireRefreshLock,
} from '../authRefreshCoordination';

describe('authRefreshCoordination', () => {
  afterEach(() => {
    resetAuthRefreshCoordinationForTests();
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it('tryAcquireRefreshLock allows same tab to re-acquire', () => {
    expect(tryAcquireRefreshLock(15_000)).toBe(true);
    expect(tryAcquireRefreshLock(15_000)).toBe(true);
    releaseRefreshLock();
  });

  it('readRecentBroadcastToken returns fresh token payload', () => {
    const token = 'abc123';
    localStorage.setItem(
      'axiomfolio_auth_refresh_token_v1',
      JSON.stringify({ accessToken: token, t: Date.now(), nonce: 0.1 }),
    );
    expect(readRecentBroadcastToken(5_000)).toBe(token);
  });

  it('readRecentBroadcastToken ignores stale payloads', () => {
    localStorage.setItem(
      'axiomfolio_auth_refresh_token_v1',
      JSON.stringify({ accessToken: 'old', t: Date.now() - 10_000, nonce: 0.2 }),
    );
    expect(readRecentBroadcastToken(4_000)).toBeNull();
  });
});

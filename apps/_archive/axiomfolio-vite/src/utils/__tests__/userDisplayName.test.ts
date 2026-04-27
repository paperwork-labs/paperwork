import { describe, it, expect } from 'vitest';

import { formatUserDisplayName } from '../userDisplayName';

describe('formatUserDisplayName', () => {
  it('returns Guest for null', () => {
    expect(formatUserDisplayName(null)).toBe('Guest');
  });

  it('preserves casing and spacing of full_name (no title case)', () => {
    expect(
      formatUserDisplayName({
        full_name: '  mcDonald ',
        username: 'ignored',
      }),
    ).toBe('mcDonald');
  });

  it('falls back to username when full_name is empty', () => {
    expect(
      formatUserDisplayName({
        full_name: '   ',
        username: 'de_la_Rosa',
      }),
    ).toBe('de_la_Rosa');
  });

  it('trims only', () => {
    expect(formatUserDisplayName({ full_name: '  Anne-Marie  ', username: 'x' })).toBe('Anne-Marie');
  });
});

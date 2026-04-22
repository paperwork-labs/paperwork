import * as React from 'react';

import { cn } from '@/lib/utils';

interface PasswordStrengthMeterProps {
  password: string;
}

interface PasswordChecks {
  length: boolean;
  mixedCase: boolean;
  digitOrSymbol: boolean;
}

const evaluatePassword = (value: string): PasswordChecks => ({
  length: value.length >= 8,
  mixedCase: /[a-z]/.test(value) && /[A-Z]/.test(value),
  digitOrSymbol: /[0-9]/.test(value) || /[^A-Za-z0-9]/.test(value),
});

/** 0 = too short (under 8 chars); 1–3 = weak through strong once length is met. */
export function computePasswordStrengthScore(value: string): number {
  if (value.length < 8) {
    return 0;
  }
  const checks = evaluatePassword(value);
  return Object.values(checks).filter(Boolean).length;
}

const STRENGTH_META: ReadonlyArray<{
  label: string;
  barClass: string;
  textClass: string;
}> = [
  { label: 'Too short', barClass: 'bg-muted', textClass: 'text-muted-foreground' },
  { label: 'Weak', barClass: 'bg-[rgb(var(--status-danger))]', textClass: 'text-[rgb(var(--status-danger)/1)]' },
  { label: 'Okay', barClass: 'bg-[rgb(var(--status-warning))]', textClass: 'text-[rgb(var(--status-warning)/1)]' },
  { label: 'Strong', barClass: 'bg-[rgb(var(--status-success))]', textClass: 'text-[rgb(var(--status-success)/1)]' },
];

const A11Y_DEBOUNCE_MS = 300;

export const PasswordStrengthMeter: React.FC<PasswordStrengthMeterProps> = ({ password }) => {
  const score = computePasswordStrengthScore(password);
  const meta = STRENGTH_META[score];

  const [debouncedPassword, setDebouncedPassword] = React.useState('');
  React.useEffect(() => {
    if (password.length === 0) {
      setDebouncedPassword('');
      return;
    }
    const id = window.setTimeout(() => setDebouncedPassword(password), A11Y_DEBOUNCE_MS);
    return () => window.clearTimeout(id);
  }, [password]);

  const announce = debouncedPassword.length > 0;
  const ariaScore = computePasswordStrengthScore(debouncedPassword);
  const ariaMeta = STRENGTH_META[ariaScore];

  return (
    <div
      className="mt-1.5 flex flex-col gap-1"
      role={announce ? 'status' : undefined}
      aria-live={announce ? 'polite' : 'off'}
      aria-label={announce ? `Password strength: ${ariaMeta.label}` : undefined}
    >
      <div className="flex gap-1" aria-hidden>
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className={cn(
              'h-1 flex-1 rounded-full transition-colors',
              i < score ? meta.barClass : 'bg-muted',
            )}
          />
        ))}
      </div>
      {password ? (
        <p className={cn('text-xs', meta.textClass)}>
          {meta.label}
          {score < 3 ? (
            <span className="text-muted-foreground">
              {' '}· aim for 8+ chars, mixed case, and a number or symbol
            </span>
          ) : null}
        </p>
      ) : null}
    </div>
  );
};

export default PasswordStrengthMeter;

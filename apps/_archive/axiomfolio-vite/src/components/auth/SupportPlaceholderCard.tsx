import * as React from 'react';
import AppCard from '@/components/ui/AppCard';
import { Button } from '@/components/ui/button';
import { Check } from 'lucide-react';
import { SUPPORT } from '@/constants/support';

export interface SupportPlaceholderCardProps {
  title: string;
  message: string;
  copyLabel?: string;
}

export const SupportPlaceholderCard: React.FC<SupportPlaceholderCardProps> = ({
  title,
  message,
  copyLabel = 'Copy email address',
}) => {
  const [copied, setCopied] = React.useState(false);
  const timeoutRef = React.useRef<number | null>(null);

  React.useEffect(() => {
    return () => {
      if (timeoutRef.current !== null) {
        window.clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
    };
  }, []);

  const handleCopy = React.useCallback(async () => {
    try {
      await navigator.clipboard.writeText(SUPPORT);
      setCopied(true);
      if (timeoutRef.current !== null) {
        window.clearTimeout(timeoutRef.current);
      }
      timeoutRef.current = window.setTimeout(() => {
        setCopied(false);
        timeoutRef.current = null;
      }, 2000);
    } catch {
      // Clipboard may be unavailable; address is still visible above.
    }
  }, []);

  return (
    <AppCard>
      <h1 className="text-center font-heading text-lg font-semibold text-foreground">{title}</h1>
      <p className="mt-3 text-center text-sm text-muted-foreground">
        {message} — email {SUPPORT}
      </p>
      <div className="mt-4 flex justify-center">
        <Button type="button" variant="secondary" onClick={handleCopy}>
          {copied ? (
            <>
              <Check className="mr-2 size-4" aria-hidden />
              Copied
            </>
          ) : (
            copyLabel
          )}
        </Button>
      </div>
    </AppCard>
  );
};

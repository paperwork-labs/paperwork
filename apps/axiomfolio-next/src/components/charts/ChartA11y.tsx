/**
 * `ChartAnnouncer` — visually-hidden ARIA live region for chart hover state.
 *
 * Charts are largely useless to screen-reader users without a textual
 * counterpart. Mount this once per chart and update `summary` whenever
 * the hovered point changes (e.g. "AAPL closed at $192.34 on Mar 14, up
 * 2.1% on the day"). We throttle so high-frequency mouse moves don't
 * spam the user — last summary in each window wins.
 */
import * as React from "react";

export interface ChartAnnouncerProps {
  summary: string;
  /** Throttle window in ms. Default 500. */
  throttleMs?: number;
}

export function ChartAnnouncer({
  summary,
  throttleMs = 500,
}: ChartAnnouncerProps) {
  const [visible, setVisible] = React.useState<string>(summary);
  const pendingRef = React.useRef<string>(summary);
  const lastFlushRef = React.useRef<number>(0);
  const timerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);

  React.useEffect(() => {
    pendingRef.current = summary;
    const now = Date.now();
    const elapsed = now - lastFlushRef.current;

    const flush = () => {
      lastFlushRef.current = Date.now();
      setVisible(pendingRef.current);
      timerRef.current = null;
    };

    if (elapsed >= throttleMs) {
      flush();
      return;
    }
    if (timerRef.current === null) {
      timerRef.current = setTimeout(flush, throttleMs - elapsed);
    }
  }, [summary, throttleMs]);

  React.useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  return (
    <div
      className="sr-only-live"
      role="status"
      aria-live="polite"
      aria-atomic="true"
      data-testid="chart-announcer"
    >
      {visible}
    </div>
  );
}

export default ChartAnnouncer;

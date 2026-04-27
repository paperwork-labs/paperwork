/** Shared styling for pick / candidate action chips (published feed + admin queue). */

export function actionChipClass(action: string): string {
  const a = action.toUpperCase();
  if (a === 'BUY' || a === 'ADD') return 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300';
  if (a === 'SELL' || a === 'EXIT') return 'bg-destructive/15 text-destructive';
  if (a === 'TRIM') return 'bg-amber-500/15 text-amber-800 dark:text-amber-200';
  if (a === 'HOLD') return 'bg-muted text-muted-foreground';
  return 'bg-secondary text-secondary-foreground';
}

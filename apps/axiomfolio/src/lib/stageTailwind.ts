/**
 * Tailwind classes referencing --palette-stage-* in index.css.
 * Keep keys as full literal strings so Tailwind can statically detect them.
 */
export const STAGE_SUBTLE_BADGE: Record<string, string> = {
  gray: 'border-transparent bg-[rgb(var(--palette-stage-gray)/0.15)] text-[rgb(var(--palette-stage-gray))]',
  green:
    'border-transparent bg-[rgb(var(--palette-stage-green)/0.15)] text-[rgb(var(--palette-stage-green))]',
  yellow:
    'border-transparent bg-[rgb(var(--palette-stage-yellow)/0.15)] text-[rgb(var(--palette-stage-yellow))]',
  orange:
    'border-transparent bg-[rgb(var(--palette-stage-orange)/0.15)] text-[rgb(var(--palette-stage-orange))]',
  red: 'border-transparent bg-[rgb(var(--palette-stage-red)/0.15)] text-[rgb(var(--palette-stage-red))]',
};

export const STAGE_SOLID_BADGE: Record<string, string> = {
  gray: 'border-transparent bg-[rgb(var(--palette-stage-gray))] text-white',
  green: 'border-transparent bg-[rgb(var(--palette-stage-green))] text-white',
  yellow: 'border-transparent bg-[rgb(var(--palette-stage-yellow))] text-white',
  orange: 'border-transparent bg-[rgb(var(--palette-stage-orange))] text-white',
  red: 'border-transparent bg-[rgb(var(--palette-stage-red))] text-white',
};

export const STAGE_BAR_FILL: Record<string, string> = {
  gray: 'bg-[rgb(var(--palette-stage-gray))]',
  green: 'bg-[rgb(var(--palette-stage-green))]',
  yellow: 'bg-[rgb(var(--palette-stage-yellow))]',
  orange: 'bg-[rgb(var(--palette-stage-orange))]',
  red: 'bg-[rgb(var(--palette-stage-red))]',
};

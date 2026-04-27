/**
 * Interim parent mark: continuous wire paperclip — slate with one amber segment.
 * Replace with final SVG from docs/brand/PROMPTS.md when the AI mark is retraced.
 */
export function PaperclipMark({ className = "" }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 128 128"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden
    >
      <path
        d="M38 44 L38 84 Q38 96 50 96 L78 96 Q90 96 90 84 L90 52 Q90 40 78 40 L50 40 Q38 40 38 52 L38 72"
        stroke="#F8FAFC"
        strokeWidth="10"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M62 40 L62 84 Q62 96 74 96"
        stroke="#F59E0B"
        strokeWidth="10"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

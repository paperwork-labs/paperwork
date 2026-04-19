/** Display keyboard shortcut parts for shortcut overlay (best-effort OS detection). */
export function formatShortcutParts(parts: string[] | undefined): string {
  if (!parts?.length) return '';
  const isMac =
    typeof navigator !== 'undefined' && /Mac|iPhone|iPod|iPad/i.test(navigator.userAgent);
  const mapped = parts.map((p) => {
    if (p === 'mod') return isMac ? '⌘' : 'Ctrl';
    if (p === 'shift') return '⇧';
    if (p === 'alt') return isMac ? '⌥' : 'Alt';
    if (p.length === 1) return p.toUpperCase();
    return p;
  });
  return isMac ? mapped.join('') : mapped.join('+');
}

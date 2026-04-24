/**
 * Opens or toggles the global command palette by synthesizing the same
 * Cmd/Ctrl+K keydown the CommandPalette component listens for.
 */
export function openCommandPalette(): void {
  const isMac =
    typeof navigator !== 'undefined' && /Mac|iPhone|iPad|iPod/.test(navigator.userAgent);
  window.dispatchEvent(
    new KeyboardEvent('keydown', {
      key: 'k',
      code: 'KeyK',
      metaKey: isMac,
      ctrlKey: !isMac,
      bubbles: true,
      cancelable: true,
    })
  );
}

import * as React from 'react';
import { CommandPalette, isTypingTarget } from '@/components/cmdk/CommandPalette';
import { ShortcutOverlay } from '@/components/cmdk/ShortcutOverlay';
import { registerDefaultCommandActions } from '@/components/cmdk/registerDefaultCommandActions';
import { useColorMode } from '@/theme/colorMode';

/**
 * Global command palette + shortcut overlay. Lives under `BrowserRouter`.
 */
export function AppCommandLayer() {
  const { toggleColorMode } = useColorMode();
  const [paletteOpen, setPaletteOpen] = React.useState(false);
  const [shortcutOpen, setShortcutOpen] = React.useState(false);

  React.useEffect(() => {
    return registerDefaultCommandActions({ toggleColorMode });
  }, [toggleColorMode]);

  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.key !== '?') return;
      if (isTypingTarget(e.target)) return;
      e.preventDefault();
      setShortcutOpen(true);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  return (
    <>
      <CommandPalette
        open={paletteOpen}
        onOpenChange={setPaletteOpen}
        onRequestShortcutOverlay={() => setShortcutOpen(true)}
      />
      <ShortcutOverlay open={shortcutOpen} onOpenChange={setShortcutOpen} />
    </>
  );
}

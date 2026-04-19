import {
  Briefcase,
  Home,
  Link2,
  Palette,
  ScanSearch,
  Settings,
  Sparkles,
  HelpCircle,
  Scissors,
  Share2,
} from 'lucide-react';
import { actionRegistry } from '@/lib/actions';

export interface RegisterCommandActionsDeps {
  toggleColorMode: () => void;
}

/**
 * Registers baseline palette actions. Call from a component inside Router + ColorModeProvider;
 * invoke the returned cleanup on unmount.
 */
export function registerDefaultCommandActions(deps: RegisterCommandActionsDeps): () => void {
  const { toggleColorMode } = deps;
  const unregister: Array<() => void> = [];

  unregister.push(
    actionRegistry.register({
      id: 'nav.home',
      label: 'Go Home',
      description: 'Market dashboard',
      section: 'navigation',
      icon: Home,
      keywords: ['dashboard', 'market', 'root'],
      run: (ctx) => ctx.navigate('/'),
    })
  );

  unregister.push(
    actionRegistry.register({
      id: 'nav.portfolio',
      label: 'Go Portfolio',
      description: 'Portfolio overview',
      section: 'navigation',
      icon: Briefcase,
      keywords: ['positions', 'account'],
      run: (ctx) => ctx.navigate('/portfolio'),
    })
  );

  unregister.push(
    actionRegistry.register({
      id: 'nav.holdings',
      label: 'Go Holdings',
      description: 'Portfolio holdings',
      section: 'navigation',
      icon: Briefcase,
      keywords: ['positions', 'stocks'],
      run: (ctx) => ctx.navigate('/portfolio/holdings'),
    })
  );

  unregister.push(
    actionRegistry.register({
      id: 'nav.scan',
      label: 'Go Scan',
      description: 'Market scanner',
      section: 'navigation',
      icon: ScanSearch,
      keywords: ['scanner', 'scan', 'market'],
      run: (ctx) => ctx.navigate('/market/scanner'),
    })
  );

  unregister.push(
    actionRegistry.register({
      id: 'nav.picks',
      label: 'Go Picks',
      description: 'Market intelligence & top picks',
      section: 'navigation',
      icon: Sparkles,
      keywords: ['picks', 'intelligence', 'brief', 'ideas'],
      run: (ctx) => ctx.navigate('/market/intelligence'),
    })
  );

  unregister.push(
    actionRegistry.register({
      id: 'nav.settings',
      label: 'Go Settings',
      section: 'navigation',
      icon: Settings,
      keywords: ['preferences', 'profile'],
      run: (ctx) => ctx.navigate('/settings'),
    })
  );

  unregister.push(
    actionRegistry.register({
      id: 'nav.connections',
      label: 'Go Connect Accounts',
      description: 'Broker connections',
      section: 'navigation',
      icon: Link2,
      keywords: ['broker', 'ibkr', 'tastytrade', 'schwab'],
      run: (ctx) => ctx.navigate('/settings/connections'),
    })
  );

  unregister.push(
    actionRegistry.register({
      id: 'settings.toggle-theme',
      label: 'Toggle Dark Mode',
      section: 'settings',
      icon: Palette,
      keywords: ['theme', 'light', 'dark', 'appearance'],
      run: (_ctx) => {
        toggleColorMode();
      },
    })
  );

  unregister.push(
    actionRegistry.register({
      id: 'settings.color-blind',
      label: 'Toggle Color-Blind Palette',
      description: 'Not wired globally yet',
      section: 'settings',
      icon: Palette,
      keywords: ['accessibility', 'a11y', 'colorblind'],
      run: (ctx) => {
        ctx.toast('Color-blind palette toggle is not wired globally yet.');
      },
    })
  );

  unregister.push(
    actionRegistry.register({
      id: 'help.shortcuts',
      label: 'Show Shortcuts',
      description: 'Keyboard shortcut reference',
      section: 'settings',
      icon: HelpCircle,
      shortcut: ['?'],
      keywords: ['help', 'keys', 'keyboard'],
      run: (ctx) => {
        ctx.openShortcutHelp?.();
      },
    })
  );

  unregister.push(
    actionRegistry.register({
      id: 'action.trim',
      label: 'Trim 25%',
      description: 'Reduce a position size (preview)',
      section: 'actions',
      icon: Scissors,
      keywords: ['trim', 'reduce', 'size'],
      run: (ctx) => {
        ctx.toast('Trim actions are coming in a follow-up release.');
      },
    })
  );

  unregister.push(
    actionRegistry.register({
      id: 'action.share-portfolio',
      label: 'Share My Portfolio',
      section: 'actions',
      icon: Share2,
      keywords: ['share', 'export', 'link'],
      run: (ctx) => {
        ctx.toast('Portfolio sharing is coming in a follow-up release.');
      },
    })
  );

  return () => {
    for (const u of unregister) u();
  };
}

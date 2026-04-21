import { useEffect } from 'react';
import hotToast from 'react-hot-toast';

type UpgradePromptEvent = {
  message?: string;
  path?: string | null;
};

export const useUpgradePrompt = (): void => {
  useEffect(() => {
    const handler = (event: Event) => {
      const detail = (event as CustomEvent<UpgradePromptEvent>).detail;
      const message = detail?.message ?? 'This action requires a higher tier.';
      hotToast.error(`${message} Visit /pricing to upgrade.`);
    };
    window.addEventListener('billing:upgrade-required', handler);
    return () => window.removeEventListener('billing:upgrade-required', handler);
  }, []);
};

export default useUpgradePrompt;

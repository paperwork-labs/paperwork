import React from 'react';
import { Box, HStack, VStack, Text, Input, Badge } from '@chakra-ui/react';
import { PageHeader } from '../components/ui/Page';
import AppCard from '../components/ui/AppCard';
import hotToast from 'react-hot-toast';
import { authApi, handleApiError } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { useColorMode } from '../theme/colorMode';

const SELECT_STYLE: React.CSSProperties = {
  width: 280,
  fontSize: 12,
  padding: '8px 10px',
  borderRadius: 10,
  border: '1px solid var(--chakra-colors-border-subtle)',
  background: 'var(--chakra-colors-bg-input)',
  color: 'var(--chakra-colors-fg-default)',
};

type SaveStatus = 'idle' | 'saving' | 'saved' | 'error';

const SettingsPreferences: React.FC = () => {
  const { user, refreshMe } = useAuth();
  const { colorModePreference, setColorModePreference } = useColorMode();

  const [themePref, setThemePref] = React.useState<'system' | 'light' | 'dark'>('system');
  const [tableDensity, setTableDensity] = React.useState<'comfortable' | 'compact'>('comfortable');
  const [timezone, setTimezone] = React.useState<string>(user?.timezone || 'America/Los_Angeles');
  const [currency, setCurrency] = React.useState<string>((user?.currency_preference || 'USD').toUpperCase());
  const [saveStatus, setSaveStatus] = React.useState<SaveStatus>('idle');
  const saveTimeoutRef = React.useRef<ReturnType<typeof setTimeout>>();
  const debounceRef = React.useRef<ReturnType<typeof setTimeout>>();
  const mountedRef = React.useRef(true);

  React.useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  const timezones = React.useMemo<string[]>(() => {
    try {
      const tzs = (Intl as any)?.supportedValuesOf?.('timeZone');
      if (Array.isArray(tzs) && tzs.length) return tzs;
    } catch { /* ignore */ }
    return ['UTC', 'America/New_York', 'America/Chicago', 'America/Los_Angeles', 'Europe/London'];
  }, []);

  // Sync local state from user on mount / external updates
  React.useEffect(() => {
    const pref = user?.ui_preferences?.color_mode_preference;
    if (pref === 'system' || pref === 'light' || pref === 'dark') {
      setThemePref(pref);
    } else {
      setThemePref(colorModePreference);
    }
    const td = user?.ui_preferences?.table_density;
    if (td === 'comfortable' || td === 'compact') setTableDensity(td);
    setTimezone(user?.timezone || 'America/Los_Angeles');
    setCurrency((user?.currency_preference || 'USD').toUpperCase());
  }, [
    user?.timezone,
    user?.currency_preference,
    user?.ui_preferences?.color_mode_preference,
    user?.ui_preferences?.table_density,
    colorModePreference,
  ]);

  const persist = React.useCallback(async (patch: {
    timezone?: string;
    currency_preference?: string;
    ui_preferences?: { color_mode_preference?: string; table_density?: string };
  }) => {
    if (!mountedRef.current) return;
    setSaveStatus('saving');
    clearTimeout(saveTimeoutRef.current);
    try {
      await authApi.updateMe(patch);
      if (patch.ui_preferences?.color_mode_preference) {
        setColorModePreference(patch.ui_preferences.color_mode_preference as 'system' | 'light' | 'dark');
      }
      await refreshMe();
      if (!mountedRef.current) return;
      setSaveStatus('saved');
      saveTimeoutRef.current = setTimeout(() => {
        if (mountedRef.current) setSaveStatus('idle');
      }, 2000);
    } catch (e) {
      if (!mountedRef.current) return;
      setSaveStatus('error');
      hotToast.error(handleApiError(e));
      saveTimeoutRef.current = setTimeout(() => {
        if (mountedRef.current) setSaveStatus('idle');
      }, 3000);
    }
  }, [refreshMe, setColorModePreference]);

  const handleThemeChange = (next: 'system' | 'light' | 'dark') => {
    setThemePref(next);
    setColorModePreference(next); // Apply theme immediately for instant feedback
    void persist({ ui_preferences: { color_mode_preference: next, table_density: tableDensity } });
  };

  const handleDensityChange = (next: 'comfortable' | 'compact') => {
    setTableDensity(next);
    void persist({ ui_preferences: { color_mode_preference: themePref, table_density: next } });
  };

  const handleTimezoneChange = (next: string) => {
    setTimezone(next);
    void persist({ timezone: next });
  };

  const handleCurrencyChange = (raw: string) => {
    const next = raw.toUpperCase();
    setCurrency(next);
    clearTimeout(debounceRef.current);
    if (next.length === 3) {
      debounceRef.current = setTimeout(() => {
        void persist({ currency_preference: next });
      }, 600);
    }
  };

  const statusBadge = saveStatus === 'saving'
    ? <Badge colorPalette="blue" variant="subtle" size="sm">Saving…</Badge>
    : saveStatus === 'saved'
      ? <Badge colorPalette="green" variant="subtle" size="sm">Saved</Badge>
      : saveStatus === 'error'
        ? <Badge colorPalette="red" variant="subtle" size="sm">Error</Badge>
        : null;

  return (
    <Box w="full">
      <Box w="full" maxW="960px" mx="auto">
        <HStack justify="space-between" align="center" mb={0}>
          <PageHeader title="Preferences" subtitle="Changes are saved automatically." />
          {statusBadge && <Box flexShrink={0}>{statusBadge}</Box>}
        </HStack>
        <VStack align="stretch" gap={4}>
          <AppCard>
            <VStack align="stretch" gap={4}>
              <Text fontWeight="semibold">Appearance</Text>
              <Box>
                <Text fontSize="sm" color="fg.muted" mb={2}>Theme</Text>
                <select
                  value={themePref}
                  onChange={(e) => handleThemeChange(e.target.value as 'system' | 'light' | 'dark')}
                  style={SELECT_STYLE}
                >
                  <option value="system">Use system preference</option>
                  <option value="light">Light</option>
                  <option value="dark">Dark</option>
                </select>
              </Box>

              <Box>
                <Text fontSize="sm" color="fg.muted" mb={2}>Table density</Text>
                <select
                  value={tableDensity}
                  onChange={(e) => handleDensityChange(e.target.value as 'comfortable' | 'compact')}
                  style={SELECT_STYLE}
                >
                  <option value="comfortable">Comfortable</option>
                  <option value="compact">Compact</option>
                </select>
              </Box>
            </VStack>
          </AppCard>

          <AppCard>
            <VStack align="stretch" gap={4}>
              <Text fontWeight="semibold">Locale</Text>
              <HStack gap={4} align="start" flexWrap="wrap">
                <Box flex="1" minW={{ base: "100%", md: "320px" }}>
                  <Text fontSize="sm" color="fg.muted" mb={1}>Timezone</Text>
                  <select
                    value={timezone}
                    onChange={(e) => handleTimezoneChange(e.target.value)}
                    style={SELECT_STYLE}
                  >
                    {timezones.map((tz) => (
                      <option key={tz} value={tz}>{tz}</option>
                    ))}
                  </select>
                </Box>
                <Box minW={{ base: "100%", md: "200px" }}>
                  <Text fontSize="sm" color="fg.muted" mb={1}>Currency</Text>
                  <Input
                    value={currency}
                    onChange={(e) => handleCurrencyChange(e.target.value)}
                    placeholder="USD"
                    maxLength={3}
                  />
                  <Text fontSize="xs" color="fg.muted" mt={1}>3-letter code (e.g. USD, EUR, GBP)</Text>
                </Box>
              </HStack>
            </VStack>
          </AppCard>
        </VStack>
      </Box>
    </Box>
  );
};

export default SettingsPreferences;

import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Activity,
  ArrowLeft,
  BarChart2,
  Check,
  Database,
  ExternalLink,
  Link2,
  Loader2,
  Pencil,
  PencilLine,
  Trash2,
  X,
} from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import {
  ResponsiveModal as Dialog,
  ResponsiveModalContent as DialogContent,
  ResponsiveModalDescription as DialogDescription,
  ResponsiveModalFooter as DialogFooter,
  ResponsiveModalHeader as DialogHeader,
  ResponsiveModalTitle as DialogTitle,
} from '@/components/ui/responsive-modal';
import { Input } from '@/components/ui/input';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import AppCard from '../components/ui/AppCard';
import { PageContainer, PageHeader } from '../components/ui/Page';
import { cn } from '@/lib/utils';
import hotToast from 'react-hot-toast';
import { accountsApi, aggregatorApi, handleApiError } from '../services/api';
import api from '../services/api';
import { useConnectJobPoll } from '../hooks/useConnectJobPoll';
import { useAuth } from '../context/AuthContext';
import { useAccountContext } from '../context/AccountContext';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import SchwabLogo from '../assets/logos/schwab.svg';
import TastytradeLogo from '../assets/logos/tastytrade.svg';
import IbkrLogo from '../assets/logos/interactive-brokers.svg';
import EtradeLogo from '../assets/logos/etrade.svg';
import TradierLogo from '../assets/logos/tradier.svg';
import CoinbaseLogo from '../assets/logos/coinbase.svg';
import IBGatewayLogo from '../assets/logos/ib-gateway.svg';
import TradingViewLogo from '../assets/logos/tradingview.svg';
import FmpLogo from '../assets/logos/fmp.svg';
import { formatDateTime, formatRelativeTime } from '../utils/format';
import { useUserPreferences } from '../hooks/useUserPreferences';
import { oauthApi } from '../services/oauth';
import { connectionsApi } from '../services/connectionsHealth';
import { BrokerPickerGrid } from '../components/connections/BrokerPickerGrid';
import { HealthCard } from '../components/connections/HealthCard';
import { FirstRunHero } from '../components/connections/FirstRunHero';
import {
  ConnectionDetailSheet,
  type DetailAccountRow,
} from '../components/connections/ConnectionDetailSheet';
import {
  LIVE_BROKER_TILES,
  type BrokerSlug,
  type BrokerTileDefinition,
  type WizardBrokerKey,
} from '../components/connections/brokerCatalog';

const selectSm =
  'h-8 w-[120px] shrink-0 rounded-md border border-input bg-background px-2 text-xs text-foreground shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 dark:bg-input/30';

const SettingsConnections: React.FC = () => {
  // Temporary shim: preserve legacy `useToast()` call sites while migrating to `react-hot-toast`.
  const toast = (args: { title: string; description?: string; status?: 'success' | 'error' | 'info' | 'warning' }) => {
    const msg = args.description ? `${args.title}: ${args.description}` : args.title;
    if (args.status === 'success') return hotToast.success(args.title);
    if (args.status === 'error') return hotToast.error(msg);
    return hotToast(msg);
  };
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { refetch: refetchGlobalAccounts } = useAccountContext();
  const { timezone } = useUserPreferences();
  const [accounts, setAccounts] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ broker: 'SCHWAB', account_number: '', account_name: '', account_type: 'TAXABLE' });
  const [syncingId, setSyncingId] = useState<number | null>(null);
  const [cfg, setCfg] = useState<{ schwabConfigured: boolean; redirect?: string; schwabProbe?: any } | null>(null);
  const [tt, setTt] = useState<{ connected: boolean; available: boolean; last_error?: string; job_error?: string } | null>(null);
  const [ttForm, setTtForm] = useState({ client_id: '', client_secret: '', refresh_token: '' });
  // Wizard
  const [wizardOpen, setWizardOpen] = useState(false);
  const [step, setStep] = useState<number>(1);
  const [broker, setBroker] = useState<'SCHWAB' | 'TASTYTRADE' | 'IBKR' | 'ETRADE' | 'TRADIER' | 'COINBASE' | ''>('');
  const [schwabForm, setSchwabForm] = useState({ account_number: '', account_name: '' });
  const [ibkrForm, setIbkrForm] = useState({ flex_token: '', query_id: '', account_number: '' });
  // E*TRADE OAuth 1.0a uses an out-of-band verifier code: the user authorizes
  // on E*TRADE's site, E*TRADE displays a ~5-char code, the user pastes it
  // back here. ``state`` is the Redis-stored CSRF token from /initiate.
  const [etradeForm, setEtradeForm] = useState({ state: '', verifier: '', account_name: '' });
  // Tradier OAuth 2.0 (authorization code): the user approves on
  // api.tradier.com, then the browser returns to
  // ``/settings/connections?tradier=linked&env=<sandbox|live>&code=...&state=...``.
  // That same tab runs the useEffect below to exchange the code. No
  // verifier paste (unlike E*TRADE OAuth 1.0a in this wizard).
  const [tradierForm, setTradierForm] = useState({
    env: 'sandbox' as 'sandbox' | 'live',
    state: '',
    account_name: '',
  });
  const [coinbaseForm, setCoinbaseForm] = useState({
    state: '',
    account_name: '',
  });
  const [busy, setBusy] = useState(false);
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [isDeleteOpen, setIsDeleteOpen] = useState(false);
  const onDeleteOpen = () => setIsDeleteOpen(true);
  const onDeleteClose = () => setIsDeleteOpen(false);
  const cancelRef = React.useRef<HTMLButtonElement>(null);
  const { poll: pollConnectJob } = useConnectJobPoll();
  const [syncHistory, setSyncHistory] = useState<any[]>([]);
  const [editAccount, setEditAccount] = useState<any | null>(null);
  const [editCredentials, setEditCredentials] = useState<Record<string, string>>({});
  const [editOpen, setEditOpen] = useState(false);
  const [editNameId, setEditNameId] = useState<number | null>(null);
  const [editNameValue, setEditNameValue] = useState('');
  const [showSetupBanner, setShowSetupBanner] = useState(false);
  const [pickerEngaged, setPickerEngaged] = useState(false);
  const [detailWizardBroker, setDetailWizardBroker] = useState<WizardBrokerKey | null>(null);
  const [oauthBusy, setOauthBusy] = useState(false);

  const connectionsHealthQuery = useQuery({
    queryKey: ['connectionsHealth'],
    queryFn: connectionsApi.getHealth,
    staleTime: 20_000,
  });

  const oauthListQuery = useQuery({
    queryKey: ['oauthConnections'],
    queryFn: () => oauthApi.listConnections(),
    staleTime: 20_000,
  });

  const openEditModal = (a: any) => {
    setEditAccount(a);
    setEditCredentials({
      client_id: '',
      client_secret: '',
      refresh_token: '',
      flex_token: '',
      query_id: '',
      account_number: a?.account_number || '',
    });
    setEditOpen(true);
  };

  const brokerDisplayName = (b: string) => {
    const key = (b || '').toUpperCase();
    if (key === 'IBKR') return 'Interactive Brokers';
    if (key === 'SCHWAB') return 'Charles Schwab';
    if (key === 'TASTYTRADE') return 'Tastytrade';
    if (key === 'ETRADE') return 'E*TRADE';
    if (key === 'TRADIER') return 'Tradier';
    if (key === 'TRADIER_SANDBOX') return 'Tradier (sandbox)';
    if (key === 'COINBASE') return 'Coinbase';
    return b;
  };

  const hasAccountsBySlug = useMemo(() => {
    const m: Record<BrokerSlug, boolean> = {
      ibkr: false,
      schwab: false,
      tastytrade: false,
      etrade: false,
      tradier: false,
      coinbase: false,
    };
    for (const t of LIVE_BROKER_TILES) {
      m[t.slug] = accounts.some((a) => {
        const b = String(a.broker).toUpperCase();
        if (t.slug === 'tradier') return b === 'TRADIER' || b === 'TRADIER_SANDBOX';
        return b === t.wizardBroker;
      });
    }
    return m;
  }, [accounts]);

  const relativeLastSyncBySlug = useMemo(() => {
    const out: Record<BrokerSlug, string | null> = {
      ibkr: null,
      schwab: null,
      tastytrade: null,
      etrade: null,
      tradier: null,
      coinbase: null,
    };
    const rows = connectionsHealthQuery.data?.by_broker ?? [];
    for (const row of rows) {
      const slug = row.broker as BrokerSlug;
      if (slug in out) {
        out[slug] = row.last_sync_at ? formatRelativeTime(row.last_sync_at) : null;
      }
    }
    return out;
  }, [connectionsHealthQuery.data]);

  const LogoTile: React.FC<{ label: string; srcs: string[]; selected: boolean; onClick: () => void; wide?: boolean }> =
    ({ label, srcs, onClick, wide, selected }) => {
      const [idx, setIdx] = React.useState(0);
      const src = srcs[Math.min(idx, srcs.length - 1)];
      return (
        <button
          type="button"
          aria-label={label}
          aria-pressed={selected}
          onClick={onClick}
          className={cn(
            'flex cursor-pointer items-center justify-center rounded-md bg-transparent p-1 transition-transform hover:scale-[1.03] active:scale-[0.98]',
            'border border-transparent',
            selected && 'border-primary bg-primary/5 ring-2 ring-primary/40',
            wide ? 'min-h-11 min-w-[150px]' : 'min-h-[60px] min-w-[60px]',
          )}
        >
          <img
            src={src}
            alt={label}
            className={cn('object-contain', wide ? 'h-10 w-[150px]' : 'h-14 w-14')}
            onError={() => {
              if (idx < srcs.length - 1) setIdx(idx + 1);
            }}
          />
        </button>
      );
    };

  const loadAccounts = async () => {
    try {
      const res: unknown = await accountsApi.list();
      setAccounts((Array.isArray(res) ? res : []) as any[]);
      refetchGlobalAccounts();
      await queryClient.invalidateQueries({ queryKey: ['connectionsHealth'] });
      await queryClient.invalidateQueries({ queryKey: ['oauthConnections'] });
    } catch (e) {
      toast({ title: 'Load accounts failed', description: handleApiError(e), status: 'error' });
    }
  };

  const loadSyncHistory = async () => {
    try {
      const res: any = await accountsApi.syncHistory();
      const list = Array.isArray(res) ? res : (Array.isArray(res?.data) ? res.data : []);
      setSyncHistory(list);
    } catch {
      setSyncHistory([]);
    }
  };

  useEffect(() => {
    const init = async () => {
      loadAccounts();
      loadSyncHistory();
      try {
        const conf: any = await aggregatorApi.config();
        setCfg({ schwabConfigured: !!conf?.schwab?.configured, redirect: conf?.schwab?.redirect_uri, schwabProbe: conf?.schwab?.probe });
        try {
          const s: any = await aggregatorApi.tastytradeStatus();
          setTt({ connected: !!s?.connected, available: !!s?.available, last_error: s?.last_error, job_error: s?.job_error });
        } catch { /* ignore */ }
      } catch {
        setCfg({ schwabConfigured: false });
      }
    };
    init();

    // Handle Schwab OAuth callback redirect
    const params = new URLSearchParams(window.location.search);
    const schwabStatus = params.get('schwab');
    if (schwabStatus === 'linked') {
      toast({ title: 'Schwab account linked successfully', status: 'success' });
      setShowSetupBanner(true);
      loadAccounts();
      loadSyncHistory();
      window.history.replaceState({}, '', window.location.pathname);
    } else if (schwabStatus === 'error') {
      const reason = params.get('reason') || 'unknown';
      toast({ title: 'Schwab linking failed', description: reason.replace(/_/g, ' '), status: 'error' });
      window.history.replaceState({}, '', window.location.pathname);
    }
    // E*TRADE sandbox does not redirect back with a code — the user pastes a
    // verifier in the wizard — but we still honor ``?etrade=linked`` in case a
    // future live-OAuth flow uses a redirect URI.
    const etradeStatus = params.get('etrade');
    if (etradeStatus === 'linked') {
      toast({ title: 'E*TRADE account linked successfully', status: 'success' });
      loadAccounts();
      loadSyncHistory();
      window.history.replaceState({}, '', window.location.pathname);
    }
    // Tradier: redirect back with ``?tradier=linked&env=...&code=...&state=...``.
    const tradierStatus = params.get('tradier');
    const tradierCode = params.get('code');
    const tradierState = params.get('state');
    const tradierEnv = (params.get('env') || 'sandbox') as 'sandbox' | 'live';
    if (tradierStatus === 'linked' && tradierCode && tradierState) {
      const brokerId = tradierEnv === 'live' ? 'tradier' : 'tradier_sandbox';
      (async () => {
        const notifyOtherTabs = () => {
          const msg = { broker: 'tradier' as const, env: tradierEnv, status: 'ok' as const };
          if (typeof BroadcastChannel !== 'undefined') {
            const bc = new BroadcastChannel('axf-oauth');
            bc.postMessage(msg);
            bc.close();
          }
          try {
            localStorage.setItem('axf-oauth-ping', JSON.stringify({ ...msg, ts: Date.now() }));
          } catch { /* private mode / blocked */ }
        };
        const defaultName = `Tradier (${tradierEnv})`;
        const brokerEnum = tradierEnv === 'live' ? 'TRADIER' as const : 'TRADIER_SANDBOX' as const;
        let placeAccountName = defaultName;
        try {
          const p = sessionStorage.getItem('axf-tradier-pending');
          if (p) {
            const o = JSON.parse(p) as { account_name?: string };
            if (o?.account_name?.trim()) placeAccountName = o.account_name.trim();
          }
        } catch { /* invalid JSON */ }
        try {
          sessionStorage.removeItem('axf-tradier-pending');
        } catch { /* */ }
        try {
          await oauthApi.callback(brokerId, tradierState, tradierCode);
          try {
            await accountsApi.add({
              broker: brokerEnum,
              account_number: 'TRADIER_OAUTH',
              account_name: placeAccountName || defaultName,
              account_type: 'TAXABLE',
            });
          } catch (e) {
            // Placeholder already exists — fine, sync will auto-correct.
            const msg = handleApiError(e).toLowerCase();
            if (!msg.includes('exists') && !msg.includes('duplicate')) throw e;
          }
          toast({ title: 'Tradier connected', status: 'success' });
          await loadAccounts();
          await loadSyncHistory();
          notifyOtherTabs();
        } catch (e) {
          toast({
            title: 'Tradier callback failed',
            description: handleApiError(e),
            status: 'error',
          });
        } finally {
          window.history.replaceState({}, '', window.location.pathname);
          try {
            window.close();
          } catch { /* not a script-opened window */ }
        }
      })();
    }
    const coinbaseStatus = params.get('coinbase');
    const coinbaseCode = params.get('code');
    const coinbaseState = params.get('state');
    if (coinbaseStatus === 'linked' && coinbaseCode && coinbaseState) {
      (async () => {
        const notifyOtherTabs = () => {
          const msg = { broker: 'coinbase' as const, status: 'ok' as const };
          if (typeof BroadcastChannel !== 'undefined') {
            const bc = new BroadcastChannel('axf-oauth');
            bc.postMessage(msg);
            bc.close();
          }
          try {
            localStorage.setItem('axf-oauth-ping', JSON.stringify({ ...msg, ts: Date.now() }));
          } catch { /* private mode / blocked */ }
        };
        const defaultName = 'Coinbase';
        let placeAccountName = defaultName;
        try {
          const p = sessionStorage.getItem('axf-coinbase-pending');
          if (p) {
            const o = JSON.parse(p) as { account_name?: string };
            if (o?.account_name?.trim()) placeAccountName = o.account_name.trim();
          }
        } catch { /* invalid JSON */ }
        try {
          sessionStorage.removeItem('axf-coinbase-pending');
        } catch { /* */ }
        try {
          await oauthApi.callback('coinbase', coinbaseState, coinbaseCode);
          try {
            await accountsApi.add({
              broker: 'COINBASE',
              account_number: 'COINBASE_OAUTH',
              account_name: placeAccountName || defaultName,
              account_type: 'TAXABLE',
            });
          } catch (e) {
            const msg = handleApiError(e).toLowerCase();
            if (!msg.includes('exists') && !msg.includes('duplicate')) throw e;
          }
          toast({ title: 'Coinbase connected', status: 'success' });
          await loadAccounts();
          await loadSyncHistory();
          notifyOtherTabs();
        } catch (e) {
          toast({
            title: 'Coinbase callback failed',
            description: handleApiError(e),
            status: 'error',
          });
        } finally {
          window.history.replaceState({}, '', window.location.pathname);
          try {
            window.close();
          } catch { /* not a script-opened window */ }
        }
      })();
    }
  }, []);

  // Tradier popup uses ``noopener`` (so ``window.opener`` is null). The
  // callback tab notifies the main Settings tab via ``BroadcastChannel`` and
  // a ``localStorage`` ping (``storage`` event fallback for older Safari).
  // Legacy: still listen for same-origin ``tradier-linked`` postMessage.
  useEffect(() => {
    const refresh = () => {
      void loadAccounts();
      void loadSyncHistory();
      void queryClient.invalidateQueries({ queryKey: ['connectionsHealth'] });
      void queryClient.invalidateQueries({ queryKey: ['oauthConnections'] });
    };
    const ch = typeof BroadcastChannel !== 'undefined' ? new BroadcastChannel('axf-oauth') : null;
    const onBc = (ev: MessageEvent) => {
      const d = ev.data as { broker?: string; status?: string } | null;
      if (d && (d.broker === 'tradier' || d.broker === 'coinbase') && d.status === 'ok') refresh();
    };
    ch?.addEventListener('message', onBc);
    const onStorage = (e: StorageEvent) => {
      if (e.key !== 'axf-oauth-ping' || !e.newValue) return;
      try {
        const d = JSON.parse(e.newValue) as { broker?: string; status?: string };
        if (d && (d.broker === 'tradier' || d.broker === 'coinbase') && d.status === 'ok') refresh();
      } catch { /* */ }
    };
    window.addEventListener('storage', onStorage);
    const onMessage = (ev: MessageEvent) => {
      if (ev.origin !== window.location.origin) return;
      if (ev.data && (ev.data as { type?: string }).type === 'tradier-linked') refresh();
    };
    window.addEventListener('message', onMessage);
    return () => {
      ch?.removeEventListener('message', onBc);
      ch?.close();
      window.removeEventListener('storage', onStorage);
      window.removeEventListener('message', onMessage);
    };
  }, []);

  const handleAdd = async () => {
    setAdding(true);
    try {
      await accountsApi.add({
        broker: form.broker,
        account_number: form.account_number.trim(),
        account_name: form.account_name.trim() || undefined,
        account_type: form.account_type,
      });
      await loadAccounts();
      setForm({ broker: 'SCHWAB', account_number: '', account_name: '', account_type: 'TAXABLE' });
      toast({ title: 'Account added', status: 'success' });
    } catch (e) {
      toast({ title: 'Add account failed', description: handleApiError(e), status: 'error' });
    } finally {
      setAdding(false);
    }
  };

  const handleConnectSchwab = async (id: number) => {
    const popup = window.open('about:blank', '_blank', 'noopener,noreferrer');
    try {
      if (cfg && !cfg.schwabConfigured) {
        try {
          popup?.close();
        } catch {
          /* noop */
        }
        toast({ title: 'Schwab OAuth not configured', description: 'Ask admin to set client_id, secret, and redirect URI on the server.', status: 'warning' });
        return;
      }
      const res: any = await aggregatorApi.schwabLink(id, false);
      const url = res?.url;
      if (url) {
        if (popup && !popup.closed) {
          popup.location.href = url;
        } else {
          window.open(url, '_blank', 'noopener,noreferrer');
        }
        toast({ title: 'Complete Schwab connect in the new tab', status: 'info' });
      }
    } catch (e) {
      try {
        popup?.close();
      } catch {
        /* noop */
      }
      toast({ title: 'Link failed', description: handleApiError(e), status: 'error' });
    }
  };

  const pollSyncStatus = async (id: number) => {
    setSyncingId(id);
    try {
      for (let i = 0; i < 20; i++) {
        const s: any = await accountsApi.syncStatus(id);
        if (s?.sync_status && !['queued', 'running'].includes(String(s.sync_status).toLowerCase())) {
          break;
        }
        await new Promise(r => setTimeout(r, 1000));
      }
    } finally {
      setSyncingId(null);
      await loadAccounts();
      await loadSyncHistory();
    }
  };

  const handleSync = async (id: number) => {
    try {
      const res: any = await accountsApi.sync(id, 'comprehensive');
      if (res?.task_id || res?.status) {
        pollSyncStatus(id);
        toast({ title: 'Sync started', status: 'success' });
      }
    } catch (e) {
      toast({ title: 'Sync failed', description: handleApiError(e), status: 'error' });
    }
  };

  const handleTTConnect = async () => {
    try {
      setBusy(true);
      const res: any = await aggregatorApi.tastytradeConnect({ client_id: ttForm.client_id.trim(), client_secret: ttForm.client_secret.trim(), refresh_token: ttForm.refresh_token.trim() });
      const jobId = res?.job_id;
      if (!jobId) throw new Error('Connect job not started');
      // Fast path: if already connected, short-circuit
      try {
        const s0: any = await aggregatorApi.tastytradeStatus();
        if (s0?.connected) {
          setTt({ connected: true, available: true });
          toast({ title: 'Tastytrade connected', status: 'success' });
          await loadAccounts();
          return;
        }
      } catch { /* ignore */ }
      const result = await pollConnectJob(jobId, (id) => aggregatorApi.tastytradeStatus(id));
      if (result.success) {
        setTt({ connected: true, available: true });
        toast({ title: 'Tastytrade connected', status: 'success' });
        await loadAccounts();
      } else {
        const errMsg = result.error || 'Login failed';
        setTt(prev => ({ ...prev ?? { connected: false, available: true }, last_error: errMsg, job_error: errMsg }));
        throw new Error(errMsg);
      }
    } catch (e) {
      toast({ title: 'Connect failed', description: handleApiError(e), status: 'error' });
    } finally {
      setBusy(false);
    }
  };

  const handleTTDisconnect = async () => {
    try {
      await aggregatorApi.tastytradeDisconnect();
      setTt({ connected: false, available: true });
      toast({ title: 'Tastytrade disconnected', status: 'success' });
      await loadAccounts();
    } catch (e) {
      toast({ title: 'Disconnect failed', description: handleApiError(e), status: 'error' });
    }
  };

  // Wizard helpers
  const startWizard = () => {
    setStep(1);
    setBroker('');
    setTtForm({ client_id: '', client_secret: '', refresh_token: '' });
    setSchwabForm({ account_number: '', account_name: '' });
    setIbkrForm({ flex_token: '', query_id: '', account_number: '' });
    setEtradeForm({ state: '', verifier: '', account_name: '' });
    setWizardOpen(true);
  };

  // E*TRADE OAuth 1.0a: step 1 — call /initiate, open authorize_url in a new
  // tab so the user gets the 5-char verifier. We keep ``state`` in local
  // component state; the backend keeps the corresponding request-token secret
  // in Redis until the user posts back the verifier.
  const handleEtradeAuthorize = async () => {
    // Popup blocker guard (Copilot review on PR #395): most browsers
    // treat ``window.open`` calls that run AFTER an ``await`` as
    // non-user-initiated and silently block them, which breaks the
    // E*TRADE authorize step. Open a blank tab synchronously while we
    // are still inside the click handler's user-gesture window, then
    // point it at the real authorize URL once the backend responds.
    const popup = window.open('about:blank', '_blank', 'noopener,noreferrer');
    try {
      setBusy(true);
      const callbackUrl = `${window.location.origin}/settings/connections?etrade=linked`;
      const res = await oauthApi.initiate('etrade_sandbox', callbackUrl);
      if (!res?.authorize_url || !res?.state) {
        throw new Error('E*TRADE did not return an authorization URL');
      }
      setEtradeForm((prev) => ({ ...prev, state: res.state }));
      if (popup && !popup.closed) {
        popup.location.href = res.authorize_url;
      } else {
        // Popup was blocked by the browser — fall back to an in-page
        // redirect-style open. The user can also copy the URL from
        // the toast if the second attempt is also blocked.
        window.open(res.authorize_url, '_blank', 'noopener,noreferrer');
      }
      toast({
        title: 'Authorize in the new tab, then paste the verifier code',
        status: 'info',
      });
    } catch (e) {
      // Close the blank popup we pre-opened so the user isn't left
      // staring at an empty "about:blank" tab.
      try { popup?.close(); } catch { /* noop */ }
      toast({ title: 'E*TRADE authorize failed', description: handleApiError(e), status: 'error' });
    } finally {
      setBusy(false);
    }
  };

  // Same popup pre-open pattern as E*TRADE. Tradier returns with
  // ``?tradier=linked&code=...`` (see page-load useEffect) — no verifier paste.
  const handleCoinbaseAuthorize = async () => {
    const popup = window.open('about:blank', '_blank', 'noopener,noreferrer');
    try {
      setBusy(true);
      const brokerId = 'coinbase';
      const callbackUrl =
        `${window.location.origin}/settings/connections?coinbase=linked`;
      try {
        sessionStorage.setItem(
          'axf-coinbase-pending',
          JSON.stringify({ account_name: coinbaseForm.account_name.trim() })
        );
      } catch { /* */ }
      const res = await oauthApi.initiate(brokerId, callbackUrl);
      if (!res?.authorize_url || !res?.state) {
        throw new Error('Coinbase did not return an authorization URL');
      }
      setCoinbaseForm((prev) => ({ ...prev, state: res.state }));
      if (popup && !popup.closed) {
        popup.location.href = res.authorize_url;
      } else {
        window.open(res.authorize_url, '_blank', 'noopener,noreferrer');
      }
      toast({
        title: 'Authorize in the new tab — we\u2019ll finish when Coinbase redirects back',
        status: 'info',
      });
    } catch (e) {
      try { popup?.close(); } catch { /* noop */ }
      toast({ title: 'Coinbase authorize failed', description: handleApiError(e), status: 'error' });
    } finally {
      setBusy(false);
    }
  };

  const handleTradierAuthorize = async (env: 'sandbox' | 'live') => {
    const popup = window.open('about:blank', '_blank', 'noopener,noreferrer');
    try {
      setBusy(true);
      setTradierForm((prev) => ({ ...prev, env }));
      const brokerId = env === 'live' ? 'tradier' : 'tradier_sandbox';
      const callbackUrl =
        `${window.location.origin}/settings/connections?tradier=linked&env=${env}`;
      try {
        sessionStorage.setItem(
          'axf-tradier-pending',
          JSON.stringify({ account_name: tradierForm.account_name.trim() })
        );
      } catch { /* */ }
      const res = await oauthApi.initiate(brokerId, callbackUrl);
      if (!res?.authorize_url || !res?.state) {
        throw new Error('Tradier did not return an authorization URL');
      }
      setTradierForm((prev) => ({ ...prev, state: res.state }));
      if (popup && !popup.closed) {
        popup.location.href = res.authorize_url;
      } else {
        window.open(res.authorize_url, '_blank', 'noopener,noreferrer');
      }
      toast({
        title: 'Authorize in the new tab — we\u2019ll finish automatically when Tradier redirects back',
        status: 'info',
      });
    } catch (e) {
      try { popup?.close(); } catch { /* noop */ }
      toast({ title: 'Tradier authorize failed', description: handleApiError(e), status: 'error' });
    } finally {
      setBusy(false);
    }
  };

  const submitWizard = async () => {
    try {
      setBusy(true);
      if (broker === 'SCHWAB') {
        const popup = window.open('about:blank', '_blank', 'noopener,noreferrer');
        try {
          // Create placeholder Schwab account then open OAuth link
          const added: any = await accountsApi.add({
            broker: 'SCHWAB',
            account_number: (schwabForm.account_number || 'SCHWAB_OAUTH').trim(),
            account_name: schwabForm.account_name.trim() || undefined,
            account_type: 'TAXABLE'
          });
          const newId = added?.id || (await (async () => { await loadAccounts(); const a = accounts.find(x => String(x.account_number).includes(schwabForm.account_number || 'SCHWAB_OAUTH') && String(x.broker).toLowerCase() === 'schwab'); return a?.id; })());
          if (!newId) throw new Error('Failed to create Schwab account');
          const res: any = await aggregatorApi.schwabLink(newId, false);
          const url = res?.url;
          if (!url) throw new Error('Authorization URL not returned');
          if (popup && !popup.closed) {
            popup.location.href = url;
          } else {
            window.open(url, '_blank', 'noopener,noreferrer');
          }
          toast({ title: 'Complete Schwab connect in the new tab', status: 'info' });
        } catch (e) {
          try { popup?.close(); } catch { /* noop */ }
          throw e;
        }
      } else if (broker === 'TASTYTRADE') {
        // Use form already shown on page? Keep wizard support as well
        if (!ttForm.client_id || !ttForm.client_secret || !ttForm.refresh_token) throw new Error('Enter Tastytrade Client ID, Client Secret, and Refresh Token');
        const res: any = await aggregatorApi.tastytradeConnect({ client_id: ttForm.client_id.trim(), client_secret: ttForm.client_secret.trim(), refresh_token: ttForm.refresh_token.trim() });
        const jobId = res?.job_id;
        if (!jobId) throw new Error('Connect job not started');
        // Fast path: if already connected, short-circuit
        try {
          const s0: any = await aggregatorApi.tastytradeStatus();
          if (s0?.connected) {
            toast({ title: 'Tastytrade connected', status: 'success' });
            await loadAccounts();
            setWizardOpen(false);
            return;
          }
        } catch { /* ignore */ }
        const ttResult = await pollConnectJob(jobId, (id) => aggregatorApi.tastytradeStatus(id));
        if (ttResult.success) {
          toast({ title: 'Tastytrade connected', status: 'success' });
          await loadAccounts();
          setWizardOpen(false);
        } else {
          setTt(prev => ({ ...prev ?? { connected: false, available: true }, last_error: ttResult.error || undefined, job_error: ttResult.error || undefined }));
          throw new Error(ttResult.error || 'Login failed');
        }
      } else if (broker === 'ETRADE') {
        // OAuth 1.0a two-phase wizard: ``state`` is populated by
        // handleEtradeAuthorize; the verifier is the 5-char code E*TRADE
        // displays after authorization. Callback persists the OAuth tokens;
        // we then create a placeholder BrokerAccount so the sync service's
        // _resolve_or_discover step can fill in the real accountIdKey.
        if (!etradeForm.state) throw new Error('Click Authorize first to open E*TRADE');
        if (!etradeForm.verifier.trim()) throw new Error('Paste the verifier code from E*TRADE');
        await oauthApi.callback('etrade_sandbox', etradeForm.state, etradeForm.verifier.trim());
        try {
          await accountsApi.add({
            broker: 'ETRADE',
            account_number: 'ETRADE_OAUTH',
            account_name: etradeForm.account_name.trim() || 'E*TRADE (sandbox)',
            account_type: 'TAXABLE',
          });
        } catch (e) {
          // If a placeholder already exists the API returns a 400; ignore so
          // the user can re-authorize without deleting the account first.
          const msg = handleApiError(e).toLowerCase();
          if (!msg.includes('exists') && !msg.includes('duplicate')) {
            throw e;
          }
        }
        toast({ title: 'E*TRADE connected', status: 'success' });
        await loadAccounts();
        await loadSyncHistory();
      } else if (broker === 'TRADIER') {
        // OAuth 2.0 authorization code: work happens in
        // ``handleTradierAuthorize`` (initiate) + the page-load
        // useEffect (callback). The wizard's Submit button simply
        // dismisses once the state variable is populated, so we surface
        // a clear error if the user clicks Done without authorizing.
        if (!tradierForm.state) {
          throw new Error('Click Authorize first to complete Tradier OAuth');
        }
        toast({ title: 'Tradier connection in progress', status: 'info' });
      } else if (broker === 'COINBASE') {
        if (!coinbaseForm.state) {
          throw new Error('Click Authorize first to complete Coinbase OAuth');
        }
        toast({ title: 'Coinbase connection in progress', status: 'info' });
      } else if (broker === 'IBKR') {
        if (!ibkrForm.flex_token || !ibkrForm.query_id) throw new Error('Enter Flex Token and Query ID');
        const res: any = await aggregatorApi.ibkrFlexConnect({
          flex_token: ibkrForm.flex_token.trim(),
          query_id: ibkrForm.query_id.trim(),
          ...(ibkrForm.account_number.trim() ? { account_number: ibkrForm.account_number.trim() } : {}),
        });
        const jobId = res?.job_id;
        if (!jobId) throw new Error('Connect job not started');
        // Fast path check
        try {
          const s0: any = await aggregatorApi.ibkrFlexStatus();
          if (s0?.connected || (Array.isArray(s0?.accounts) && s0.accounts.length > 0)) {
            toast({ title: 'Interactive Brokers connected', status: 'success' });
            await loadAccounts();
            setWizardOpen(false);
            return;
          }
        } catch { /* ignore */ }
        const ibkrResult = await pollConnectJob(jobId, (id) => aggregatorApi.ibkrFlexStatus(id), { isIbkr: true });
        if (ibkrResult.success) {
          toast({ title: 'Interactive Brokers connected', status: 'success' });
          await loadAccounts();
        } else {
          throw new Error(ibkrResult.error || 'IBKR connect failed');
        }
      }
      setWizardOpen(false);
    } catch (e) {
      toast({ title: 'Connection failed', description: handleApiError(e), status: 'error' });
    } finally {
      setBusy(false);
    }
  };

  /* ---------- IB Gateway ---------- */
  const gatewayQuery = useQuery({
    queryKey: ['ibGatewayStatus'],
    queryFn: async () => {
      const res = await api.get('/portfolio/options/gateway-status');
      return res.data?.data ?? { connected: false, available: false };
    },
    staleTime: 30000,
    refetchInterval: 60000,
  });
  const gwData = gatewayQuery.data as { connected?: boolean; available?: boolean; host?: string; port?: number; client_id?: number; trading_mode?: string; last_connected?: string; error?: string; vnc_url?: string } | undefined;

  const gatewayConnectMutation = useMutation({
    mutationFn: () => api.post('/portfolio/options/gateway-connect'),
    onSuccess: () => {
      gatewayQuery.refetch();
      hotToast.success('Gateway reconnection triggered — auto-checking status...');
      let polls = 0;
      const timer = setInterval(() => {
        polls++;
        gatewayQuery.refetch();
        if (polls >= 10) clearInterval(timer);
      }, 3000);
    },
    onError: (err: unknown) => { hotToast.error(`Gateway connect failed: ${handleApiError(err)}`); },
  });

  /* ---------- IB Gateway settings ---------- */
  const [gwEditOpen, setGwEditOpen] = useState(false);
  const [gwForm, setGwForm] = useState({ host: '', port: '', client_id: '' });
  const ibkrAccount = accounts.find((a: any) => String(a.broker || '').toUpperCase() === 'IBKR');

  const loadGwSettings = async () => {
    if (!ibkrAccount) return;
    try {
      const res = await api.get(`/accounts/${ibkrAccount.id}/gateway-settings`);
      const gw = res.data?.data ?? {};
      setGwForm({
        host: gw.gateway_host || gwData?.host || '',
        port: String(gw.gateway_port || gwData?.port || ''),
        client_id: String(gw.gateway_client_id || gwData?.client_id || ''),
      });
    } catch {
      setGwForm({
        host: gwData?.host || '',
        port: String(gwData?.port || ''),
        client_id: String(gwData?.client_id || ''),
      });
    }
  };

  const saveGwSettings = useMutation({
    mutationFn: async () => {
      if (!ibkrAccount) throw new Error('No IBKR account found');
      const payload: Record<string, any> = {};
      if (gwForm.host.trim()) payload.gateway_host = gwForm.host.trim();
      if (gwForm.port.trim()) payload.gateway_port = parseInt(gwForm.port, 10);
      if (gwForm.client_id.trim()) payload.gateway_client_id = parseInt(gwForm.client_id, 10);
      await api.patch(`/accounts/${ibkrAccount.id}/gateway-settings`, payload);
    },
    onSuccess: () => {
      hotToast.success('Gateway settings saved');
      setGwEditOpen(false);
    },
    onError: (err: unknown) => { hotToast.error(`Save failed: ${handleApiError(err)}`); },
  });

  /* ---------- TradingView preferences ---------- */
  const tvPrefs = (user as any)?.ui_preferences ?? {};
  const [tvInterval, setTvInterval] = useState(tvPrefs.tv_default_interval || 'D');
  const [tvStudies, setTvStudies] = useState<string>(tvPrefs.tv_default_studies || 'EMA,RSI,MACD,Volume');

  const tvPrefsMutation = useMutation({
    mutationFn: (prefs: Record<string, string>) => api.patch('/users/preferences', { ui_preferences: prefs }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['authUser'] });
      hotToast.success('TradingView preferences saved');
    },
    onError: (err: unknown) => { hotToast.error(`Save failed: ${handleApiError(err)}`); },
  });

  const syncAllMutation = useMutation({
    mutationFn: () => accountsApi.syncAll(),
    onSuccess: () => {
      hotToast.success('Sync queued for all enabled accounts');
      void loadAccounts();
      void loadSyncHistory();
      void queryClient.invalidateQueries({ queryKey: ['connectionsHealth'] });
    },
    onError: (err: unknown) => {
      hotToast.error(`Sync failed: ${handleApiError(err)}`);
    },
  });

  const openWizardForBroker = (wb: WizardBrokerKey) => {
    setBroker(wb);
    setStep(2);
    setWizardOpen(true);
    setPickerEngaged(true);
  };

  const onTileConnect = (def: BrokerTileDefinition) => {
    setPickerEngaged(true);
    openWizardForBroker(def.wizardBroker);
  };

  const onTileReconnect = (def: BrokerTileDefinition) => {
    setPickerEngaged(true);
    const wb = def.wizardBroker;
    if (wb === 'COINBASE') {
      void handleCoinbaseAuthorize();
      return;
    }
    if (wb === 'SCHWAB') {
      const schwab = accounts.find((a) => String(a.broker).toUpperCase() === 'SCHWAB');
      if (schwab) void handleConnectSchwab(schwab.id);
      else openWizardForBroker('SCHWAB');
      return;
    }
    openWizardForBroker(wb);
  };

  const onTileManage = (def: BrokerTileDefinition) => {
    setDetailWizardBroker(def.wizardBroker);
  };

  const showFirstRun =
    connectionsHealthQuery.isSuccess &&
    connectionsHealthQuery.data !== undefined &&
    connectionsHealthQuery.data.connected === 0;

  const showHealthStrip =
    connectionsHealthQuery.isSuccess &&
    connectionsHealthQuery.data !== undefined &&
    connectionsHealthQuery.data.connected > 0;

  const detailAccounts: DetailAccountRow[] = useMemo(() => {
    if (!detailWizardBroker) return [];
    return accounts
      .filter((a) => {
        const b = String(a.broker).toUpperCase();
        if (detailWizardBroker === 'TRADIER') return b === 'TRADIER' || b === 'TRADIER_SANDBOX';
        return b === detailWizardBroker;
      })
      .map((a) => ({
        id: a.id as number,
        broker: String(a.broker),
        account_number: String(a.account_number),
        account_name: a.account_name as string | null | undefined,
        account_type: a.account_type as string | undefined,
        is_enabled: a.is_enabled as boolean | undefined,
        sync_status: a.sync_status as string | null | undefined,
        sync_error_message: a.sync_error_message as string | null | undefined,
        last_successful_sync: a.last_successful_sync as string | null | undefined,
        total_value: a.total_value != null ? String(a.total_value) : undefined,
        cash_balance: a.cash_balance != null ? String(a.cash_balance) : undefined,
      }));
  }, [accounts, detailWizardBroker]);

  return (
    <TooltipProvider delayDuration={200}>
    <div className="w-full">
      <PageContainer width="default">
        <PageHeader
          title="Connections"
          subtitle="Manage brokerages, live data, charting, and data provider integrations."
          actions={
            <Button type="button" onClick={startWizard}>
              + New connection
            </Button>
          }
        />
        <div className="flex flex-col gap-6 items-stretch">

          {showSetupBanner && accounts.filter(a => String(a.broker).toUpperCase() === 'SCHWAB').length > 0 && (
            <div className="rounded-xl border-2 border-[rgb(var(--status-success))] bg-muted/40 p-4">
              <div className="mb-2 text-base font-bold">
                {accounts.filter(a => String(a.broker).toUpperCase() === 'SCHWAB').length} Schwab account{accounts.filter(a => String(a.broker).toUpperCase() === 'SCHWAB').length > 1 ? 's' : ''} connected
              </div>
              <div className="mb-3 text-sm text-muted-foreground">
                Classify your accounts and choose which to track in your portfolio. Empty accounts are fine to leave untracked.
              </div>
              <div className="mb-3 flex flex-col gap-2 items-stretch">
                {accounts.filter(a => String(a.broker).toUpperCase() === 'SCHWAB').map((a: any) => (
                  <div key={a.id} className="flex flex-row items-center gap-3 rounded-md border border-border p-2">
                    <div className="flex-1 text-sm font-medium">{a.account_name || a.account_number}</div>
                    <select
                      className={selectSm}
                      value={(a.account_type || 'taxable').toUpperCase()}
                      onChange={async (e) => {
                        try {
                          await accountsApi.updateAccount(a.id, { account_type: e.target.value });
                          await loadAccounts();
                        } catch (err) {
                          toast({ title: 'Update failed', status: 'error', description: handleApiError(err) });
                        }
                      }}
                    >
                      <option value="TAXABLE">Taxable</option>
                      <option value="IRA">IRA</option>
                      <option value="ROTH_IRA">Roth IRA</option>
                      <option value="HSA">HSA</option>
                      <option value="TRUST">Trust</option>
                    </select>
                    <div className="flex flex-row items-center gap-1">
                      <Checkbox
                        checked={!!a.is_enabled}
                        onCheckedChange={async (v) => {
                          const next = v === true;
                          try {
                            await accountsApi.updateAccount(a.id, { is_enabled: next });
                            await loadAccounts();
                          } catch (err) {
                            toast({ title: 'Update failed', status: 'error', description: handleApiError(err) });
                          }
                        }}
                      />
                      <div className="text-xs font-medium">{a.is_enabled ? 'Track' : 'Skip'}</div>
                    </div>
                  </div>
                ))}
              </div>
              <div className="flex flex-row items-center gap-2">
                <Button type="button" size="sm" onClick={() => { setShowSetupBanner(false); navigate('/portfolio'); }}>
                  Go to Portfolio
                </Button>
                <Button type="button" size="sm" variant="ghost" onClick={() => setShowSetupBanner(false)}>
                  Done, dismiss
                </Button>
              </div>
            </div>
          )}

          {/* ========== SECTION 1: BROKERAGES ========== */}
          <div>
            <div className="mb-1 flex flex-row items-center gap-3">
              <div className="rounded-md bg-muted/60 p-1.5"><Link2 className="size-[18px]" aria-hidden /></div>
              <div className="text-lg font-bold">Brokerages</div>
            </div>
            <div className="mb-4 pl-[42px] text-sm text-muted-foreground">
              Connect brokerage accounts to import positions, trades, and transactions.
            </div>
          </div>

          {connectionsHealthQuery.isError ? (
            <Alert variant="destructive">
              <AlertTitle>Could not load connection health</AlertTitle>
              <AlertDescription className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <span>{handleApiError(connectionsHealthQuery.error)}</span>
                <Button type="button" size="sm" variant="outline" onClick={() => void connectionsHealthQuery.refetch()}>
                  Retry
                </Button>
              </AlertDescription>
            </Alert>
          ) : null}

          {connectionsHealthQuery.isLoading ? (
            <div className="flex flex-row items-center gap-2 text-sm text-muted-foreground" role="status">
              <Loader2 className="size-4 animate-spin" aria-hidden />
              Loading connection status...
            </div>
          ) : null}

          {showFirstRun ? <FirstRunHero onEngage={() => setPickerEngaged(true)} /> : null}

          {showHealthStrip && connectionsHealthQuery.data ? (
            <HealthCard
              health={connectionsHealthQuery.data}
              onRunSync={() => syncAllMutation.mutate()}
              syncPending={syncAllMutation.isPending}
            />
          ) : null}

          {(tt?.last_error || tt?.job_error) && (
            <Alert variant="destructive">
              <AlertTitle>Tastytrade connection error</AlertTitle>
              <AlertDescription>{tt.job_error || tt.last_error}</AlertDescription>
            </Alert>
          )}

          {connectionsHealthQuery.isSuccess && connectionsHealthQuery.data ? (
            <BrokerPickerGrid
              byBroker={connectionsHealthQuery.data.by_broker}
              hasAccountsBySlug={hasAccountsBySlug}
              relativeLastSyncBySlug={relativeLastSyncBySlug}
              dimmed={showFirstRun && !pickerEngaged}
              onConnect={onTileConnect}
              onReconnect={onTileReconnect}
              onManage={onTileManage}
              schwabConfigured={cfg?.schwabConfigured}
            />
          ) : null}

          {detailWizardBroker ? (
            <ConnectionDetailSheet
              open={detailWizardBroker != null}
              onOpenChange={(open) => {
                if (!open) setDetailWizardBroker(null);
              }}
              wizardBroker={detailWizardBroker}
              accounts={detailAccounts}
              oauthConnections={oauthListQuery.data?.connections ?? []}
              timezone={timezone}
              syncingId={syncingId}
              busy={oauthBusy}
              schwabConfigured={cfg?.schwabConfigured}
              onSync={(accountId) => void handleSync(accountId)}
              onDeleteAccount={(accountId) => {
                setDeleteId(accountId);
                onDeleteOpen();
              }}
              onConnectSchwab={(accountId) => void handleConnectSchwab(accountId)}
              onEditCredentials={(account) => {
                const full = accounts.find((x) => x.id === account.id);
                if (full) openEditModal(full);
              }}
              onUpdateAccountType={async (accountId, accountType) => {
                await accountsApi.updateAccount(accountId, { account_type: accountType });
                await loadAccounts();
              }}
              onToggleTrack={async (accountId, next) => {
                await accountsApi.updateAccount(accountId, { is_enabled: next });
                await loadAccounts();
                toast({ title: next ? 'Tracking in portfolio' : 'Removed from portfolio', status: 'success' });
              }}
              onRevokeOAuth={async (connectionId) => {
                setOauthBusy(true);
                try {
                  await oauthApi.revoke(connectionId);
                  hotToast.success('OAuth connection disconnected');
                  await loadAccounts();
                } catch (error) {
                  hotToast.error('Failed to disconnect. Please try again.');
                  throw error;
                } finally {
                  setOauthBusy(false);
                }
              }}
            />
          ) : null}

          {syncHistory.length > 0 && (
            <div>
              <details>
                <summary className="cursor-pointer py-2 text-sm font-semibold text-muted-foreground">
                  Recent syncs ({syncHistory.length})
                </summary>
                <div className="mt-2 overflow-x-auto">
                  <table className="w-full min-w-[480px] border-collapse text-sm">
                    <thead>
                      <tr className="border-b border-border text-left text-xs text-muted-foreground">
                        <th className="px-2 py-2 font-medium">Account</th>
                        <th className="px-2 py-2 font-medium">Status</th>
                        <th className="px-2 py-2 font-medium">Started</th>
                        <th className="px-2 py-2 font-medium">Error</th>
                      </tr>
                    </thead>
                    <tbody>
                      {syncHistory.slice(0, 10).map((s: any) => (
                        <tr key={s.id} className="border-b border-border last:border-0">
                          <td className="px-2 py-2">
                            <div className="text-sm">{s.account_name || s.account_number}</div>
                          </td>
                          <td className="px-2 py-2">
                            <Badge
                              variant="outline"
                              className={cn(
                                'font-normal',
                                s.status === 'SUCCESS'
                                  ? 'border-[rgb(var(--status-success)/0.4)] text-[rgb(var(--status-success)/1)]'
                                  : s.status === 'ERROR'
                                    ? 'border-destructive/40 text-destructive'
                                    : 'border-blue-500/40 text-blue-800 dark:text-blue-200',
                              )}
                            >
                              {s.status}
                            </Badge>
                            {s.duration_seconds != null && (
                              <span className="text-xs text-muted-foreground">
                                {' '}
                                {s.duration_seconds}s
                              </span>
                            )}
                          </td>
                          <td className="px-2 py-2">
                            <div className="text-xs">{formatDateTime(s.started_at, timezone)}</div>
                          </td>
                          <td className="max-w-[220px] px-2 py-2">
                            {s.error_message ? (
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <span className="line-clamp-1 cursor-default text-xs text-destructive">{s.error_message}</span>
                                </TooltipTrigger>
                                <TooltipContent className="max-w-sm text-background">{s.error_message}</TooltipContent>
                              </Tooltip>
                            ) : (
                              '—'
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>
            </div>
          )}

          <hr className="my-2 border-0 border-t border-border" />

          {/* ========== SECTION 2: IB GATEWAY ========== */}
          <div>
            <div className="mb-1 flex flex-row items-center gap-3">
              <div className="rounded-md bg-muted/60 p-1.5"><Activity className="size-[18px]" aria-hidden /></div>
              <div className="text-lg font-bold">IB Gateway</div>
              <Badge
                variant="outline"
                className={cn(
                  'text-xs font-normal',
                  gwData?.connected
                    ? 'border-[rgb(var(--status-success)/0.4)] text-[rgb(var(--status-success)/1)]'
                    : 'text-muted-foreground',
                )}
              >
                {gatewayQuery.isPending ? 'Checking...' : gwData?.connected ? 'Connected' : 'Offline'}
              </Badge>
            </div>
            <div className="mb-3 pl-[42px] text-sm text-muted-foreground">
              Live connection to Interactive Brokers for real-time quotes, option chains, and Greeks.
            </div>
          </div>
          <AppCard
            className={cn(
              'border-l-[3px]',
              gwData?.connected ? 'border-l-[rgb(var(--status-success))]' : 'border-l-transparent',
            )}
          >
            <div className="flex flex-col gap-3 items-stretch">
              <div className="mb-1 flex flex-row items-center gap-3">
                <img src={IBGatewayLogo} alt="IB Gateway" className="size-7 rounded-md" />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-row items-center gap-2">
                    <div className={cn("size-2 rounded-full", gwData?.connected ? "bg-[rgb(var(--status-success))]" : "bg-muted-foreground/50")} />
                    <div className="text-sm font-medium">{gwData?.connected ? 'Connected' : gwData?.available === false ? 'Unavailable' : 'Disconnected'}</div>
                    {gwData?.connected && gwData?.last_connected && (
                      <div className="text-xs text-muted-foreground">since {formatDateTime(gwData.last_connected, timezone)}</div>
                    )}
                  </div>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <div className="text-xs font-bold uppercase text-muted-foreground">Host</div>
                  <div className="mt-1 font-mono text-sm">{gwData?.host || '—'}</div>
                </div>
                <div>
                  <div className="text-xs font-bold uppercase text-muted-foreground">Port</div>
                  <div className="mt-1 font-mono text-sm">{gwData?.port || '—'}</div>
                </div>
                <div>
                  <div className="text-xs font-bold uppercase text-muted-foreground">Trading Mode</div>
                  <div className="mt-1 text-sm">{gwData?.trading_mode || '—'}</div>
                </div>
              </div>
              {gwData?.error && (
                <Alert variant="destructive" className="text-sm">
                  <AlertDescription className="text-xs">{gwData.error}</AlertDescription>
                </Alert>
              )}
              <div className="mt-1 flex flex-row items-center gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant={gwData?.connected ? 'secondary' : 'default'}
                  onClick={() => gatewayConnectMutation.mutate()}
                  disabled={gatewayConnectMutation.isPending}
                >
                  {gatewayConnectMutation.isPending ? <Loader2 className="mr-1 size-3.5 animate-spin" aria-hidden /> : null}
                  {gwData?.connected ? 'Reconnect' : 'Connect'}
                </Button>
                <Button type="button" size="sm" variant="ghost" onClick={() => void gatewayQuery.refetch()}>
                  Refresh Status
                </Button>
                {gwData?.vnc_url && (
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => window.open(gwData.vnc_url, '_blank', 'noopener,noreferrer')}
                  >
                    View Gateway (noVNC) <ExternalLink className="ml-1.5 inline size-3.5" aria-hidden />
                  </Button>
                )}
                <Button type="button" size="sm" variant="ghost" onClick={() => { void loadGwSettings(); setGwEditOpen(!gwEditOpen); }}>
                  {gwEditOpen ? 'Hide Settings' : 'Edit Settings'}
                </Button>
              </div>
              {!gwData?.connected && (
                <div className="text-xs text-muted-foreground">
                  After logging in to the Gateway UI (noVNC), click Connect above to establish the backend link.
                  Status will auto-refresh for 30 seconds.
                </div>
              )}
              {gwEditOpen && (
                <div className="rounded-md border border-border bg-muted/40 p-3">
                  <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                    <div>
                      <div className="mb-1 text-xs font-bold text-muted-foreground">Host</div>
                      <Input className="h-8 font-mono text-xs" value={gwForm.host} onChange={(e) => setGwForm({ ...gwForm, host: e.target.value })} placeholder="ib-gateway" />
                    </div>
                    <div>
                      <div className="mb-1 text-xs font-bold text-muted-foreground">Port</div>
                      <Input className="h-8 font-mono text-xs" value={gwForm.port} onChange={(e) => setGwForm({ ...gwForm, port: e.target.value })} placeholder="8888" />
                    </div>
                    <div>
                      <div className="mb-1 text-xs font-bold text-muted-foreground">Client ID</div>
                      <Input className="h-8 font-mono text-xs" value={gwForm.client_id} onChange={(e) => setGwForm({ ...gwForm, client_id: e.target.value })} placeholder="1" />
                    </div>
                  </div>
                  <div className="mt-3 flex flex-row items-center gap-2">
                    <Button type="button" size="sm" onClick={() => saveGwSettings.mutate()} disabled={saveGwSettings.isPending}>
                      {saveGwSettings.isPending ? <Loader2 className="mr-1 size-3.5 animate-spin" aria-hidden /> : null}
                      Save Settings
                    </Button>
                    <Button type="button" size="sm" variant="ghost" onClick={() => setGwEditOpen(false)}>Cancel</Button>
                  </div>
                </div>
              )}
            </div>
          </AppCard>

          <hr className="my-2 border-0 border-t border-border" />

          {/* ========== SECTION 3: TRADINGVIEW ========== */}
          <div>
            <div className="mb-1 flex flex-row items-center gap-3">
              <div className="rounded-md bg-muted/60 p-1.5"><BarChart2 className="size-[18px]" aria-hidden /></div>
              <div className="text-lg font-bold">TradingView</div>
              <Badge variant="outline" className="border-[rgb(var(--status-success)/0.4)] text-xs font-normal text-[rgb(var(--status-success)/1)]">Embed</Badge>
            </div>
            <div className="mb-3 pl-[42px] text-sm text-muted-foreground">
              Charting preferences for the embedded TradingView widget. Charts appear in Market Dashboard and Portfolio Workspace.
            </div>
          </div>
          <AppCard className="border-l-[3px] border-l-[rgb(var(--status-success))]">
            <div className="flex flex-col gap-4 items-stretch">
              <div className="mb-1 flex flex-row items-center gap-3">
                <img src={TradingViewLogo} alt="TradingView" className="size-7 rounded-md" />
                <div className="text-sm font-medium">Charting Preferences</div>
              </div>
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <div>
                  <div className="mb-1 text-xs font-bold uppercase text-muted-foreground">Default Interval</div>
                  <select
                    className={cn(selectSm, 'w-full max-w-[200px]')}
                    value={tvInterval}
                    onChange={(e) => setTvInterval(e.target.value)}
                  >
                    <option value="1">1m</option>
                    <option value="5">5m</option>
                    <option value="15">15m</option>
                    <option value="60">1h</option>
                    <option value="D">Daily</option>
                    <option value="W">Weekly</option>
                    <option value="M">Monthly</option>
                  </select>
                </div>
                <div>
                  <div className="mb-1 text-xs font-bold uppercase text-muted-foreground">Default Studies</div>
                  <Input
                    className="h-8 text-xs"
                    value={tvStudies}
                    onChange={(e) => setTvStudies(e.target.value)}
                    placeholder="EMA,RSI,MACD,Volume"
                  />
                  <div className="mt-1 text-xs text-muted-foreground">Comma-separated TradingView study names</div>
                </div>
              </div>
              <div className="rounded-md border border-border bg-muted/40 p-3">
                <div className="mb-1 text-sm font-semibold">About Embedded Charts</div>
                <div className="text-xs text-muted-foreground">
                  We use TradingView's public embed widget for in-app charting. This provides candlestick charts with
                  built-in studies (EMA, RSI, MACD, Bollinger, VWAP, Volume) but does <strong>not</strong> connect to
                  your personal TradingView account — Pine Scripts, saved templates, and custom indicators are not available
                  in the embed.
                </div>
                <div className="mt-1 text-xs text-muted-foreground">
                  To access your full TradingView workspace, use the pop-out button on any chart. Upgrading to the
                  TradingView Charting Library (requires a license) would enable custom data feeds and account integration
                  in a future release.
                </div>
              </div>
              <Button
                type="button"
                size="sm"
                className="self-start"
                onClick={() => tvPrefsMutation.mutate({ tv_default_interval: tvInterval, tv_default_studies: tvStudies })}
                disabled={tvPrefsMutation.isPending}
              >
                {tvPrefsMutation.isPending ? <Loader2 className="mr-1 size-3.5 animate-spin" aria-hidden /> : null}
                Save Preferences
              </Button>
            </div>
          </AppCard>

          <hr className="my-2 border-0 border-t border-border" />

          {/* ========== SECTION 4: DATA PROVIDERS ========== */}
          <div>
            <div className="mb-1 flex flex-row items-center gap-3">
              <div className="rounded-md bg-muted/60 p-1.5"><Database className="size-[18px]" aria-hidden /></div>
              <div className="text-lg font-bold">Data Providers</div>
              <Badge variant="outline" className="text-xs font-normal text-muted-foreground">Coming Soon</Badge>
            </div>
            <div className="mb-3 pl-[42px] text-sm text-muted-foreground">
              Connect third-party data sources for OHLCV, fundamentals, and index constituents.
            </div>
          </div>
          <Card className="rounded-xl border border-border shadow-xs">
            <CardContent className="pt-6">
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <div className="rounded-lg border border-border p-4 opacity-60">
                  <div className="mb-2 flex flex-row items-center gap-3">
                    <img src={FmpLogo} alt="FMP" className="size-6 rounded-md" />
                    <div className="text-sm font-semibold">Financial Modeling Prep</div>
                  </div>
                  <div className="text-xs text-muted-foreground">OHLCV, fundamentals, index constituents. API key configuration coming soon.</div>
                </div>
                <div className="rounded-lg border border-border p-4 opacity-60">
                  <div className="mb-2 flex flex-row items-center gap-3">
                    <div className="flex size-6 items-center justify-center rounded-md bg-teal-600">
                      <Database className="size-3.5 text-white" aria-hidden />
                    </div>
                    <div className="text-sm font-semibold">Twelve Data</div>
                  </div>
                  <div className="text-xs text-muted-foreground">OHLCV fallback provider. API key configuration coming soon.</div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </PageContainer>
      <Dialog
        open={editOpen}
        onOpenChange={(open) => {
          if (!open) {
            setEditOpen(false);
            setEditAccount(null);
          }
        }}
      >
        <DialogContent className="max-w-md gap-4" showCloseButton>
          <DialogHeader>
            <DialogTitle>
              Edit credentials — {editAccount ? (editAccount.account_name || editAccount.account_number) : ''}
            </DialogTitle>
          </DialogHeader>
          {editAccount && (
            <div className="flex flex-col gap-3">
              {String(editAccount.broker || '').toLowerCase() === 'tastytrade' && (
                <>
                  <Input placeholder="Client ID" value={editCredentials.client_id || ''} onChange={(e) => setEditCredentials({ ...editCredentials, client_id: e.target.value })} />
                  <Input placeholder="Client Secret (leave blank to keep)" type="password" value={editCredentials.client_secret || ''} onChange={(e) => setEditCredentials({ ...editCredentials, client_secret: e.target.value })} />
                  <Input placeholder="Refresh Token (leave blank to keep)" type="password" value={editCredentials.refresh_token || ''} onChange={(e) => setEditCredentials({ ...editCredentials, refresh_token: e.target.value })} />
                  <div className="text-xs text-muted-foreground">Enter new values to update. Leave secrets blank to keep existing.</div>
                </>
              )}
              {String(editAccount.broker || '').toLowerCase() === 'ibkr' && (
                <>
                  <Input placeholder="Flex Token (leave blank to keep)" value={editCredentials.flex_token || ''} onChange={(e) => setEditCredentials({ ...editCredentials, flex_token: e.target.value })} />
                  <Input placeholder="Query ID (leave blank to keep)" value={editCredentials.query_id || ''} onChange={(e) => setEditCredentials({ ...editCredentials, query_id: e.target.value })} />
                  <Input placeholder="Account Number (optional)" value={editCredentials.account_number || ''} onChange={(e) => setEditCredentials({ ...editCredentials, account_number: e.target.value })} />
                  <div className="text-xs text-muted-foreground">Enter new values to update. Leave blank to keep existing.</div>
                </>
              )}
            </div>
          )}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => { setEditOpen(false); setEditAccount(null); }}>Cancel</Button>
            <Button
              type="button"
              disabled={busy}
              onClick={async () => {
                if (!editAccount) return;
                const broker = String(editAccount.broker || '').toLowerCase();
                if (broker === 'tastytrade') {
                  const hasAny = editCredentials.client_id || editCredentials.client_secret || editCredentials.refresh_token;
                  if (!hasAny) {
                    toast({ title: 'Enter at least one credential to update', status: 'error' });
                    return;
                  }
                } else if (broker === 'ibkr') {
                  const hasAny = editCredentials.flex_token || editCredentials.query_id;
                  if (!hasAny) {
                    toast({ title: 'Enter at least one credential to update', status: 'error' });
                    return;
                  }
                }
                setBusy(true);
                try {
                  const creds: Record<string, string> = broker === 'tastytrade'
                    ? {
                        client_id: editCredentials.client_id || '',
                        client_secret: editCredentials.client_secret || '',
                        refresh_token: editCredentials.refresh_token || '',
                      }
                    : {
                        flex_token: editCredentials.flex_token || '',
                        query_id: editCredentials.query_id || '',
                      };
                  await accountsApi.updateCredentials(editAccount.id, {
                    broker: broker,
                    credentials: creds,
                    ...(broker === 'ibkr' && editCredentials.account_number ? { account_number: editCredentials.account_number } : {}),
                  });
                  toast({ title: 'Credentials updated', status: 'success' });
                  setEditOpen(false);
                  setEditAccount(null);
                  await loadAccounts();
                } catch (e) {
                  toast({ title: 'Update failed', description: handleApiError(e), status: 'error' });
                } finally {
                  setBusy(false);
                }
              }}
            >
              {busy ? <Loader2 className="mr-1 size-3.5 animate-spin" aria-hidden /> : null}
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <Dialog
        open={isDeleteOpen}
        onOpenChange={(open) => {
          if (!open && !deleteLoading) {
            onDeleteClose();
            setDeleteId(null);
          }
        }}
      >
        <DialogContent showCloseButton={!deleteLoading}>
          <DialogHeader>
            <DialogTitle>Delete Broker Account</DialogTitle>
          </DialogHeader>
          <DialogDescription>
            This will permanently remove the broker account connection and stored credentials for this user. You can re-connect later. Continue?
          </DialogDescription>
          <DialogFooter>
            <Button ref={cancelRef} type="button" variant="ghost" onClick={() => { if (!deleteLoading) { onDeleteClose(); setDeleteId(null); } }}>
              Cancel
            </Button>
            <Button
              type="button"
              variant="destructive"
              disabled={deleteLoading}
              onClick={async () => {
                if (!deleteId) return;
                setDeleteLoading(true);
                try {
                  await accountsApi.remove?.(deleteId);
                  toast({ title: 'Account deleted', status: 'success' });
                  await loadAccounts();
                } catch (e) {
                  toast({ title: 'Delete failed', description: handleApiError(e), status: 'error' });
                } finally {
                  setDeleteLoading(false);
                  setDeleteId(null);
                  onDeleteClose();
                }
              }}
            >
              {deleteLoading ? <Loader2 className="mr-1 size-3.5 animate-spin" aria-hidden /> : null}
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={wizardOpen}
        onOpenChange={(open: boolean) => {
          if (!open) setWizardOpen(false);
        }}
      >
        <DialogContent className="max-w-xl gap-4" showCloseButton>
          <DialogHeader>
            <div className="flex items-center gap-2">
              {step === 2 && (
                <Button type="button" aria-label="Back" variant="ghost" size="icon-sm" onClick={() => setStep(1)}>
                  <ArrowLeft className="size-4" aria-hidden />
                </Button>
              )}
              <DialogTitle>
                {step === 2 && broker ? `Connect ${brokerDisplayName(broker)}` : 'New Brokerage Connection'}
              </DialogTitle>
            </div>
          </DialogHeader>
          <div className="flex flex-col gap-4">
            {step === 1 && (
              <div className="flex flex-col gap-4 items-stretch">
                <div className="text-muted-foreground">Choose a broker to connect</div>
                <div className="grid grid-cols-2 gap-6 md:grid-cols-4">
                  <LogoTile label="Charles Schwab" srcs={[SchwabLogo]} selected={broker === 'SCHWAB'} onClick={() => { setBroker('SCHWAB'); setStep(2); }} wide />
                  <LogoTile label="Tastytrade" srcs={[TastytradeLogo]} selected={broker === 'TASTYTRADE'} onClick={() => { setBroker('TASTYTRADE'); setStep(2); }} wide />
                  <LogoTile label="Interactive Brokers" srcs={[IbkrLogo]} selected={broker === 'IBKR'} onClick={() => { setBroker('IBKR'); setStep(2); }} wide />
                  <LogoTile label="E*TRADE" srcs={[EtradeLogo]} selected={broker === 'ETRADE'} onClick={() => { setBroker('ETRADE'); setStep(2); }} wide />
                  <LogoTile label="Tradier" srcs={[TradierLogo]} selected={broker === 'TRADIER'} onClick={() => { setBroker('TRADIER'); setStep(2); }} wide />
                  <LogoTile label="Coinbase" srcs={[CoinbaseLogo]} selected={broker === 'COINBASE'} onClick={() => { setBroker('COINBASE'); setStep(2); }} wide />
                </div>
                <div className="text-sm text-muted-foreground">More brokers coming soon (Fidelity, Robinhood, Public)</div>
              </div>
            )}
            {step === 2 && broker === 'SCHWAB' && (
              <div className="flex flex-col gap-3 items-stretch">
                <div className="font-semibold">Schwab OAuth</div>
                <div className="text-sm text-muted-foreground">We’ll create a placeholder account and send you to Schwab to authorize. Ensure your redirect URI matches the portal exactly.</div>
                <div className="flex flex-row items-center gap-2">
                  <Input placeholder="Account Number (optional)" value={schwabForm.account_number} onChange={(e) => setSchwabForm({ ...schwabForm, account_number: e.target.value })} />
                  <Input placeholder="Account Name (optional)" value={schwabForm.account_name} onChange={(e) => setSchwabForm({ ...schwabForm, account_name: e.target.value })} />
                </div>
                {cfg?.redirect && <div className="text-xs text-muted-foreground">Redirect: {cfg.redirect}</div>}
              </div>
            )}
            {step === 2 && broker === 'TASTYTRADE' && (
              <div className="flex flex-col gap-3 items-stretch">
                <div className="font-semibold">Tastytrade OAuth</div>
                <div className="text-xs text-muted-foreground">
                  Create an OAuth app at{' '}
                  <a href="https://my.tastytrade.com/app.html#/manage/api-access/oauth-applications" target="_blank" rel="noopener noreferrer" style={{ textDecoration: 'underline' }}>
                    my.tastytrade.com &gt; API Access &gt; OAuth
                  </a>
                  , then generate a refresh token under Manage &gt; Create Grant.
                </div>
                <Input placeholder="Client ID" value={ttForm.client_id} onChange={(e) => setTtForm({ ...ttForm, client_id: e.target.value })} onKeyDown={(e) => { if (e.key === 'Enter') submitWizard(); }} />
                <Input placeholder="Client Secret" type="password" value={ttForm.client_secret} onChange={(e) => setTtForm({ ...ttForm, client_secret: e.target.value })} onKeyDown={(e) => { if (e.key === 'Enter') submitWizard(); }} />
                <Input placeholder="Refresh Token" type="password" value={ttForm.refresh_token} onChange={(e) => setTtForm({ ...ttForm, refresh_token: e.target.value })} onKeyDown={(e) => { if (e.key === 'Enter') submitWizard(); }} />
                <div className="text-xs text-muted-foreground">Refresh tokens never expire. Secrets are encrypted at rest.</div>
              </div>
            )}
            {step === 2 && broker === 'IBKR' && (
              <div className="flex flex-col gap-3 items-stretch">
                <div className="font-semibold">IBKR Flex Query</div>
                <Input placeholder="Flex Token" value={ibkrForm.flex_token} onChange={(e) => setIbkrForm({ ...ibkrForm, flex_token: e.target.value })} onKeyDown={(e) => { if (e.key === 'Enter') submitWizard(); }} />
                <Input placeholder="Query ID" value={ibkrForm.query_id} onChange={(e) => setIbkrForm({ ...ibkrForm, query_id: e.target.value })} onKeyDown={(e) => { if (e.key === 'Enter') submitWizard(); }} />
                <Input placeholder="IBKR Account Number (e.g. U1234567 - optional)" value={ibkrForm.account_number} onChange={(e) => setIbkrForm({ ...ibkrForm, account_number: e.target.value })} onKeyDown={(e) => { if (e.key === 'Enter') submitWizard(); }} />
                <div className="text-xs text-muted-foreground">
                  Client Portal &rarr; Reports &rarr; Flex Queries &rarr; create a query with these sections:
                  {' '}<strong>Open Positions</strong> (stocks &amp; options),
                  {' '}<strong>Trades</strong>,
                  {' '}<strong>Cash Transactions</strong> (dividends, fees, interest),
                  {' '}<strong>Option Exercises/Assignments</strong>,
                  {' '}<strong>Account Information</strong>.
                  {' '}Set the date period to <strong>Last 365 days</strong> for full history.
                  {' '}Then enable Flex Web Service, copy the Token and Query ID.
                  {' '}Account number is auto-detected from the report if left blank.
                </div>
                <div className="mt-1 text-xs text-muted-foreground/80">
                  Note: The FlexQuery API may return fewer sections than a manual download.
                  If dividends or transactions are missing, verify the sections above are included in your query.
                </div>
              </div>
            )}
            {step === 2 && broker === 'COINBASE' && (
              <div className="flex flex-col gap-3 items-stretch">
                <div className="font-semibold">Coinbase (OAuth 2.0)</div>
                <div className="text-xs text-muted-foreground">
                  Read-only wallet access (accounts and transactions). A new tab opens
                  Coinbase to approve access; this page continues automatically when
                  Coinbase redirects back.
                </div>
                <Input
                  placeholder="Account Name (optional)"
                  value={coinbaseForm.account_name}
                  onChange={(e) => setCoinbaseForm({ ...coinbaseForm, account_name: e.target.value })}
                />
                {!coinbaseForm.state ? (
                  <div className="flex flex-col gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      disabled={busy}
                      onClick={() => void handleCoinbaseAuthorize()}
                    >
                      {busy ? <Loader2 className="mr-1 size-3.5 animate-spin" aria-hidden /> : <ExternalLink className="mr-1.5 size-3.5" aria-hidden />}
                      Authorize on Coinbase
                    </Button>
                  </div>
                ) : (
                  <div className="flex flex-col gap-2">
                    <div className="text-xs text-muted-foreground">
                      Waiting for Coinbase to redirect back with the authorization code.
                    </div>
                    <Button
                      type="button"
                      size="xs"
                      variant="ghost"
                      onClick={() => setCoinbaseForm({ state: '', account_name: coinbaseForm.account_name })}
                    >
                      Start over
                    </Button>
                  </div>
                )}
              </div>
            )}
            {step === 2 && broker === 'TRADIER' && (
              <div className="flex flex-col gap-3 items-stretch">
                <div className="font-semibold">Tradier (OAuth 2.0)</div>
                <div className="text-xs text-muted-foreground">
                  Tradier supports both sandbox and live brokerage accounts. Sandbox is
                  recommended for first-time connections; you can add a live connection
                  later without removing the sandbox link.
                </div>
                <div className="flex flex-row gap-2">
                  <Button
                    type="button"
                    size="sm"
                    variant={tradierForm.env === 'sandbox' ? 'default' : 'outline'}
                    onClick={() => setTradierForm({ ...tradierForm, env: 'sandbox' })}
                  >
                    Sandbox
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant={tradierForm.env === 'live' ? 'default' : 'outline'}
                    onClick={() => setTradierForm({ ...tradierForm, env: 'live' })}
                  >
                    Live
                  </Button>
                </div>
                <Input
                  placeholder="Account Name (optional)"
                  value={tradierForm.account_name}
                  onChange={(e) => setTradierForm({ ...tradierForm, account_name: e.target.value })}
                />
                {!tradierForm.state ? (
                  <div className="flex flex-col gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      disabled={busy}
                      onClick={() => void handleTradierAuthorize(tradierForm.env)}
                    >
                      {busy ? <Loader2 className="mr-1 size-3.5 animate-spin" aria-hidden /> : <ExternalLink className="mr-1.5 size-3.5" aria-hidden />}
                      Authorize on Tradier ({tradierForm.env})
                    </Button>
                    <div className="text-xs text-muted-foreground">
                      A new tab opens Tradier's authorization page. After approving,
                      Tradier will redirect that tab back here and we'll finish the
                      exchange automatically &mdash; no verifier to paste.
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-col gap-2">
                    <div className="text-xs text-muted-foreground">
                      Waiting for Tradier to redirect back with the authorization code.
                      If nothing happens within a minute, the popup may have been
                      closed &mdash; click Start over.
                    </div>
                    <div className="flex flex-row items-center gap-2">
                      <Button
                        type="button"
                        size="xs"
                        variant="ghost"
                        onClick={() => setTradierForm({ env: tradierForm.env, state: '', account_name: tradierForm.account_name })}
                      >
                        Start over
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            )}
            {step === 2 && broker === 'ETRADE' && (
              <div className="flex flex-col gap-3 items-stretch">
                <div className="font-semibold">E*TRADE Sandbox (OAuth 1.0a)</div>
                <div className="text-xs text-muted-foreground">
                  Sandbox is the only E*TRADE tier supported in v1. Live OAuth (production keys, no sandbox-only routes) is tracked for a later phase.
                </div>
                <Input
                  placeholder="Account Name (optional)"
                  value={etradeForm.account_name}
                  onChange={(e) => setEtradeForm({ ...etradeForm, account_name: e.target.value })}
                />
                {!etradeForm.state ? (
                  <div className="flex flex-col gap-2">
                    <Button type="button" variant="outline" disabled={busy} onClick={() => void handleEtradeAuthorize()}>
                      {busy ? <Loader2 className="mr-1 size-3.5 animate-spin" aria-hidden /> : <ExternalLink className="mr-1.5 size-3.5" aria-hidden />}
                      Authorize on E*TRADE
                    </Button>
                    <div className="text-xs text-muted-foreground">
                      A new tab opens E*TRADE's sandbox authorization page. After approving, E*TRADE shows a short verifier code — come back here and paste it below.
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-col gap-2">
                    <Input
                      placeholder="Verifier code (e.g. ABCDE)"
                      value={etradeForm.verifier}
                      onChange={(e) => setEtradeForm({ ...etradeForm, verifier: e.target.value })}
                      onKeyDown={(e) => { if (e.key === 'Enter') submitWizard(); }}
                      autoFocus
                    />
                    <div className="flex flex-row items-center gap-2">
                      <Button
                        type="button"
                        size="xs"
                        variant="ghost"
                        onClick={() => setEtradeForm({ state: '', verifier: '', account_name: etradeForm.account_name })}
                      >
                        Start over
                      </Button>
                      <div className="text-xs text-muted-foreground">
                        Request tokens expire 5 minutes after authorize; click Start over if you waited too long.
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
          <DialogFooter>
            {step === 2 && broker !== 'ETRADE' && broker !== 'TRADIER' && broker !== 'COINBASE' && (
              <Button type="button" disabled={busy} onClick={() => void submitWizard()}>
                {busy ? <Loader2 className="mr-1 size-3.5 animate-spin" aria-hidden /> : null}
                Connect
              </Button>
            )}
            {step === 2 && broker === 'ETRADE' && etradeForm.state && (
              <Button type="button" disabled={busy || !etradeForm.verifier.trim()} onClick={() => void submitWizard()}>
                {busy ? <Loader2 className="mr-1 size-3.5 animate-spin" aria-hidden /> : null}
                Finish connection
              </Button>
            )}
            {step === 2 && broker === 'TRADIER' && (
              <Button type="button" variant="ghost" onClick={() => setWizardOpen(false)}>
                Close
              </Button>
            )}
            {step === 2 && broker === 'COINBASE' && (
              <Button type="button" variant="ghost" onClick={() => setWizardOpen(false)}>
                Close
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
    </TooltipProvider>
  );
};

export default SettingsConnections; 
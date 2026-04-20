import React, { useEffect, useState } from 'react';
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
import { PageHeader } from '../components/ui/Page';
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
import IBGatewayLogo from '../assets/logos/ib-gateway.svg';
import TradingViewLogo from '../assets/logos/tradingview.svg';
import FmpLogo from '../assets/logos/fmp.svg';
import { formatDateTime, formatDate } from '../utils/format';
import { useUserPreferences } from '../hooks/useUserPreferences';

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
  const [broker, setBroker] = useState<'SCHWAB' | 'TASTYTRADE' | 'IBKR' | ''>('');
  const [schwabForm, setSchwabForm] = useState({ account_number: '', account_name: '' });
  const [ibkrForm, setIbkrForm] = useState({ flex_token: '', query_id: '', account_number: '' });
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
    return b;
  };

  const LogoTile: React.FC<{ label: string; srcs: string[]; selected: boolean; onClick: () => void; wide?: boolean }> =
    ({ label, srcs, onClick, wide, selected: _selected }) => {
      const [idx, setIdx] = React.useState(0);
      const src = srcs[Math.min(idx, srcs.length - 1)];
      return (
        <button
          type="button"
          aria-label={label}
          onClick={onClick}
          className={cn(
            'flex cursor-pointer items-center justify-center rounded-md border-0 bg-transparent p-1 transition-transform hover:scale-[1.03] active:scale-[0.98]',
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
      const res: any = await accountsApi.list();
      setAccounts(res || []);
      refetchGlobalAccounts();
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
    try {
      if (cfg && !cfg.schwabConfigured) {
        toast({ title: 'Schwab OAuth not configured', description: 'Ask admin to set client_id, secret, and redirect URI on the server.', status: 'warning' });
        return;
      }
      const res: any = await aggregatorApi.schwabLink(id, false);
      const url = res?.url;
      if (url) {
        window.open(url, '_blank', 'noopener,noreferrer');
        toast({ title: 'Complete Schwab connect in the new tab', status: 'info' });
      }
    } catch (e) {
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
    setWizardOpen(true);
  };

  const submitWizard = async () => {
    try {
      setBusy(true);
      if (broker === 'SCHWAB') {
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
        window.open(url, '_blank', 'noopener,noreferrer');
        toast({ title: 'Complete Schwab connect in the new tab', status: 'info' });
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
  const queryClient = useQueryClient();
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

  return (
    <TooltipProvider delayDuration={200}>
    <div className="w-full">
      <div className="mx-auto w-full max-w-[960px]">
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
            <div className="rounded-xl border-2 border-emerald-500 bg-muted/40 p-4">
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
                <Button type="button" size="sm" onClick={() => { setShowSetupBanner(false); window.location.href = '/portfolio'; }}>
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

          {(tt?.last_error || tt?.job_error) && (
            <Alert variant="destructive">
              <AlertTitle>Tastytrade connection error</AlertTitle>
              <AlertDescription>{tt.job_error || tt.last_error}</AlertDescription>
            </Alert>
          )}

          {/* Card-per-broker layout */}
          <div className={cn("grid gap-4", accounts.length > 0 ? "grid-cols-1" : "grid-cols-1 md:grid-cols-3")}>
            {(() => {
              const brokerConfigs: { key: string; name: string; logo: string; connected: boolean }[] = [
                { key: 'IBKR', name: 'Interactive Brokers', logo: IbkrLogo, connected: accounts.some(a => String(a.broker).toUpperCase() === 'IBKR') },
                { key: 'SCHWAB', name: 'Charles Schwab', logo: SchwabLogo, connected: accounts.some(a => String(a.broker).toUpperCase() === 'SCHWAB') },
                { key: 'TASTYTRADE', name: 'Tastytrade', logo: TastytradeLogo, connected: accounts.some(a => String(a.broker).toUpperCase() === 'TASTYTRADE') },
              ];
              return brokerConfigs.map(bc => {
                const brokerAccounts = accounts.filter(a => String(a.broker).toUpperCase() === bc.key);
                const hasAccounts = brokerAccounts.length > 0;
                const brokerSyncs = syncHistory.filter((s: any) => {
                  const matchAcct = brokerAccounts.find(a => a.id === s.account_id || a.account_number === s.account_number);
                  return !!matchAcct;
                });
                const lastSync = brokerSyncs.length > 0 ? brokerSyncs[0] : null;

                return (
                  <AppCard
                    key={bc.key}
                    className={cn(
                      'border-l-[3px] transition-opacity',
                      hasAccounts ? 'border-l-emerald-500 opacity-100' : 'border-l-transparent opacity-85 hover:opacity-100',
                    )}
                  >
                    <div className="flex flex-col gap-3 items-stretch">
                      <div className="flex flex-row items-center justify-between">
                        <div className="flex flex-row items-center gap-3">
                          <img src={bc.logo} alt={bc.name} className="size-9 rounded-lg bg-muted/60 object-contain p-0.5" />
                          <div>
                            <div className="text-sm font-semibold">{bc.name}</div>
                            {lastSync && (
                              <div className="text-xs text-muted-foreground">
                                Synced {formatDateTime(lastSync.started_at, timezone)}
                                {lastSync.status === 'ERROR' ? ' — failed' : ''}
                              </div>
                            )}
                          </div>
                        </div>
                        <div className="flex flex-row items-center gap-2">
                          <div className={cn("size-2 rounded-full", hasAccounts ? "bg-emerald-500" : "bg-muted-foreground/50")} />
                          <div className={cn("text-xs font-medium", hasAccounts ? "text-foreground" : "text-muted-foreground")}>
                            {hasAccounts ? `${brokerAccounts.length} account${brokerAccounts.length > 1 ? 's' : ''}` : 'Not connected'}
                          </div>
                        </div>
                      </div>

                      {!hasAccounts && (
                        <div className="rounded-md border border-dashed border-border p-4 text-center">
                          <Button type="button" size="sm" variant="outline" onClick={() => { setBroker(bc.key as any); setStep(2); setWizardOpen(true); }}>
                            + Connect {bc.name}
                          </Button>
                        </div>
                      )}

                      {brokerAccounts.map((a: any) => (
                        <div key={a.id} className={cn("rounded-md border border-border bg-muted/40 p-3", !a.is_enabled && "opacity-60")}>
                          <div className="mb-2 flex flex-row items-center justify-between">
                            <div className="flex flex-row items-center gap-2">
                              {editNameId === a.id ? (
                                <div className="flex flex-row items-center gap-1">
                                  <Input
                                    className="h-8 w-[140px] text-xs"
                                    value={editNameValue}
                                    onChange={(e) => setEditNameValue(e.target.value)}
                                    placeholder="Account name"
                                    onKeyDown={(e) => {
                                      if (e.key === 'Enter') { accountsApi.updateAccount(a.id, { account_name: editNameValue.trim() || undefined }).then(() => { setEditNameId(null); loadAccounts(); toast({ title: 'Name updated', status: 'success' }); }).catch((err) => toast({ title: 'Update failed', status: 'error', description: handleApiError(err) })); }
                                      else if (e.key === 'Escape') setEditNameId(null);
                                    }}
                                  />
                                  <Button type="button" size="icon-xs" aria-label="Save" onClick={async () => { try { await accountsApi.updateAccount(a.id, { account_name: editNameValue.trim() || undefined }); setEditNameId(null); await loadAccounts(); toast({ title: 'Name updated', status: 'success' }); } catch (err) { toast({ title: 'Update failed', status: 'error', description: handleApiError(err) }); } }}><Check className="size-3" aria-hidden /></Button>
                                  <Button type="button" size="icon-xs" variant="ghost" aria-label="Cancel" onClick={() => setEditNameId(null)}><X className="size-3" aria-hidden /></Button>
                                </div>
                              ) : (
                                <div className="flex flex-row items-center gap-1">
                                  <div>
                                    <div className="text-sm font-medium">{a.account_name || a.account_number}</div>
                                    {a.account_number && String(a.account_number) !== String(a.account_name || '') && (
                                      <div className="text-xs text-muted-foreground">{a.account_number}</div>
                                    )}
                                    {a.data_range_start && a.data_range_end && (
                                      <div className="text-xs text-muted-foreground">Data: {formatDate(a.data_range_start, timezone)} – {formatDate(a.data_range_end, timezone)}</div>
                                    )}
                                  </div>
                                  <Button type="button" size="icon-xs" variant="ghost" aria-label="Edit name" onClick={() => { setEditNameId(a.id); setEditNameValue(a.account_name || a.account_number || ''); }}><PencilLine className="size-3.5" aria-hidden /></Button>
                                </div>
                              )}
                            </div>
                            <div className="flex flex-row items-center gap-2">
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
                              {a.sync_status && (String(a.sync_status).toLowerCase() === 'error' || String(a.sync_status).toLowerCase() === 'failed') && a.sync_error_message ? (
                                <Tooltip>
                                  <TooltipTrigger asChild>
                                    <Badge variant="outline" className="cursor-default border-destructive/40 text-destructive">{a.sync_status}</Badge>
                                  </TooltipTrigger>
                                  <TooltipContent className="max-w-xs text-background">{a.sync_error_message}</TooltipContent>
                                </Tooltip>
                              ) : (
                                a.sync_status ? <Badge variant="outline" className="font-normal">{a.sync_status}</Badge> : null
                              )}
                            </div>
                          </div>
                          <div className="mb-2 flex flex-row items-center justify-between">
                            <div className="flex flex-row items-center gap-2">
                              <Checkbox
                                checked={!!a.is_enabled}
                                onCheckedChange={async (v) => {
                                  const next = v === true;
                                  try {
                                    await accountsApi.updateAccount(a.id, { is_enabled: next });
                                    await loadAccounts();
                                    toast({ title: next ? 'Tracking in portfolio' : 'Removed from portfolio', status: 'success' });
                                  } catch (err) {
                                    toast({ title: 'Update failed', status: 'error', description: handleApiError(err) });
                                  }
                                }}
                              />
                              <div className={cn("text-xs font-medium", a.is_enabled ? "text-foreground" : "text-muted-foreground")}>
                                {a.is_enabled ? 'Track in Portfolio' : 'Not tracked'}
                              </div>
                            </div>
                          </div>
                          {String(a.sync_error_message || '').toLowerCase().includes('encrypt') || String(a.sync_error_message || '').toLowerCase().includes('credential') ? (
                            <div className="mb-2 text-xs text-destructive">Credentials invalid — please re-add this account.</div>
                          ) : null}
                          <div className="flex flex-row flex-wrap items-center gap-2">
                            {String(a.broker || '').toLowerCase() === 'schwab' && (
                              <Button type="button" size="xs" variant="outline" onClick={() => void handleConnectSchwab(a.id)} disabled={cfg ? !cfg.schwabConfigured : false}>
                                Link Schwab <ExternalLink className="ml-1.5 inline size-3.5" aria-hidden />
                              </Button>
                            )}
                            {(String(a.broker || '').toLowerCase() === 'tastytrade' || String(a.broker || '').toLowerCase() === 'ibkr') && (
                              <Button type="button" size="icon-xs" variant="outline" aria-label="Edit credentials" onClick={() => openEditModal(a)}><Pencil className="size-3.5" aria-hidden /></Button>
                            )}
                            <Button type="button" size="xs" disabled={syncingId === a.id} onClick={() => void handleSync(a.id)}>
                              {syncingId === a.id ? <Loader2 className="mr-1 size-3 animate-spin" aria-hidden /> : null}
                              Sync
                            </Button>
                            <Button type="button" size="icon-xs" variant="ghost" aria-label="Delete account" onClick={() => { setDeleteId(a.id); onDeleteOpen(); }}><Trash2 className="size-3.5" aria-hidden /></Button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </AppCard>
                );
              });
            })()}
          </div>
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
                                  ? 'border-emerald-500/40 text-emerald-800 dark:text-emerald-200'
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
                    ? 'border-emerald-500/40 text-emerald-800 dark:text-emerald-200'
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
              gwData?.connected ? 'border-l-emerald-500' : 'border-l-transparent',
            )}
          >
            <div className="flex flex-col gap-3 items-stretch">
              <div className="mb-1 flex flex-row items-center gap-3">
                <img src={IBGatewayLogo} alt="IB Gateway" className="size-7 rounded-md" />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-row items-center gap-2">
                    <div className={cn("size-2 rounded-full", gwData?.connected ? "bg-emerald-500" : "bg-muted-foreground/50")} />
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
              <Badge variant="outline" className="border-emerald-500/40 text-xs font-normal text-emerald-800 dark:text-emerald-200">Active</Badge>
            </div>
            <div className="mb-3 pl-[42px] text-sm text-muted-foreground">
              Charting preferences for the embedded TradingView widget. Charts appear in Market Dashboard and Portfolio Workspace.
            </div>
          </div>
          <AppCard className="border-l-[3px] border-l-emerald-500">
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
      </div>
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
              <DialogTitle>New Brokerage Connection</DialogTitle>
            </div>
          </DialogHeader>
          <div className="flex flex-col gap-4">
            {step === 1 && (
              <div className="flex flex-col gap-4 items-stretch">
                <div className="text-muted-foreground">Choose a broker to connect</div>
                <div className="grid grid-cols-3 gap-6">
                  <LogoTile label="Charles Schwab" srcs={[SchwabLogo]} selected={broker === 'SCHWAB'} onClick={() => { setBroker('SCHWAB'); setStep(2); }} wide />
                  <LogoTile label="Tastytrade" srcs={[TastytradeLogo]} selected={broker === 'TASTYTRADE'} onClick={() => { setBroker('TASTYTRADE'); setStep(2); }} wide />
                  <LogoTile label="Interactive Brokers" srcs={[IbkrLogo]} selected={broker === 'IBKR'} onClick={() => { setBroker('IBKR'); setStep(2); }} wide />
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
          </div>
          <DialogFooter>
            {step === 2 && (
              <Button type="button" disabled={busy} onClick={() => void submitWizard()}>
                {busy ? <Loader2 className="mr-1 size-3.5 animate-spin" aria-hidden /> : null}
                Connect
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
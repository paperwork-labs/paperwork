import React, { useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Text,
  VStack,
  HStack,
  Input,
  Button,
  Badge,
  SimpleGrid,
  useDisclosure,
  IconButton,
  Image,
  Separator,
  CardRoot,
  CardBody,
  TableScrollArea,
  TableRoot,
  TableHeader,
  TableBody,
  TableRow,
  TableColumnHeader,
  TableCell,
  DialogRoot,
  DialogBackdrop,
  DialogContent,
  DialogPositioner,
  DialogHeader,
  DialogBody,
  DialogFooter,
  DialogTitle,
  DialogDescription,
  TooltipRoot,
  TooltipTrigger,
  TooltipPositioner,
  TooltipContent,
  NativeSelectRoot,
  NativeSelectField,
} from '@chakra-ui/react';
import AppCard from '../components/ui/AppCard';
import { PageHeader } from '../components/ui/Page';
import hotToast from 'react-hot-toast';
import { accountsApi, aggregatorApi, handleApiError } from '../services/api';
import api from '../services/api';
import { useConnectJobPoll } from '../hooks/useConnectJobPoll';
import { useAuth } from '../context/AuthContext';
import { useQuery, useMutation, useQueryClient } from 'react-query';
import { FiArrowLeft, FiEdit2, FiEdit3, FiExternalLink, FiTrash2, FiActivity, FiBarChart2, FiDatabase, FiLink } from 'react-icons/fi';
import SchwabLogo from '../assets/logos/schwab.svg';
import TastytradeLogo from '../assets/logos/tastytrade.svg';
import IbkrLogo from '../assets/logos/interactive-brokers.svg';
import IBGatewayLogo from '../assets/logos/ib-gateway.svg';
import TradingViewLogo from '../assets/logos/tradingview.svg';
import FmpLogo from '../assets/logos/fmp.svg';

const SettingsConnections: React.FC = () => {
  // Temporary shim: preserve legacy `useToast()` call sites while migrating to `react-hot-toast`.
  const toast = (args: { title: string; description?: string; status?: 'success' | 'error' | 'info' | 'warning' }) => {
    const msg = args.description ? `${args.title}: ${args.description}` : args.title;
    if (args.status === 'success') return hotToast.success(args.title);
    if (args.status === 'error') return hotToast.error(msg);
    return hotToast(msg);
  };
  const { user } = useAuth();
  const [accounts, setAccounts] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ broker: 'SCHWAB', account_number: '', account_name: '', account_type: 'TAXABLE' });
  const [syncingId, setSyncingId] = useState<number | null>(null);
  const [cfg, setCfg] = useState<{ schwabConfigured: boolean; redirect?: string; schwabProbe?: any } | null>(null);
  const [tt, setTt] = useState<{ connected: boolean; available: boolean; last_error?: string; job_error?: string } | null>(null);
  const [ttForm, setTtForm] = useState({ client_id: '', client_secret: '', refresh_token: '' });
  // Wizard
  const wizard = useDisclosure();
  const [step, setStep] = useState<number>(1);
  const [broker, setBroker] = useState<'SCHWAB' | 'TASTYTRADE' | 'IBKR' | ''>('');
  const [schwabForm, setSchwabForm] = useState({ account_number: '', account_name: '' });
  const [ibkrForm, setIbkrForm] = useState({ flex_token: '', query_id: '', account_number: '' });
  const [busy, setBusy] = useState(false);
  const [deleteId, setDeleteId] = useState<number | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const {
    open: isDeleteOpen,
    onOpen: onDeleteOpen,
    onClose: onDeleteClose,
  } = useDisclosure();
  const cancelRef = React.useRef<HTMLButtonElement>(null);
  const { poll: pollConnectJob } = useConnectJobPoll();
  const [syncHistory, setSyncHistory] = useState<any[]>([]);
  const [editAccount, setEditAccount] = useState<any | null>(null);
  const [editCredentials, setEditCredentials] = useState<Record<string, string>>({});
  const editDisclosure = useDisclosure();
  const [editNameId, setEditNameId] = useState<number | null>(null);
  const [editNameValue, setEditNameValue] = useState('');

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
    editDisclosure.onOpen();
  };

  const brokerDisplayName = (b: string) => {
    const key = (b || '').toUpperCase();
    if (key === 'IBKR') return 'Interactive Brokers';
    if (key === 'SCHWAB') return 'Charles Schwab';
    if (key === 'TASTYTRADE') return 'Tastytrade';
    return b;
  };

  const LogoTile: React.FC<{ label: string; srcs: string[]; selected: boolean; onClick: () => void; wide?: boolean }> =
    ({ label, srcs, selected, onClick, wide }) => {
      const [idx, setIdx] = React.useState(0);
      const src = srcs[Math.min(idx, srcs.length - 1)];
      return (
        <Box
          as="div"
          aria-label={label}
          onClick={onClick}
          cursor="pointer"
          bg="transparent"
          border="0"
          rounded="md"
          p={1}
          _hover={{ transform: 'scale(1.03)' }}
          _active={{ transform: 'scale(0.98)' }}
          display="flex"
          alignItems="center"
          justifyContent="center"
          minH={wide ? "44px" : "60px"}
          minW={wide ? "150px" : "60px"}
        >
          <Image
            src={src}
            alt={label}
            height={wide ? "40px" : "56px"}
            width={wide ? "150px" : "56px"}
            objectFit="contain"
            onError={() => {
              if (idx < srcs.length - 1) setIdx(idx + 1);
            }}
          />
        </Box>
      );
    };

  const loadAccounts = async () => {
    try {
      const res: any = await accountsApi.list();
      setAccounts(res || []);
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
    wizard.onOpen();
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
            wizard.onClose();
            return;
          }
        } catch { /* ignore */ }
        const ttResult = await pollConnectJob(jobId, (id) => aggregatorApi.tastytradeStatus(id));
        if (ttResult.success) {
          toast({ title: 'Tastytrade connected', status: 'success' });
          await loadAccounts();
          wizard.onClose();
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
            wizard.onClose();
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
      wizard.onClose();
    } catch (e) {
      toast({ title: 'Connection failed', description: handleApiError(e), status: 'error' });
    } finally {
      setBusy(false);
    }
  };

  /* ---------- IB Gateway ---------- */
  const gatewayQuery = useQuery(
    ['ibGatewayStatus'],
    async () => {
      const res = await api.get('/portfolio/options/gateway-status');
      return res.data?.data ?? { connected: false, available: false };
    },
    { staleTime: 30000, refetchInterval: 60000 },
  );
  const gwData = gatewayQuery.data as { connected?: boolean; available?: boolean; host?: string; port?: number; client_id?: number; trading_mode?: string; last_connected?: string; error?: string; vnc_url?: string } | undefined;

  const gatewayConnectMutation = useMutation(
    () => api.post('/portfolio/options/gateway-connect'),
    {
      onSuccess: () => {
        gatewayQuery.refetch();
        hotToast.success('Gateway reconnection triggered');
      },
      onError: (err: unknown) => { hotToast.error(`Gateway connect failed: ${handleApiError(err)}`); },
    },
  );

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

  const saveGwSettings = useMutation(
    async () => {
      if (!ibkrAccount) throw new Error('No IBKR account found');
      const payload: Record<string, any> = {};
      if (gwForm.host.trim()) payload.gateway_host = gwForm.host.trim();
      if (gwForm.port.trim()) payload.gateway_port = parseInt(gwForm.port, 10);
      if (gwForm.client_id.trim()) payload.gateway_client_id = parseInt(gwForm.client_id, 10);
      await api.patch(`/accounts/${ibkrAccount.id}/gateway-settings`, payload);
    },
    {
      onSuccess: () => {
        hotToast.success('Gateway settings saved');
        setGwEditOpen(false);
      },
      onError: (err: unknown) => { hotToast.error(`Save failed: ${handleApiError(err)}`); },
    },
  );

  /* ---------- TradingView preferences ---------- */
  const queryClient = useQueryClient();
  const tvPrefs = (user as any)?.ui_preferences ?? {};
  const [tvInterval, setTvInterval] = useState(tvPrefs.tv_default_interval || 'D');
  const [tvStudies, setTvStudies] = useState<string>(tvPrefs.tv_default_studies || 'EMA,RSI,MACD,Volume');

  const tvPrefsMutation = useMutation(
    (prefs: Record<string, string>) => api.patch('/users/preferences', { ui_preferences: prefs }),
    {
      onSuccess: () => {
        queryClient.invalidateQueries('authUser');
        hotToast.success('TradingView preferences saved');
      },
      onError: (err: unknown) => { hotToast.error(`Save failed: ${handleApiError(err)}`); },
    },
  );

  return (
    <Box w="full">
      <Box w="full" maxW="960px" mx="auto">
        <PageHeader
          title="Connections"
          subtitle="Manage brokerages, live data, charting, and data provider integrations."
          actions={<Button onClick={startWizard}>+ New connection</Button>}
        />
        <VStack align="stretch" gap={6}>

          {/* ========== SECTION 1: BROKERAGES ========== */}
          <Box>
            <HStack gap={3} mb={1}>
              <Box p={1.5} borderRadius="md" bg="bg.subtle"><FiLink size={18} /></Box>
              <Text fontWeight="bold" fontSize="lg">Brokerages</Text>
            </HStack>
            <Text fontSize="sm" color="fg.muted" mb={4} pl="42px">
              Connect brokerage accounts to import positions, trades, and transactions.
            </Text>
          </Box>

          {(tt?.last_error || tt?.job_error) && (
            <Alert.Root colorPalette="red" status="error" variant="subtle">
              <Alert.Indicator />
              <Alert.Content>
                <Alert.Title>Tastytrade connection error</Alert.Title>
                <Alert.Description>{tt.job_error || tt.last_error}</Alert.Description>
              </Alert.Content>
            </Alert.Root>
          )}

          {/* Card-per-broker layout */}
          <SimpleGrid columns={{ base: 1, md: accounts.length > 0 ? 1 : 3 }} gap={4}>
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
                  <AppCard key={bc.key} borderLeftWidth="3px" borderLeftColor={hasAccounts ? 'green.500' : 'transparent'} opacity={hasAccounts ? 1 : 0.85} _hover={{ opacity: 1 }}>
                    <VStack align="stretch" gap={3}>
                      <HStack justify="space-between">
                        <HStack gap={3}>
                          <Image src={bc.logo} alt={bc.name} boxSize="36px" borderRadius="lg" objectFit="contain" p="2px" bg="bg.subtle" />
                          <Box>
                            <Text fontWeight="semibold" fontSize="sm">{bc.name}</Text>
                            {lastSync && (
                              <Text fontSize="xs" color="fg.muted">
                                Synced {new Date(lastSync.started_at).toLocaleString()}
                                {lastSync.status === 'ERROR' ? ' — failed' : ''}
                              </Text>
                            )}
                          </Box>
                        </HStack>
                        <HStack gap={2}>
                          <Box w="8px" h="8px" borderRadius="full" bg={hasAccounts ? 'green.500' : 'gray.400'} />
                          <Text fontSize="xs" fontWeight="medium" color={hasAccounts ? 'fg.default' : 'fg.muted'}>
                            {hasAccounts ? `${brokerAccounts.length} account${brokerAccounts.length > 1 ? 's' : ''}` : 'Not connected'}
                          </Text>
                        </HStack>
                      </HStack>

                      {!hasAccounts && (
                        <Box border="1px dashed" borderColor="border.subtle" p={4} borderRadius="md" textAlign="center">
                          <Button size="sm" variant="outline" onClick={() => { setBroker(bc.key as any); setStep(2); wizard.onOpen(); }}>
                            + Connect {bc.name}
                          </Button>
                        </Box>
                      )}

                      {brokerAccounts.map((a: any) => (
                        <Box key={a.id} p={3} borderWidth="1px" borderColor="border.subtle" borderRadius="md" bg="bg.subtle">
                          <HStack justify="space-between" mb={2}>
                            <HStack gap={2}>
                              {editNameId === a.id ? (
                                <HStack gap={1}>
                                  <Input size="sm" value={editNameValue} onChange={(e) => setEditNameValue(e.target.value)} placeholder="Account name" w="140px"
                                    onKeyDown={(e) => {
                                      if (e.key === 'Enter') { accountsApi.updateAccount(a.id, { account_name: editNameValue.trim() || undefined }).then(() => { setEditNameId(null); loadAccounts(); toast({ title: 'Name updated', status: 'success' }); }).catch((err) => toast({ title: 'Update failed', status: 'error', description: handleApiError(err) })); }
                                      else if (e.key === 'Escape') setEditNameId(null);
                                    }}
                                  />
                                  <IconButton aria-label="Save" size="xs" onClick={async () => { try { await accountsApi.updateAccount(a.id, { account_name: editNameValue.trim() || undefined }); setEditNameId(null); await loadAccounts(); toast({ title: 'Name updated', status: 'success' }); } catch (err) { toast({ title: 'Update failed', status: 'error', description: handleApiError(err) }); } }}>✓</IconButton>
                                  <IconButton aria-label="Cancel" size="xs" variant="ghost" onClick={() => setEditNameId(null)}>✕</IconButton>
                                </HStack>
                              ) : (
                                <HStack gap={1}>
                                  <Box>
                                    <Text fontSize="sm" fontWeight="medium">{a.account_name || a.account_number}</Text>
                                    {a.account_number && String(a.account_number) !== String(a.account_name || '') && (
                                      <Text fontSize="xs" color="fg.muted">{a.account_number}</Text>
                                    )}
                                    {a.data_range_start && a.data_range_end && (
                                      <Text fontSize="xs" color="fg.muted">Data: {new Date(a.data_range_start).toLocaleDateString()} – {new Date(a.data_range_end).toLocaleDateString()}</Text>
                                    )}
                                  </Box>
                                  <IconButton aria-label="Edit name" size="xs" variant="ghost" onClick={() => { setEditNameId(a.id); setEditNameValue(a.account_name || a.account_number || ''); }}><FiEdit3 /></IconButton>
                                </HStack>
                              )}
                            </HStack>
                            <HStack gap={1}>
                              {a.sync_status && (String(a.sync_status).toLowerCase() === 'error' || String(a.sync_status).toLowerCase() === 'failed') && a.sync_error_message ? (
                                <TooltipRoot>
                                  <TooltipTrigger asChild>
                                    <Badge variant="outline" colorPalette="red" size="sm">{a.sync_status}</Badge>
                                  </TooltipTrigger>
                                  <TooltipPositioner><TooltipContent maxW="xs">{a.sync_error_message}</TooltipContent></TooltipPositioner>
                                </TooltipRoot>
                              ) : (
                                <>
                                  <Badge colorPalette={a.is_enabled ? 'green' : 'gray'} size="sm" variant="subtle">{a.is_enabled ? 'Active' : 'Disabled'}</Badge>
                                  {a.sync_status && <Badge variant="outline" size="sm">{a.sync_status}</Badge>}
                                </>
                              )}
                            </HStack>
                          </HStack>
                          {String(a.sync_error_message || '').toLowerCase().includes('encrypt') || String(a.sync_error_message || '').toLowerCase().includes('credential') ? (
                            <Text fontSize="xs" color="red.500" mb={2}>Credentials invalid — please re-add this account.</Text>
                          ) : null}
                          <HStack gap={2} flexWrap="wrap">
                            {String(a.broker || '').toLowerCase() === 'schwab' && (
                              <Button size="xs" variant="outline" onClick={() => handleConnectSchwab(a.id)} disabled={cfg ? !cfg.schwabConfigured : false}>
                                Link Schwab <FiExternalLink style={{ marginLeft: 6 }} />
                              </Button>
                            )}
                            {(String(a.broker || '').toLowerCase() === 'tastytrade' || String(a.broker || '').toLowerCase() === 'ibkr') && (
                              <IconButton aria-label="Edit credentials" size="xs" variant="outline" onClick={() => openEditModal(a)}><FiEdit2 /></IconButton>
                            )}
                            <Button size="xs" loading={syncingId === a.id} onClick={() => handleSync(a.id)}>Sync</Button>
                            <IconButton aria-label="Delete account" size="xs" variant="ghost" onClick={() => { setDeleteId(a.id); onDeleteOpen(); }}><FiTrash2 /></IconButton>
                          </HStack>
                        </Box>
                      ))}
                    </VStack>
                  </AppCard>
                );
              });
            })()}
          </SimpleGrid>
          {syncHistory.length > 0 && (
            <Box>
              <details>
                <summary style={{ cursor: 'pointer', fontSize: '14px', fontWeight: 600, color: 'var(--chakra-colors-fg-muted)', padding: '8px 0' }}>
                  Recent syncs ({syncHistory.length})
                </summary>
                <Box mt={2}>
                  <TableScrollArea>
                    <TableRoot size="sm" variant="line">
                      <TableHeader>
                        <TableRow>
                          <TableColumnHeader>Account</TableColumnHeader>
                          <TableColumnHeader>Status</TableColumnHeader>
                          <TableColumnHeader>Started</TableColumnHeader>
                          <TableColumnHeader>Error</TableColumnHeader>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {syncHistory.slice(0, 10).map((s: any) => (
                          <TableRow key={s.id}>
                            <TableCell>
                              <Text fontSize="sm">{s.account_name || s.account_number}</Text>
                            </TableCell>
                            <TableCell>
                              <Badge colorPalette={s.status === 'SUCCESS' ? 'green' : s.status === 'ERROR' ? 'red' : 'blue'} variant="subtle" size="sm">
                                {s.status}
                              </Badge>
                              {s.duration_seconds != null && <Text as="span" fontSize="xs" color="fg.muted"> {s.duration_seconds}s</Text>}
                            </TableCell>
                            <TableCell><Text fontSize="xs">{s.started_at ? new Date(s.started_at).toLocaleString() : '—'}</Text></TableCell>
                            <TableCell>
                              {s.error_message ? (
                                <TooltipRoot>
                                  <TooltipTrigger asChild><Text fontSize="xs" lineClamp={1} maxW="200px" color="red.500">{s.error_message}</Text></TooltipTrigger>
                                  <TooltipPositioner><TooltipContent maxW="sm">{s.error_message}</TooltipContent></TooltipPositioner>
                                </TooltipRoot>
                              ) : '—'}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </TableRoot>
                  </TableScrollArea>
                </Box>
              </details>
            </Box>
          )}

          <Separator />

          {/* ========== SECTION 2: IB GATEWAY ========== */}
          <Box>
            <HStack gap={3} mb={1}>
              <Box p={1.5} borderRadius="md" bg="bg.subtle"><FiActivity size={18} /></Box>
              <Text fontWeight="bold" fontSize="lg">IB Gateway</Text>
              <Badge
                colorPalette={gwData?.connected ? 'green' : 'gray'}
                variant="subtle"
                fontSize="xs"
              >
                {gatewayQuery.isLoading ? 'Checking...' : gwData?.connected ? 'Connected' : 'Offline'}
              </Badge>
            </HStack>
            <Text fontSize="sm" color="fg.muted" mb={3} pl="42px">
              Live connection to Interactive Brokers for real-time quotes, option chains, and Greeks.
            </Text>
          </Box>
          <AppCard borderLeftWidth="3px" borderLeftColor={gwData?.connected ? 'green.500' : 'transparent'}>
            <VStack align="stretch" gap={3}>
              <HStack gap={3} mb={1}>
                <Image src={IBGatewayLogo} alt="IB Gateway" boxSize="28px" borderRadius="md" />
                <Box flex={1}>
                  <HStack gap={2}>
                    <Box w="8px" h="8px" borderRadius="full" bg={gwData?.connected ? 'green.500' : 'gray.400'} />
                    <Text fontSize="sm" fontWeight="medium">{gwData?.connected ? 'Connected' : gwData?.available === false ? 'Unavailable' : 'Disconnected'}</Text>
                    {gwData?.connected && gwData?.last_connected && (
                      <Text fontSize="xs" color="fg.muted">since {new Date(gwData.last_connected).toLocaleString()}</Text>
                    )}
                  </HStack>
                </Box>
              </HStack>
              <SimpleGrid columns={{ base: 3, md: 3 }} gap={4}>
                <Box>
                  <Text fontSize="xs" fontWeight="bold" color="fg.muted" textTransform="uppercase">Host</Text>
                  <Text fontSize="sm" mt={1} fontFamily="mono">{gwData?.host || '—'}</Text>
                </Box>
                <Box>
                  <Text fontSize="xs" fontWeight="bold" color="fg.muted" textTransform="uppercase">Port</Text>
                  <Text fontSize="sm" mt={1} fontFamily="mono">{gwData?.port || '—'}</Text>
                </Box>
                <Box>
                  <Text fontSize="xs" fontWeight="bold" color="fg.muted" textTransform="uppercase">Trading Mode</Text>
                  <Text fontSize="sm" mt={1}>{gwData?.trading_mode || '—'}</Text>
                </Box>
              </SimpleGrid>
              {gwData?.error && (
                <Alert.Root colorPalette="red" status="error" variant="subtle" size="sm">
                  <Alert.Indicator />
                  <Alert.Content>
                    <Alert.Description fontSize="xs">{gwData.error}</Alert.Description>
                  </Alert.Content>
                </Alert.Root>
              )}
              <HStack gap={2} mt={1}>
                <Button
                  size="sm"
                  colorPalette={gwData?.connected ? 'gray' : 'brand'}
                  onClick={() => gatewayConnectMutation.mutate()}
                  loading={gatewayConnectMutation.isLoading}
                >
                  {gwData?.connected ? 'Reconnect' : 'Connect'}
                </Button>
                <Button size="sm" variant="ghost" onClick={() => gatewayQuery.refetch()}>
                  Refresh Status
                </Button>
                {gwData?.vnc_url && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => window.open(gwData.vnc_url, '_blank', 'noopener,noreferrer')}
                  >
                    View Gateway (noVNC) <FiExternalLink style={{ marginLeft: 6 }} />
                  </Button>
                )}
                <Button size="sm" variant="ghost" onClick={() => { loadGwSettings(); setGwEditOpen(!gwEditOpen); }}>
                  {gwEditOpen ? 'Hide Settings' : 'Edit Settings'}
                </Button>
              </HStack>
              {gwEditOpen && (
                <Box p={3} borderWidth="1px" borderColor="border.subtle" borderRadius="md" bg="bg.subtle">
                  <SimpleGrid columns={{ base: 1, md: 3 }} gap={3}>
                    <Box>
                      <Text fontSize="xs" fontWeight="bold" color="fg.muted" mb={1}>Host</Text>
                      <Input size="sm" fontFamily="mono" value={gwForm.host} onChange={(e) => setGwForm({ ...gwForm, host: e.target.value })} placeholder="ib-gateway" />
                    </Box>
                    <Box>
                      <Text fontSize="xs" fontWeight="bold" color="fg.muted" mb={1}>Port</Text>
                      <Input size="sm" fontFamily="mono" value={gwForm.port} onChange={(e) => setGwForm({ ...gwForm, port: e.target.value })} placeholder="8888" />
                    </Box>
                    <Box>
                      <Text fontSize="xs" fontWeight="bold" color="fg.muted" mb={1}>Client ID</Text>
                      <Input size="sm" fontFamily="mono" value={gwForm.client_id} onChange={(e) => setGwForm({ ...gwForm, client_id: e.target.value })} placeholder="1" />
                    </Box>
                  </SimpleGrid>
                  <HStack mt={3} gap={2}>
                    <Button size="sm" colorPalette="brand" onClick={() => saveGwSettings.mutate()} loading={saveGwSettings.isLoading}>
                      Save Settings
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setGwEditOpen(false)}>Cancel</Button>
                  </HStack>
                </Box>
              )}
            </VStack>
          </AppCard>

          <Separator />

          {/* ========== SECTION 3: TRADINGVIEW ========== */}
          <Box>
            <HStack gap={3} mb={1}>
              <Box p={1.5} borderRadius="md" bg="bg.subtle"><FiBarChart2 size={18} /></Box>
              <Text fontWeight="bold" fontSize="lg">TradingView</Text>
              <Badge colorPalette="green" variant="subtle" fontSize="xs">Active</Badge>
            </HStack>
            <Text fontSize="sm" color="fg.muted" mb={3} pl="42px">
              Charting preferences for the embedded TradingView widget. Charts appear in Market Dashboard and Portfolio Workspace.
            </Text>
          </Box>
          <AppCard borderLeftWidth="3px" borderLeftColor="green.500">
            <VStack align="stretch" gap={4}>
              <HStack gap={3} mb={1}>
                <Image src={TradingViewLogo} alt="TradingView" boxSize="28px" borderRadius="md" />
                <Text fontSize="sm" fontWeight="medium">Charting Preferences</Text>
              </HStack>
              <SimpleGrid columns={{ base: 1, md: 2 }} gap={4}>
                <Box>
                  <Text fontSize="xs" fontWeight="bold" color="fg.muted" textTransform="uppercase" mb={1}>Default Interval</Text>
                  <NativeSelectRoot size="sm">
                    <NativeSelectField
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
                    </NativeSelectField>
                  </NativeSelectRoot>
                </Box>
                <Box>
                  <Text fontSize="xs" fontWeight="bold" color="fg.muted" textTransform="uppercase" mb={1}>Default Studies</Text>
                  <Input
                    size="sm"
                    value={tvStudies}
                    onChange={(e) => setTvStudies(e.target.value)}
                    placeholder="EMA,RSI,MACD,Volume"
                  />
                  <Text fontSize="xs" color="fg.muted" mt={1}>Comma-separated TradingView study names</Text>
                </Box>
              </SimpleGrid>
              <Box p={3} borderWidth="1px" borderColor="border.subtle" borderRadius="md" bg="bg.subtle">
                <Text fontSize="sm" fontWeight="semibold" mb={1}>About Embedded Charts</Text>
                <Text fontSize="xs" color="fg.muted">
                  We use TradingView's public embed widget for in-app charting. This provides candlestick charts with
                  built-in studies (EMA, RSI, MACD, Bollinger, VWAP, Volume) but does <strong>not</strong> connect to
                  your personal TradingView account — Pine Scripts, saved templates, and custom indicators are not available
                  in the embed.
                </Text>
                <Text fontSize="xs" color="fg.muted" mt={1}>
                  To access your full TradingView workspace, use the pop-out button on any chart. Upgrading to the
                  TradingView Charting Library (requires a license) would enable custom data feeds and account integration
                  in a future release.
                </Text>
              </Box>
              <Button
                size="sm"
                colorPalette="brand"
                alignSelf="flex-start"
                onClick={() => tvPrefsMutation.mutate({ tv_default_interval: tvInterval, tv_default_studies: tvStudies })}
                loading={tvPrefsMutation.isLoading}
              >
                Save Preferences
              </Button>
            </VStack>
          </AppCard>

          <Separator />

          {/* ========== SECTION 4: DATA PROVIDERS ========== */}
          <Box>
            <HStack gap={3} mb={1}>
              <Box p={1.5} borderRadius="md" bg="bg.subtle"><FiDatabase size={18} /></Box>
              <Text fontWeight="bold" fontSize="lg">Data Providers</Text>
              <Badge colorPalette="gray" variant="subtle" fontSize="xs">Coming Soon</Badge>
            </HStack>
            <Text fontSize="sm" color="fg.muted" mb={3} pl="42px">
              Connect third-party data sources for OHLCV, fundamentals, and index constituents.
            </Text>
          </Box>
          <CardRoot bg="bg.card" borderWidth="1px" borderColor="border.subtle" borderRadius="xl">
            <CardBody>
              <SimpleGrid columns={{ base: 1, md: 2 }} gap={4}>
                <Box p={4} borderWidth="1px" borderColor="border.subtle" borderRadius="lg" opacity={0.6}>
                  <HStack gap={3} mb={2}>
                    <Image src={FmpLogo} alt="FMP" boxSize="24px" borderRadius="md" />
                    <Text fontWeight="semibold" fontSize="sm">Financial Modeling Prep</Text>
                  </HStack>
                  <Text fontSize="xs" color="fg.muted">OHLCV, fundamentals, index constituents. API key configuration coming soon.</Text>
                </Box>
                <Box p={4} borderWidth="1px" borderColor="border.subtle" borderRadius="lg" opacity={0.6}>
                  <HStack gap={3} mb={2}>
                    <Box w="24px" h="24px" borderRadius="md" bg="teal.600" display="flex" alignItems="center" justifyContent="center">
                      <FiDatabase color="white" size={14} />
                    </Box>
                    <Text fontWeight="semibold" fontSize="sm">Twelve Data</Text>
                  </HStack>
                  <Text fontSize="xs" color="fg.muted">OHLCV fallback provider. API key configuration coming soon.</Text>
                </Box>
              </SimpleGrid>
            </CardBody>
          </CardRoot>
        </VStack>
      </Box>
      <DialogRoot placement="center"
        open={editDisclosure.open}
        onOpenChange={(d) => {
          if (!d.open) {
            editDisclosure.onClose();
            setEditAccount(null);
          }
        }}
      >
        <DialogBackdrop />
        <DialogPositioner>
          <DialogContent maxW="md">
          <DialogHeader>
            <DialogTitle>Edit credentials — {editAccount ? (editAccount.account_name || editAccount.account_number) : ''}</DialogTitle>
          </DialogHeader>
          <DialogBody>
            {editAccount && (
              <VStack align="stretch" gap={3}>
                {String(editAccount.broker || '').toLowerCase() === 'tastytrade' && (
                  <>
                    <Input placeholder="Client ID" value={editCredentials.client_id || ''} onChange={(e) => setEditCredentials({ ...editCredentials, client_id: e.target.value })} />
                    <Input placeholder="Client Secret (leave blank to keep)" type="password" value={editCredentials.client_secret || ''} onChange={(e) => setEditCredentials({ ...editCredentials, client_secret: e.target.value })} />
                    <Input placeholder="Refresh Token (leave blank to keep)" type="password" value={editCredentials.refresh_token || ''} onChange={(e) => setEditCredentials({ ...editCredentials, refresh_token: e.target.value })} />
                    <Text fontSize="xs" color="fg.muted">Enter new values to update. Leave secrets blank to keep existing.</Text>
                  </>
                )}
                {String(editAccount.broker || '').toLowerCase() === 'ibkr' && (
                  <>
                    <Input placeholder="Flex Token (leave blank to keep)" value={editCredentials.flex_token || ''} onChange={(e) => setEditCredentials({ ...editCredentials, flex_token: e.target.value })} />
                    <Input placeholder="Query ID (leave blank to keep)" value={editCredentials.query_id || ''} onChange={(e) => setEditCredentials({ ...editCredentials, query_id: e.target.value })} />
                    <Input placeholder="Account Number (optional)" value={editCredentials.account_number || ''} onChange={(e) => setEditCredentials({ ...editCredentials, account_number: e.target.value })} />
                    <Text fontSize="xs" color="fg.muted">Enter new values to update. Leave blank to keep existing.</Text>
                  </>
                )}
              </VStack>
            )}
          </DialogBody>
          <DialogFooter>
            <Button variant="outline" onClick={() => { editDisclosure.onClose(); setEditAccount(null); }}>Cancel</Button>
            <Button
              loading={busy}
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
                  editDisclosure.onClose();
                  setEditAccount(null);
                  await loadAccounts();
                } catch (e) {
                  toast({ title: 'Update failed', description: handleApiError(e), status: 'error' });
                } finally {
                  setBusy(false);
                }
              }}
            >
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
        </DialogPositioner>
      </DialogRoot>
      <DialogRoot placement="center"
        open={isDeleteOpen}
        onOpenChange={(d) => {
          if (!d.open && !deleteLoading) {
            onDeleteClose();
            setDeleteId(null);
          }
        }}
      >
        <DialogBackdrop />
        <DialogPositioner>
          <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Broker Account</DialogTitle>
          </DialogHeader>
          <DialogBody>
            <DialogDescription>
              This will permanently remove the broker account connection and stored credentials for this user. You can re-connect later. Continue?
            </DialogDescription>
          </DialogBody>
          <DialogFooter>
            <Button ref={cancelRef} onClick={() => { if (!deleteLoading) { onDeleteClose(); setDeleteId(null); } }}>
              Cancel
            </Button>
            <Button colorScheme="red" ml={3} loading={deleteLoading} onClick={async () => {
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
            }}>
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
        </DialogPositioner>
      </DialogRoot>

      <DialogRoot placement="center" open={wizard.open} onOpenChange={(d) => { if (!d.open) wizard.onClose(); }}>
        <DialogBackdrop />
        <DialogPositioner>
          <DialogContent maxW="xl">
          <DialogHeader>
            <HStack gap={2}>
              {step === 2 && (
                <IconButton aria-label="Back" variant="ghost" size="sm" onClick={() => setStep(1)}>
                  <FiArrowLeft />
                </IconButton>
              )}
              <DialogTitle>New Brokerage Connection</DialogTitle>
            </HStack>
          </DialogHeader>
          <DialogBody>
            {step === 1 && (
              <VStack align="stretch" gap={4}>
                <Text color="fg.muted">Choose a broker to connect</Text>
                <SimpleGrid columns={{ base: 3, md: 3 }} gap={6}>
                  <LogoTile label="Charles Schwab" srcs={[SchwabLogo]} selected={broker === 'SCHWAB'} onClick={() => { setBroker('SCHWAB'); setStep(2); }} wide />
                  <LogoTile label="Tastytrade" srcs={[TastytradeLogo]} selected={broker === 'TASTYTRADE'} onClick={() => { setBroker('TASTYTRADE'); setStep(2); }} wide />
                  <LogoTile label="Interactive Brokers" srcs={[IbkrLogo]} selected={broker === 'IBKR'} onClick={() => { setBroker('IBKR'); setStep(2); }} wide />
                </SimpleGrid>
                <Text fontSize="sm" color="fg.muted">More brokers coming soon (Fidelity, Robinhood, Public)</Text>
              </VStack>
            )}
            {step === 2 && broker === 'SCHWAB' && (
              <VStack align="stretch" gap={3}>
                <Text fontWeight="semibold">Schwab OAuth</Text>
                <Text fontSize="sm" color="fg.muted">We’ll create a placeholder account and send you to Schwab to authorize. Ensure your redirect URI matches the portal exactly.</Text>
                <HStack>
                  <Input placeholder="Account Number (optional)" value={schwabForm.account_number} onChange={(e) => setSchwabForm({ ...schwabForm, account_number: e.target.value })} />
                  <Input placeholder="Account Name (optional)" value={schwabForm.account_name} onChange={(e) => setSchwabForm({ ...schwabForm, account_name: e.target.value })} />
                </HStack>
                {cfg?.redirect && <Text fontSize="xs" color="fg.muted">Redirect: {cfg.redirect}</Text>}
              </VStack>
            )}
            {step === 2 && broker === 'TASTYTRADE' && (
              <VStack align="stretch" gap={3}>
                <Text fontWeight="semibold">Tastytrade OAuth</Text>
                <Text fontSize="xs" color="fg.muted">
                  Create an OAuth app at{' '}
                  <a href="https://my.tastytrade.com/app.html#/manage/api-access/oauth-applications" target="_blank" rel="noopener noreferrer" style={{ textDecoration: 'underline' }}>
                    my.tastytrade.com &gt; API Access &gt; OAuth
                  </a>
                  , then generate a refresh token under Manage &gt; Create Grant.
                </Text>
                <Input placeholder="Client ID" value={ttForm.client_id} onChange={(e) => setTtForm({ ...ttForm, client_id: e.target.value })} onKeyDown={(e) => { if (e.key === 'Enter') submitWizard(); }} />
                <Input placeholder="Client Secret" type="password" value={ttForm.client_secret} onChange={(e) => setTtForm({ ...ttForm, client_secret: e.target.value })} onKeyDown={(e) => { if (e.key === 'Enter') submitWizard(); }} />
                <Input placeholder="Refresh Token" type="password" value={ttForm.refresh_token} onChange={(e) => setTtForm({ ...ttForm, refresh_token: e.target.value })} onKeyDown={(e) => { if (e.key === 'Enter') submitWizard(); }} />
                <Text fontSize="xs" color="fg.muted">Refresh tokens never expire. Secrets are encrypted at rest.</Text>
              </VStack>
            )}
            {step === 2 && broker === 'IBKR' && (
              <VStack align="stretch" gap={3}>
                <Text fontWeight="semibold">IBKR Flex Query</Text>
                <Input placeholder="Flex Token" value={ibkrForm.flex_token} onChange={(e) => setIbkrForm({ ...ibkrForm, flex_token: e.target.value })} onKeyDown={(e) => { if (e.key === 'Enter') submitWizard(); }} />
                <Input placeholder="Query ID" value={ibkrForm.query_id} onChange={(e) => setIbkrForm({ ...ibkrForm, query_id: e.target.value })} onKeyDown={(e) => { if (e.key === 'Enter') submitWizard(); }} />
                <Input placeholder="IBKR Account Number (e.g. U1234567 - optional)" value={ibkrForm.account_number} onChange={(e) => setIbkrForm({ ...ibkrForm, account_number: e.target.value })} onKeyDown={(e) => { if (e.key === 'Enter') submitWizard(); }} />
                <Text fontSize="xs" color="fg.muted">
                  Client Portal &rarr; Reports &rarr; Flex Queries &rarr; create a query with these sections:
                  {' '}<strong>Open Positions</strong> (stocks &amp; options),
                  {' '}<strong>Trades</strong>,
                  {' '}<strong>Cash Transactions</strong> (dividends, fees, interest),
                  {' '}<strong>Option Exercises/Assignments</strong>,
                  {' '}<strong>Account Information</strong>.
                  {' '}Set the date period to <strong>Last 365 days</strong> for full history.
                  {' '}Then enable Flex Web Service, copy the Token and Query ID.
                  {' '}Account number is auto-detected from the report if left blank.
                </Text>
                <Text fontSize="xs" color="fg.subtle" mt={1}>
                  Note: The FlexQuery API may return fewer sections than a manual download.
                  If dividends or transactions are missing, verify the sections above are included in your query.
                </Text>
              </VStack>
            )}
          </DialogBody>
          <DialogFooter>
            {step === 2 && <Button loading={busy} onClick={submitWizard}>Connect</Button>}
          </DialogFooter>
        </DialogContent>
        </DialogPositioner>
      </DialogRoot>
    </Box>
  );
};

export default SettingsConnections; 
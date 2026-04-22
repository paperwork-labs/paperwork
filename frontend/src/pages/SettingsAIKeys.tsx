import React from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import hotToast from 'react-hot-toast';

import { PageHeader } from '@/components/ui/Page';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { aiKeysApi, handleApiError } from '@/services/api';

/**
 * `SettingsAIKeys` — BYOK (Bring Your Own Key) UI.
 *
 * Lets a Pro+ user paste an OpenAI or Anthropic API key so the native
 * AgentBrain routes their tokens through the user's key instead of the
 * platform budget. Storage is write-only: the plaintext key is never
 * displayed again after save — only a `provider` stub + `has_key`
 * flag come back from `GET /settings/ai-keys`.
 *
 * Four explicit states (per `no-silent-fallback.mdc`):
 *   - loading: initial status fetch
 *   - error:   status fetch failed (retry surface, no silent fallback)
 *   - empty:   no key stored (save form is the only control)
 *   - data:    key stored (save = rotate; remove available with confirm)
 */

type Provider = 'openai' | 'anthropic';

const SettingsAIKeys: React.FC = () => {
  const [provider, setProvider] = React.useState<Provider>('openai');
  const [apiKey, setApiKey] = React.useState('');

  const statusQuery = useQuery({
    queryKey: ['settings', 'ai-keys', 'status'],
    queryFn: aiKeysApi.status,
  });

  const saveMutation = useMutation({
    mutationFn: aiKeysApi.upsert,
    onSuccess: (data) => {
      setApiKey('');
      hotToast.success(
        statusQuery.data?.has_key
          ? `Key rotated (${data.provider ?? 'unknown'})`
          : `Key saved (${data.provider ?? 'unknown'})`,
      );
      void statusQuery.refetch();
    },
    onError: (e) => hotToast.error(handleApiError(e)),
  });

  const removeMutation = useMutation({
    mutationFn: aiKeysApi.remove,
    onSuccess: () => {
      hotToast.success('Key removed');
      void statusQuery.refetch();
    },
    onError: (e) => hotToast.error(handleApiError(e)),
  });

  const handleRemove = React.useCallback(() => {
    // Native confirm keeps a11y + keyboard-navigability for free without
    // pulling in a modal dependency just for a destructive BYOK action.
    const ok = window.confirm(
      'Remove the stored API key? You can paste a new one at any time.',
    );
    if (!ok) return;
    removeMutation.mutate();
  }, [removeMutation]);

  const hasKey = statusQuery.data?.has_key ?? false;
  const storedProvider = statusQuery.data?.provider ?? null;
  const saveLabel = hasKey ? 'Rotate key' : 'Save key';

  const renderStatus = () => {
    if (statusQuery.isLoading) {
      return (
        <p className="text-xs text-muted-foreground">Loading key status…</p>
      );
    }
    if (statusQuery.isError) {
      return (
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <span>Status:</span>
          <span className="text-[rgb(var(--status-danger)/1)]">
            Could not check key status
          </span>
          <Button
            type="button"
            size="xs"
            variant="outline"
            onClick={() => void statusQuery.refetch()}
            disabled={statusQuery.isFetching}
          >
            {statusQuery.isFetching ? 'Retrying…' : 'Retry'}
          </Button>
        </div>
      );
    }
    if (!hasKey) {
      return (
        <p className="text-xs text-muted-foreground">
          Status: no key on file. Paste a key to enable BYOK routing.
        </p>
      );
    }
    return (
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <span>
          Status: key saved ({storedProvider ?? 'unknown'}). Paste a new value
          above and click <span className="font-medium">Rotate key</span> to
          replace it.
        </span>
        <Button
          type="button"
          size="xs"
          variant="outline"
          onClick={handleRemove}
          disabled={removeMutation.isPending}
        >
          {removeMutation.isPending ? 'Removing…' : 'Remove key'}
        </Button>
      </div>
    );
  };

  return (
    <div className="w-full">
      <div className="mx-auto w-full max-w-[860px]">
        <PageHeader
          title="AI Keys"
          subtitle="Paste your OpenAI or Anthropic API key. Keys are encrypted at rest and never displayed again after save."
        />
        <Card>
          <CardContent className="space-y-4 pt-6">
            <div>
              <Label htmlFor="ai-provider">Provider</Label>
              <select
                id="ai-provider"
                className="mt-1 h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                value={provider}
                onChange={(e) => setProvider(e.target.value as Provider)}
              >
                <option value="openai">openai</option>
                <option value="anthropic">anthropic</option>
              </select>
            </div>
            <div>
              <Label htmlFor="ai-key">API key</Label>
              <Input
                id="ai-key"
                type="password"
                autoComplete="off"
                value={apiKey}
                placeholder={hasKey ? 'Paste new key to rotate' : 'Paste key'}
                onChange={(e) => setApiKey(e.target.value)}
              />
            </div>
            <div className="flex items-center gap-2">
              <Button
                type="button"
                disabled={saveMutation.isPending || !apiKey.trim()}
                onClick={() =>
                  saveMutation.mutate({ provider, api_key: apiKey.trim() })
                }
              >
                {saveMutation.isPending ? 'Saving…' : saveLabel}
              </Button>
            </div>
            {renderStatus()}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default SettingsAIKeys;

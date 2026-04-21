import React from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import hotToast from 'react-hot-toast';

import { PageHeader } from '@/components/ui/Page';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { aiKeysApi, handleApiError } from '@/services/api';

const SettingsAIKeys: React.FC = () => {
  const [provider, setProvider] = React.useState<'openai' | 'anthropic'>('openai');
  const [apiKey, setApiKey] = React.useState('');

  const statusQuery = useQuery({
    queryKey: ['settings', 'ai-keys', 'status'],
    queryFn: aiKeysApi.status,
  });
  const saveMutation = useMutation({
    mutationFn: aiKeysApi.upsert,
    onSuccess: () => {
      setApiKey('');
      hotToast.success('Key saved');
      void statusQuery.refetch();
    },
    onError: (e) => hotToast.error(handleApiError(e)),
  });

  return (
    <div className="w-full">
      <div className="mx-auto w-full max-w-[860px]">
        <PageHeader
          title="AI Keys"
          subtitle="Paste your OpenAI or Anthropic API key. This is write-only; the plaintext key is never shown again."
        />
        <Card>
          <CardContent className="space-y-4 pt-6">
            <div>
              <Label htmlFor="ai-provider">Provider</Label>
              <select
                id="ai-provider"
                className="mt-1 h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                value={provider}
                onChange={(e) => setProvider(e.target.value as 'openai' | 'anthropic')}
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
                placeholder="Paste key"
                onChange={(e) => setApiKey(e.target.value)}
              />
            </div>
            <Button
              type="button"
              disabled={saveMutation.isPending || !apiKey.trim()}
              onClick={() => saveMutation.mutate({ provider, api_key: apiKey.trim() })}
            >
              Save key
            </Button>
            <p className="text-xs text-muted-foreground">
              Status:{' '}
              {statusQuery.isLoading
                ? 'Loading...'
                : statusQuery.isError
                  ? 'Unavailable'
                  : statusQuery.data?.has_key
                    ? `Saved (${statusQuery.data.provider ?? 'unknown'})`
                    : 'Not configured'}
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default SettingsAIKeys;

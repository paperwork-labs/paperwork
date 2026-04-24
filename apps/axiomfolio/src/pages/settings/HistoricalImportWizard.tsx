import React from 'react';
import { accountsApi, handleApiError } from '@/services/api';

type SourceType = 'xml' | 'csv';

export default function HistoricalImportWizard(): React.ReactElement {
  const [step, setStep] = React.useState<1 | 2 | 3>(1);
  const [source, setSource] = React.useState<SourceType>('xml');
  const [accountId, setAccountId] = React.useState('');
  const [dateFrom, setDateFrom] = React.useState('');
  const [dateTo, setDateTo] = React.useState('');
  const [xmlContent, setXmlContent] = React.useState('');
  const [csvContent, setCsvContent] = React.useState('');
  const [error, setError] = React.useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [runId, setRunId] = React.useState<number | null>(null);

  const canContinueSource = accountId.trim().length > 0;
  const canContinueDateRange =
    source === 'xml' ? Boolean(dateFrom && dateTo) : Boolean(csvContent.trim());

  const submit = async () => {
    setError(null);
    setIsSubmitting(true);
    try {
      const id = Number(accountId);
      if (!Number.isFinite(id) || id <= 0) {
        throw new Error('Account ID must be a positive number');
      }
      if (source === 'xml') {
        const run = await accountsApi.startHistoricalImport(id, {
          date_from: dateFrom,
          date_to: dateTo,
          xml_content: xmlContent.trim() ? xmlContent : undefined,
        });
        setRunId((run as { id?: number }).id ?? null);
      } else {
        const run = await accountsApi.startHistoricalImportCsv(id, {
          csv_content: csvContent,
        });
        setRunId((run as { id?: number }).id ?? null);
      }
      setStep(3);
    } catch (e) {
      setError(handleApiError(e));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-3xl space-y-6 p-4">
      <div>
        <h1 className="text-2xl font-semibold">Historical Import Wizard</h1>
        <p className="text-sm text-muted-foreground">
          Backfill older portfolio activity from IBKR Flex XML or CSV exports.
        </p>
      </div>

      {step === 1 && (
        <section className="space-y-4 rounded-lg border p-4">
          <h2 className="text-lg font-medium">Step 1: Source</h2>
          <div className="space-y-2">
            <label className="block text-sm font-medium" htmlFor="account-id">
              Account ID
            </label>
            <input
              id="account-id"
              className="w-full rounded-md border bg-background px-3 py-2 text-sm"
              placeholder="e.g. 12"
              value={accountId}
              onChange={(e) => setAccountId(e.target.value)}
            />
          </div>
          <fieldset className="space-y-2">
            <legend className="text-sm font-medium">Import source</legend>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="radio"
                name="source"
                checked={source === 'xml'}
                onChange={() => setSource('xml')}
              />
              IBKR Flex XML
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="radio"
                name="source"
                checked={source === 'csv'}
                onChange={() => setSource('csv')}
              />
              CSV Activity Statement
            </label>
          </fieldset>
          <button
            type="button"
            className="rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-50"
            disabled={!canContinueSource}
            onClick={() => setStep(2)}
          >
            Continue
          </button>
        </section>
      )}

      {step === 2 && (
        <section className="space-y-4 rounded-lg border p-4">
          <h2 className="text-lg font-medium">Step 2: Date Range</h2>
          {source === 'xml' ? (
            <>
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="space-y-1 text-sm">
                  <span className="font-medium">From</span>
                  <input
                    type="date"
                    className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                    value={dateFrom}
                    onChange={(e) => setDateFrom(e.target.value)}
                  />
                </label>
                <label className="space-y-1 text-sm">
                  <span className="font-medium">To</span>
                  <input
                    type="date"
                    className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                    value={dateTo}
                    onChange={(e) => setDateTo(e.target.value)}
                  />
                </label>
              </div>
              <label className="block space-y-1 text-sm">
                <span className="font-medium">Optional XML content upload</span>
                <textarea
                  className="h-40 w-full rounded-md border bg-background px-3 py-2 font-mono text-xs"
                  value={xmlContent}
                  onChange={(e) => setXmlContent(e.target.value)}
                  placeholder="Paste Flex XML here if you want to upload directly."
                />
              </label>
            </>
          ) : (
            <label className="block space-y-1 text-sm">
              <span className="font-medium">CSV content</span>
              <textarea
                className="h-56 w-full rounded-md border bg-background px-3 py-2 font-mono text-xs"
                value={csvContent}
                onChange={(e) => setCsvContent(e.target.value)}
                placeholder="Paste CSV export rows here."
              />
            </label>
          )}
          <div className="flex gap-2">
            <button
              type="button"
              className="rounded-md border px-3 py-2 text-sm"
              onClick={() => setStep(1)}
            >
              Back
            </button>
            <button
              type="button"
              className="rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground disabled:opacity-50"
              disabled={!canContinueDateRange || isSubmitting}
              onClick={submit}
            >
              {isSubmitting ? 'Starting import...' : 'Start import'}
            </button>
          </div>
          {error ? <p className="text-sm text-destructive">{error}</p> : null}
        </section>
      )}

      {step === 3 && (
        <section className="space-y-3 rounded-lg border p-4">
          <h2 className="text-lg font-medium">Step 3: Confirm</h2>
          <p className="text-sm text-muted-foreground">
            Historical import queued successfully{runId ? ` (run #${runId})` : ''}.
          </p>
          <p className="text-sm">
            Historical orders imported via backfill will not receive automatic AI explanations; the Explainer processes trades from the last 24h only.
          </p>
          <button
            type="button"
            className="rounded-md border px-3 py-2 text-sm"
            onClick={() => {
              setStep(1);
              setError(null);
            }}
          >
            Start another import
          </button>
        </section>
      )}
    </div>
  );
}

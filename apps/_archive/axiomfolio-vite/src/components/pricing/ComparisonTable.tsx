import React from 'react';

import type { PricingCatalogResponse, PricingFeature } from '@/types/pricing';
import { Check } from 'lucide-react';

interface ComparisonTableProps {
  catalog: PricingCatalogResponse;
}

export const ComparisonTable: React.FC<ComparisonTableProps> = ({ catalog }) => {
  const featureMap = new Map<string, PricingFeature>();
  for (const tier of catalog.tiers) {
    for (const feature of tier.features) {
      if (!featureMap.has(feature.key)) {
        featureMap.set(feature.key, feature);
      }
    }
  }
  const allFeatures = Array.from(featureMap.values());
  return (
    <div className="overflow-x-auto rounded-xl border border-border bg-card">
      <table className="w-full min-w-[860px] text-left text-sm">
        <thead className="border-b border-border bg-muted/40">
          <tr>
            <th className="px-4 py-3">Feature</th>
            {catalog.tiers.map((tier) => (
              <th key={tier.tier} className="px-4 py-3">{tier.name}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {allFeatures.map((feature) => (
            <tr key={feature.key} className="border-b border-border">
              <td className="px-4 py-3">
                <div className="font-medium">{feature.title}</div>
                <div className="text-xs text-muted-foreground">{feature.description}</div>
              </td>
              {catalog.tiers.map((tier) => {
                const has = tier.features.some((f) => f.key === feature.key);
                return (
                  <td key={`${feature.key}:${tier.tier}`} className="px-4 py-3">
                    {has ? (
                      <>
                        <Check aria-hidden className="size-4 text-emerald-600" />
                        <span className="sr-only">Included</span>
                      </>
                    ) : (
                      <span className="text-muted-foreground">-</span>
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default ComparisonTable;

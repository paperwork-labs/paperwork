import React from 'react';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

interface ByokAnomalyCardProps {
  count: number | null;
  isLoading?: boolean;
  isError?: boolean;
}

export const ByokAnomalyCard: React.FC<ByokAnomalyCardProps> = ({
  count,
  isLoading = false,
  isError = false,
}) => {
  let body = 'No anomalies';
  if (isLoading) body = 'Loading...';
  else if (isError) body = 'Unavailable';
  else if (typeof count === 'number' && count > 0) body = `${count} anomalies`;

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">BYOK Anomaly</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-2xl font-semibold">{body}</p>
      </CardContent>
    </Card>
  );
};

export default ByokAnomalyCard;

// Stub: token validation + password POST land with the backend reset flow. See KNOWLEDGE.md D143.

import React from 'react';
import { useSearchParams } from 'react-router-dom';

import AuthLayout from '@/components/layout/AuthLayout';
import AppCard from '@/components/ui/AppCard';

const ResetPassword: React.FC = () => {
  const [params] = useSearchParams();
  const token = params.get('token');

  return (
    <AuthLayout>
      <AppCard>
        <h2 className="text-xl font-semibold tracking-tight text-card-foreground">Reset password</h2>
        <p className="mt-3 text-sm text-muted-foreground">
          Password reset will open soon — meanwhile, contact support@axiomfolio.com.
        </p>
        <span className="sr-only">
          {token ? 'This URL includes a reset token.' : 'No reset token was provided in the URL.'}
        </span>
      </AppCard>
    </AuthLayout>
  );
};

export default ResetPassword;

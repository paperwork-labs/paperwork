// Stub: backend endpoint lands in a separate PR. See KNOWLEDGE.md D143.

import React, { useState } from 'react';

import AuthLayout from '@/components/layout/AuthLayout';
import AppCard from '@/components/ui/AppCard';
import FormField from '@/components/ui/FormField';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

const SUCCESS_MESSAGE =
  "If an account exists with that email, we'll send reset instructions to it. Meanwhile, email support@axiomfolio.com if you need help sooner.";

const ForgotPassword: React.FC = () => {
  const [email, setEmail] = useState('');
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitted(true);
  };

  return (
    <AuthLayout>
      <AppCard>
        {submitted ? (
          <p className="text-sm text-foreground">{SUCCESS_MESSAGE}</p>
        ) : (
          <form className="flex flex-col gap-4" onSubmit={handleSubmit} noValidate>
            <div>
              <h2 className="text-xl font-semibold tracking-tight text-card-foreground">Forgot password</h2>
              <p className="mt-1 text-sm text-muted-foreground">Enter your email and we&apos;ll send reset instructions if we find an account.</p>
            </div>
            <FormField label="Email" htmlFor="forgot-email">
              <Input
                id="forgot-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                autoComplete="email"
              />
            </FormField>
            <Button type="submit" className="h-11 rounded-lg">
              Send reset link
            </Button>
          </form>
        )}
      </AppCard>
    </AuthLayout>
  );
};

export default ForgotPassword;

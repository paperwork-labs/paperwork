import AuthLayout from '@/components/layout/AuthLayout';
import { SupportPlaceholderCard } from '@/components/auth/SupportPlaceholderCard';

const ForgotPassword = () => {
  return (
    <AuthLayout>
      <SupportPlaceholderCard title="Forgot password" message="Forgot password support is coming" />
    </AuthLayout>
  );
};

export default ForgotPassword;

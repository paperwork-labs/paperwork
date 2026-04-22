import AuthLayout from '@/components/layout/AuthLayout';
import { SupportPlaceholderCard } from '@/components/auth/SupportPlaceholderCard';

const ResetPassword = () => {
  return (
    <AuthLayout>
      <SupportPlaceholderCard title="Password reset" message="Password reset coming" />
    </AuthLayout>
  );
};

export default ResetPassword;

import React from 'react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@/test/testing-library';
import { ChakraProvider } from '@chakra-ui/react';
import { MemoryRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { system } from '../../theme/system';

afterEach(() => cleanup());

/**
 * Minimal replicas of the route guard components so we can test the
 * route structure without pulling in the full app and all lazy-loaded pages.
 */

const RequireAuth: React.FC<{ children: React.ReactElement }> = ({ children }) => {
  return children;
};

const mockUseAuth = vi.fn();

const RequireAdmin: React.FC<{ children?: React.ReactElement }> = ({ children }) => {
  const { role } = mockUseAuth();
  if (role !== 'admin') {
    return <Navigate to="/" replace />;
  }
  return children ?? <Outlet />;
};

const SettingsShell: React.FC = () => (
  <div>
    <span>Settings Shell</span>
    <Outlet />
  </div>
);
const SettingsProfile: React.FC = () => <div>Settings Profile Page</div>;
const AdminDashboard: React.FC = () => <div>Admin Dashboard Page</div>;
const HomePage: React.FC = () => <div>Home Page</div>;

function TestApp({ initialRoute }: { initialRoute: string }) {
  return (
    <ChakraProvider value={system}>
      <MemoryRouter initialEntries={[initialRoute]}>
        <Routes>
          <Route path="/" element={<RequireAuth><Outlet /></RequireAuth>}>
            <Route index element={<HomePage />} />
            <Route path="settings" element={<SettingsShell />}>
              <Route index element={<Navigate to="profile" replace />} />
              <Route path="profile" element={<SettingsProfile />} />
              <Route element={<RequireAdmin />}>
                <Route path="admin/dashboard" element={<AdminDashboard />} />
              </Route>
            </Route>
          </Route>
        </Routes>
      </MemoryRouter>
    </ChakraProvider>
  );
}

describe('Route guards', () => {
  it('non-admin user can access /settings/profile', async () => {
    mockUseAuth.mockReturnValue({ role: 'viewer' });
    render(<TestApp initialRoute="/settings/profile" />);
    await waitFor(() => {
      expect(screen.getByText('Settings Profile Page')).toBeTruthy();
    });
  });

  it('non-admin user is redirected from /settings/admin/dashboard', async () => {
    mockUseAuth.mockReturnValue({ role: 'viewer' });
    render(<TestApp initialRoute="/settings/admin/dashboard" />);
    await waitFor(() => {
      expect(screen.queryByText('Admin Dashboard Page')).toBeNull();
      expect(screen.getByText('Home Page')).toBeTruthy();
    });
  });

  it('admin user can access /settings/admin/dashboard', async () => {
    mockUseAuth.mockReturnValue({ role: 'admin' });
    render(<TestApp initialRoute="/settings/admin/dashboard" />);
    await waitFor(() => {
      expect(screen.getByText('Admin Dashboard Page')).toBeTruthy();
    });
  });

  it('admin user can access /settings/profile', async () => {
    mockUseAuth.mockReturnValue({ role: 'admin' });
    render(<TestApp initialRoute="/settings/profile" />);
    await waitFor(() => {
      expect(screen.getByText('Settings Profile Page')).toBeTruthy();
    });
  });
});

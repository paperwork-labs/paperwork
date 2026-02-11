import React from 'react';
import { Box, Flex, VStack, Button, Text, IconButton, TooltipRoot, TooltipTrigger, TooltipPositioner, TooltipContent, useMediaQuery } from '@chakra-ui/react';
import { NavLink, Outlet } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { FiBell, FiGrid, FiLock, FiSliders, FiUser, FiShield, FiActivity } from 'react-icons/fi';

const MenuLink: React.FC<{ to: string; children: React.ReactNode }> = ({ to, children }) => {
  const activeBg = 'bg.muted';
  const hoverBg = 'bg.subtle';
  const activeColor = 'fg.default';
  const textColor = 'fg.muted';
  return (
    <NavLink to={to} style={({ isActive }) => ({ textDecoration: 'none' })}>
      {({ isActive }) => (
        <Button
          variant="ghost"
          justifyContent="flex-start"
          width="100%"
          bg={isActive ? activeBg : 'transparent'}
          color={isActive ? activeColor : textColor}
          _hover={{ bg: hoverBg, color: 'fg.default' }}
        >
          {children}
        </Button>
      )}
    </NavLink>
  );
};

const SettingsShell: React.FC = () => {
  const { user } = useAuth();
  const sectionColor = 'fg.muted';
  const [isDesktop] = useMediaQuery(['(min-width: 48em)']);

  const iconNav = (to: string, label: string, icon: React.ReactNode) => (
    <NavLink to={to} style={{ textDecoration: 'none' }}>
      {({ isActive }) => (
        <TooltipRoot>
          <TooltipTrigger asChild>
            <IconButton
              aria-label={label}
              variant={isActive ? 'solid' : 'ghost'}
              colorScheme={isActive ? 'brand' : undefined}
              size="md"
            >
              {icon}
            </IconButton>
          </TooltipTrigger>
          <TooltipPositioner>
            <TooltipContent>{label}</TooltipContent>
          </TooltipPositioner>
        </TooltipRoot>
      )}
    </NavLink>
  );

  return (
    <Flex gap={2} p={0} w="full" minW={0} overflowX="hidden">
      {isDesktop ? (
        <Box w="160px" flexShrink={0}>
          <VStack align="stretch" gap={1}>
            <Text fontSize="sm" color={sectionColor} px={2}>ACCOUNT</Text>
            <MenuLink to="/settings/profile">Profile</MenuLink>
            <MenuLink to="/settings/preferences">Preferences</MenuLink>
            <MenuLink to="/settings/brokerages">Brokerages</MenuLink>
            <MenuLink to="/settings/notifications">Notifications</MenuLink>
            <MenuLink to="/settings/security">Security</MenuLink>
            {user?.role === 'admin' && (
              <>
                <Text fontSize="sm" color={sectionColor} px={2} mt={4}>ADMIN</Text>
                <MenuLink to="/settings/admin/dashboard">Dashboard</MenuLink>
                <MenuLink to="/settings/admin/users">Users</MenuLink>
                <MenuLink to="/settings/admin/jobs">Jobs</MenuLink>
                <MenuLink to="/settings/admin/schedules">Schedules</MenuLink>
              </>
            )}
          </VStack>
        </Box>
      ) : (
        <Box w="56px" flexShrink={0}>
          <VStack align="stretch" gap={2}>
            {iconNav('/settings/profile', 'Profile', <FiUser />)}
            {iconNav('/settings/preferences', 'Preferences', <FiSliders />)}
            {iconNav('/settings/brokerages', 'Brokerages', <FiShield />)}
            {iconNav('/settings/notifications', 'Notifications', <FiBell />)}
            {iconNav('/settings/security', 'Security', <FiLock />)}
            {user?.role === 'admin' ? (
              <>
                {iconNav('/settings/admin/dashboard', 'Admin Dashboard', <FiGrid />)}
                {iconNav('/settings/admin/users', 'Admin Users', <FiUser />)}
                {iconNav('/settings/admin/jobs', 'Admin Jobs', <FiActivity />)}
                {iconNav('/settings/admin/schedules', 'Admin Schedules', <FiGrid />)}
              </>
            ) : null}
          </VStack>
        </Box>
      )}
      <Box flex="1" minW={0} overflowX="hidden">
        <Outlet />
      </Box>
    </Flex>
  );
};

export default SettingsShell;





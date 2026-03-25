import React from 'react';
import { Box, Flex, VStack, Button, Text, IconButton, TooltipRoot, TooltipTrigger, TooltipPositioner, TooltipContent, useMediaQuery } from '@chakra-ui/react';
import { NavLink, Outlet } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { FiBell, FiSliders, FiUser, FiShield, FiActivity, FiCpu } from 'react-icons/fi';

const MenuLink: React.FC<{ to: string; children: React.ReactNode }> = ({ to, children }) => (
  <NavLink to={to} style={() => ({ textDecoration: 'none' })}>
    {({ isActive }) => (
      <Button
        variant="ghost"
        justifyContent="flex-start"
        width="100%"
        bg={isActive ? 'bg.subtle' : 'transparent'}
        color={isActive ? 'fg.default' : 'fg.muted'}
        fontWeight={isActive ? 'semibold' : 'medium'}
        borderLeft={isActive ? '2px solid' : '2px solid transparent'}
        borderLeftColor={isActive ? 'amber.500' : 'transparent'}
        _hover={{ bg: 'bg.muted', color: 'fg.default' }}
        transition="all 200ms ease"
      >
        {children}
      </Button>
    )}
  </NavLink>
);

const SettingsShell: React.FC = () => {
  const { user } = useAuth();
  const [isDesktop] = useMediaQuery(['(min-width: 48em)']);

  const iconNav = (to: string, label: string, icon: React.ReactNode) => (
    <NavLink to={to} style={{ textDecoration: 'none' }}>
      {({ isActive }) => (
        <TooltipRoot>
          <TooltipTrigger asChild>
            <IconButton
              aria-label={label}
              variant={isActive ? 'solid' : 'ghost'}
              bg={isActive ? 'amber.500' : undefined}
              color={isActive ? 'white' : undefined}
              _hover={isActive ? { bg: 'amber.400' } : undefined}
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
            <Text fontSize="2xs" color="fg.subtle" px={2} fontWeight="semibold" letterSpacing="0.08em" textTransform="uppercase">Account</Text>
            <MenuLink to="/settings/profile">Profile</MenuLink>
            <MenuLink to="/settings/preferences">Preferences</MenuLink>
            <MenuLink to="/settings/connections">Connections</MenuLink>
            <MenuLink to="/settings/notifications">Notifications</MenuLink>
            {user?.role === 'admin' && (
              <>
                <Text fontSize="2xs" color="fg.subtle" px={2} mt={4} fontWeight="semibold" letterSpacing="0.08em" textTransform="uppercase">Admin</Text>
                <MenuLink to="/settings/admin/system">System Status</MenuLink>
                <MenuLink to="/settings/admin/users">Users</MenuLink>
                <MenuLink to="/settings/admin/agent">Agent</MenuLink>
              </>
            )}
          </VStack>
        </Box>
      ) : (
        <Box w="56px" flexShrink={0}>
          <VStack align="stretch" gap={2}>
            {iconNav('/settings/profile', 'Profile', <FiUser />)}
            {iconNav('/settings/preferences', 'Preferences', <FiSliders />)}
            {iconNav('/settings/connections', 'Connections', <FiShield />)}
            {iconNav('/settings/notifications', 'Notifications', <FiBell />)}
            {user?.role === 'admin' ? (
              <>
                {iconNav('/settings/admin/system', 'System Status', <FiActivity />)}
                {iconNav('/settings/admin/users', 'Users', <FiUser />)}
                {iconNav('/settings/admin/agent', 'Agent', <FiCpu />)}
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





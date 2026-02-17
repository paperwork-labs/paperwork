import React from 'react';
import {
  Box,
  HStack,
  VStack,
  Text,
  Badge,
  StatRoot,
  StatLabel,
  StatHelpText,
  StatValueText,
  StatUpIndicator,
  StatDownIndicator,
  CardRoot,
  CardBody,
  PopoverRoot,
  PopoverTrigger,
  PopoverContent,
  PopoverBody,
  Icon,
  Flex,
  SimpleGrid,
} from '@chakra-ui/react';
import { FiInfo, FiTrendingUp, FiTrendingDown, FiDollarSign } from 'react-icons/fi';
import AppDivider from './AppDivider';
import { useUserPreferences } from '../../hooks/useUserPreferences';
import { formatMoney } from '../../utils/format';

export interface AccountData {
  account_id: string;
  account_name: string;
  account_type: string;
  broker: string;
  total_value: number;
  unrealized_pnl: number;
  unrealized_pnl_pct?: number;
  positions_count: number;
  allocation_pct: number;
  available_funds?: number;
  buying_power?: number;
  day_change?: number;
  day_change_pct?: number;
}

export interface AccountSelectorProps {
  accounts: AccountData[];
  selectedAccount: string;
  onAccountChange: (accountId: string) => void;
  showAllOption?: boolean;
  showSummary?: boolean;
  size?: 'sm' | 'md' | 'lg';
  variant?: 'simple' | 'detailed';
}

const AccountSelector: React.FC<AccountSelectorProps> = ({
  accounts = [],
  selectedAccount,
  onAccountChange,
  showAllOption = true,
  showSummary = true,
  size = 'md',
  variant = 'detailed',
}) => {
  const bgColor = 'bg.card';
  const borderColor = 'border.subtle';
  const hoverBg = 'bg.panel';
  const { currency } = useUserPreferences();

  // Calculate totals
  const totalValue = accounts.reduce((sum, acc) => sum + acc.total_value, 0);
  const totalPnL = accounts.reduce((sum, acc) => sum + acc.unrealized_pnl, 0);
  const totalPnLPct = totalValue > 0 ? (totalPnL / (totalValue - totalPnL)) * 100 : 0;
  const totalPositions = accounts.reduce((sum, acc) => sum + acc.positions_count, 0);

  const formatCurrency = (amount: number) =>
    formatMoney(amount || 0, currency, { maximumFractionDigits: 0, minimumFractionDigits: 0 });

  const formatPercentage = (pct: number | undefined) => {
    if (pct === undefined || pct === null || Number.isNaN(pct)) return '0.00%';
    return `${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%`;
  };

  const getChangeColor = (value: number | undefined) => {
    if (value === undefined || value === null || Number.isNaN(value)) return 'fg.subtle';
    return value >= 0 ? 'status.success' : 'status.danger';
  };

  const selectedAccountData = accounts.find((acc) => acc.account_id === selectedAccount);

  if (variant === 'simple') {
    return (
      <select
        value={selectedAccount}
        onChange={(e: React.ChangeEvent<HTMLSelectElement>) => onAccountChange(e.target.value)}
        disabled={!accounts.length}
        style={{
          maxWidth: 250,
          padding: '8px 10px',
          borderRadius: 10,
          border: '1px solid var(--chakra-colors-border-subtle)',
          background: 'var(--chakra-colors-bg-input)',
          color: 'var(--chakra-colors-fg-default)',
          fontSize: 14,
        }}
      >
        {showAllOption ? <option value="all">All Accounts ({accounts.length})</option> : null}
        {accounts.map((account) => (
          <option key={account.account_id} value={account.account_id}>
            {account.account_name} - {formatCurrency(account.total_value)}
          </option>
        ))}
      </select>
    );
  }

  return (
    <CardRoot bg={bgColor} borderWidth="1px" borderColor={borderColor} borderRadius="xl">
      <CardBody>
        <VStack gap={4} align="stretch">
          <HStack justify="space-between" align="center">
            <HStack gap={3}>
              <Text fontSize="sm" fontWeight="semibold" color="fg.default">
                Account
              </Text>
              <Badge variant="subtle" colorPalette="blue">
                {accounts.length} linked
              </Badge>
            </HStack>

            <PopoverRoot>
              <PopoverTrigger asChild>
                <HStack
                  gap={2}
                  cursor="pointer"
                  px={3}
                  py={2}
                  borderRadius="lg"
                  borderWidth="1px"
                  borderColor={borderColor}
                  _hover={{ bg: hoverBg }}
                >
                  <Text fontSize="sm" fontWeight="semibold">
                    {selectedAccountData?.account_name || 'All Accounts'}
                  </Text>
                  <Icon as={FiInfo} color="fg.muted" />
                </HStack>
              </PopoverTrigger>
              <PopoverContent>
                <PopoverBody>
                  <VStack gap={2} align="stretch">
                    {showAllOption ? (
                      <Box
                        px={3}
                        py={2}
                        borderRadius="lg"
                        cursor="pointer"
                        _hover={{ bg: hoverBg }}
                        onClick={() => onAccountChange('all')}
                      >
                        <Text fontSize="sm" fontWeight="semibold">
                          All Accounts
                        </Text>
                        <Text fontSize="xs" color="fg.muted">
                          Combined portfolio view
                        </Text>
                      </Box>
                    ) : null}

                    {accounts.map((account) => (
                      <Box
                        key={account.account_id}
                        px={3}
                        py={2}
                        borderRadius="lg"
                        cursor="pointer"
                        _hover={{ bg: hoverBg }}
                        onClick={() => onAccountChange(account.account_id)}
                      >
                        <HStack justify="space-between">
                          <Box>
                            <Text fontSize="sm" fontWeight="semibold">
                              {account.account_name}
                            </Text>
                            <Text fontSize="xs" color="fg.muted">
                              {account.broker} • {account.account_type}
                            </Text>
                          </Box>
                          <Text fontSize="sm" fontWeight="semibold">
                            {formatCurrency(account.total_value)}
                          </Text>
                        </HStack>
                      </Box>
                    ))}
                  </VStack>
                </PopoverBody>
              </PopoverContent>
            </PopoverRoot>
          </HStack>

          {showSummary ? (
            <>
              <AppDivider />

              <SimpleGrid columns={{ base: 2, md: 4 }} gap={4}>
                <StatRoot size="sm">
                  <StatLabel>Total Value</StatLabel>
                  <StatValueText fontSize="md">{formatCurrency(totalValue)}</StatValueText>
                </StatRoot>
                <StatRoot size="sm">
                  <StatLabel>Total P&L</StatLabel>
                  <StatValueText fontSize="md" color={getChangeColor(totalPnL)}>
                    {totalPnL >= 0 ? <StatUpIndicator /> : <StatDownIndicator />}
                    {formatCurrency(totalPnL)}
                  </StatValueText>
                  <StatHelpText>{formatPercentage(totalPnLPct)}</StatHelpText>
                </StatRoot>
                <StatRoot size="sm">
                  <StatLabel>Accounts</StatLabel>
                  <StatValueText fontSize="md">{accounts.length}</StatValueText>
                </StatRoot>
                <StatRoot size="sm">
                  <StatLabel>Total Positions</StatLabel>
                  <StatValueText fontSize="md">{totalPositions}</StatValueText>
                </StatRoot>
              </SimpleGrid>

              {selectedAccountData && selectedAccount !== 'all' ? (
                <Box>
                  <Text fontSize="sm" fontWeight="semibold" mb={2}>
                    Selected account
                  </Text>
                  <SimpleGrid columns={{ base: 2, md: 4 }} gap={4}>
                    <StatRoot size="sm">
                      <StatLabel>Account Value</StatLabel>
                      <StatValueText fontSize="md">
                        {formatCurrency(selectedAccountData?.total_value || 0)}
                      </StatValueText>
                    </StatRoot>
                    <StatRoot size="sm">
                      <StatLabel>Unrealized P&L</StatLabel>
                      <StatValueText fontSize="md" color={getChangeColor(selectedAccountData?.unrealized_pnl)}>
                        {(selectedAccountData?.unrealized_pnl || 0) >= 0 ? <StatUpIndicator /> : <StatDownIndicator />}
                        {formatCurrency(selectedAccountData?.unrealized_pnl || 0)}
                      </StatValueText>
                      <StatHelpText>{formatPercentage(selectedAccountData.unrealized_pnl_pct)}</StatHelpText>
                    </StatRoot>
                    <StatRoot size="sm">
                      <StatLabel>Positions</StatLabel>
                      <StatValueText fontSize="md">{selectedAccountData?.positions_count || 0}</StatValueText>
                    </StatRoot>
                    <StatRoot size="sm">
                      <StatLabel>Allocation</StatLabel>
                      <StatValueText fontSize="md">
                        {(selectedAccountData?.allocation_pct ?? 0).toFixed(1)}%
                      </StatValueText>
                    </StatRoot>
                  </SimpleGrid>

                  {(selectedAccountData?.buying_power !== undefined ||
                    selectedAccountData?.available_funds !== undefined ||
                    selectedAccountData?.day_change !== undefined) ? (
                    <Box mt={4}>
                      <AppDivider />
                      <Flex mt={4} gap={4} wrap="wrap">
                        {selectedAccountData?.buying_power !== undefined ? (
                          <HStack gap={2}>
                            <Icon as={FiDollarSign} color="fg.muted" />
                            <Text fontSize="sm" color="fg.muted">
                              Buying Power:
                            </Text>
                            <Text fontSize="sm" fontWeight="semibold">
                              {formatCurrency(selectedAccountData.buying_power)}
                            </Text>
                          </HStack>
                        ) : null}
                        {selectedAccountData?.available_funds !== undefined ? (
                          <HStack gap={2}>
                            <Icon as={FiDollarSign} color="fg.muted" />
                            <Text fontSize="sm" color="fg.muted">
                              Available:
                            </Text>
                            <Text fontSize="sm" fontWeight="semibold">
                              {formatCurrency(selectedAccountData.available_funds)}
                            </Text>
                          </HStack>
                        ) : null}
                        {selectedAccountData?.day_change !== undefined ? (
                          <HStack gap={2}>
                            <Icon
                              as={selectedAccountData.day_change >= 0 ? FiTrendingUp : FiTrendingDown}
                              color={getChangeColor(selectedAccountData.day_change)}
                            />
                            <Text fontSize="sm" color="fg.muted">
                              Day:
                            </Text>
                            <Text fontSize="sm" fontWeight="semibold" color={getChangeColor(selectedAccountData.day_change)}>
                              {formatCurrency(selectedAccountData.day_change)}
                            </Text>
                          </HStack>
                        ) : null}
                      </Flex>
                    </Box>
                  ) : null}
                </Box>
              ) : null}
            </>
          ) : null}
        </VStack>
      </CardBody>
    </CardRoot>
  );
};

export default AccountSelector;



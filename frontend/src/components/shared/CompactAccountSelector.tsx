import React from 'react';
import {
  NativeSelectRoot,
  NativeSelectField,
  NativeSelectIndicator,
} from '@chakra-ui/react';

export interface CompactAccountSelectorProps {
  value: string;
  onChange: (value: string) => void;
  disabled: boolean;
  accounts: Array<{ account_number: string; account_name?: string }>;
  width?: string | number;
}

export const CompactAccountSelector: React.FC<CompactAccountSelectorProps> = ({
  value,
  onChange,
  disabled,
  accounts,
  width = '100%',
}) => (
  <NativeSelectRoot size="sm" width={width} disabled={disabled}>
    <NativeSelectField value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="all">All Accounts</option>
      <option value="taxable">Taxable</option>
      <option value="ira">Tax-Deferred (IRA)</option>
      {accounts.map((a) => (
        <option key={a.account_number} value={a.account_number}>
          {a.account_name || a.account_number}
        </option>
      ))}
    </NativeSelectField>
    <NativeSelectIndicator />
  </NativeSelectRoot>
);

export default CompactAccountSelector;

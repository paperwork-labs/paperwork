import React from 'react';
import { Box, Text, HStack } from '@chakra-ui/react';

export interface HistogramBin {
  label: string;
  value: number;
  /** Optional semantic color zone: 'danger' | 'neutral' | 'success' */
  zone?: 'danger' | 'neutral' | 'success';
}

const ZONE_COLORS: Record<string, { bar: string; label: string }> = {
  danger: { bar: 'var(--chakra-colors-status-danger)', label: 'var(--chakra-colors-status-danger)' },
  success: { bar: 'var(--chakra-colors-status-success)', label: 'var(--chakra-colors-status-success)' },
  neutral: { bar: 'var(--chakra-colors-brand-400)', label: 'var(--chakra-colors-fg-muted)' },
};

interface BarHistogramProps {
  bins: HistogramBin[];
  height?: number;
  title?: string;
  subtitle?: string;
  showValues?: boolean;
}

const BarHistogram: React.FC<BarHistogramProps> = ({
  bins,
  height = 160,
  title,
  subtitle,
  showValues = true,
}) => {
  const maxVal = Math.max(...bins.map((b) => b.value), 1);

  return (
    <Box>
      {title && <Text fontSize="sm" fontWeight="semibold" mb={1}>{title}</Text>}
      {subtitle && <Text fontSize="xs" color="fg.muted" mb={2}>{subtitle}</Text>}
      <Box display="flex" gap="3px" alignItems="flex-end" h={`${height}px`}>
        {bins.map((b) => {
          const pct = (b.value / maxVal) * 100;
          const zone = b.zone || 'neutral';
          const colors = ZONE_COLORS[zone];
          return (
            <Box key={b.label} flex="1" display="flex" flexDirection="column" alignItems="center" justifyContent="flex-end" h="full">
              {showValues && b.value > 0 && (
                <Text fontSize="9px" fontWeight="medium" color={colors.label} mb="2px">{b.value}</Text>
              )}
              <Box
                w="full"
                borderRadius="4px"
                minH="2px"
                h={`${Math.max(pct, 2)}%`}
                bg={colors.bar}
                opacity={zone === 'neutral' ? 0.75 : 0.85}
                title={`${b.label}: ${b.value}`}
                transition="height 0.3s ease"
              />
              <Text fontSize="8px" color="fg.muted" mt="3px" textAlign="center" lineHeight="1">{b.label}</Text>
            </Box>
          );
        })}
      </Box>
    </Box>
  );
};

export default BarHistogram;

export interface TimeSeriesBarProps {
  data: Array<{ date: string; values: Array<{ value: number; color: string; label: string }> }>;
  height?: number;
  title?: string;
  legend?: Array<{ color: string; label: string }>;
}

export const TimeSeriesBar: React.FC<TimeSeriesBarProps> = ({
  data,
  height = 140,
  title,
  legend,
}) => {
  const maxVal = 100;
  const fmtDate = (d: string) => {
    const parts = d.split('-');
    return parts.length >= 3 ? `${parts[1]}/${parts[2]}` : d.slice(5);
  };

  return (
    <Box>
      {title && <Text fontSize="sm" fontWeight="semibold" mb={1}>{title}</Text>}
      {legend && (
        <HStack gap={3} mb={2}>
          {legend.map((l) => (
            <HStack key={l.label} gap={1}>
              <Box w="10px" h="10px" bg={l.color} borderRadius="sm" opacity={0.7} />
              <Text fontSize="xs" color="fg.muted">{l.label}</Text>
            </HStack>
          ))}
        </HStack>
      )}
      <Box position="relative" h={`${height}px`} display="flex" alignItems="flex-end" gap="1px">
        {data.map((pt, i) => (
          <Box key={i} flex="1" position="relative" h="100%">
            {pt.values.map((v, vi) => {
              const h = (v.value / maxVal) * 100;
              return (
                <Box
                  key={vi}
                  position="absolute"
                  bottom="0"
                  w="full"
                  bg={v.color}
                  h={`${h}%`}
                  opacity={0.5 + vi * 0.15}
                  borderRadius="sm"
                  title={`${pt.date}: ${v.value.toFixed(1)}% ${v.label}`}
                  transition="height 0.3s ease"
                />
              );
            })}
          </Box>
        ))}
      </Box>
      <HStack justify="space-between" mt={1}>
        <Text fontSize="9px" color="fg.muted">{fmtDate(data[0]?.date || '')}</Text>
        {data.length > 10 && (
          <Text fontSize="9px" color="fg.muted">{fmtDate(data[Math.floor(data.length / 2)]?.date || '')}</Text>
        )}
        <Text fontSize="9px" color="fg.muted">{fmtDate(data[data.length - 1]?.date || '')}</Text>
      </HStack>
    </Box>
  );
};

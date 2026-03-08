import React from "react";
import { Box, HStack, Heading, Text, type BoxProps, type StackProps } from "@chakra-ui/react";

export function Page({ children, ...props }: BoxProps & { children: React.ReactNode }) {
  return (
    <Box w="full" maxW="1200px" mx="auto" px={{ base: 4, md: 6 }} py={{ base: 6, md: 8 }} {...props}>
      {children}
    </Box>
  );
}

export interface PageHeaderProps extends StackProps {
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
  rightContent?: React.ReactNode;
}

export function PageHeader({
  title,
  subtitle,
  actions,
  rightContent,
  ...props
}: PageHeaderProps) {
  return (
    <Box mb={6}>
      <HStack align="flex-start" justify="space-between" gap={4} {...props}>
        <Box>
          <Heading size="lg" letterSpacing="-0.02em" color="fg.default">
            {title}
          </Heading>
          {subtitle ? (
            <Text mt={1} fontSize="sm" color="fg.muted">
              {subtitle}
            </Text>
          ) : null}
        </Box>
        {rightContent}
      </HStack>
      {actions ? <Box mt={2}>{actions}</Box> : null}
    </Box>
  );
}

export default PageHeader;



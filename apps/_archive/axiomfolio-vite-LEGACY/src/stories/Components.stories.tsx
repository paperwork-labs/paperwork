import React from "react";
import { Eye } from "lucide-react";
import AppCard from "../components/ui/AppCard";
import FormField from "../components/ui/FormField";
import StatCard from "../components/shared/StatCard";
import { useColorMode } from "../theme/colorMode";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default {
  title: "DesignSystem/Components",
};

export const Basics = () => {
  const { colorMode, toggleColorMode } = useColorMode();
  return (
    <div className="p-6">
      <div className="mb-5 flex flex-row items-center justify-between">
        <div>
          <div className="text-lg font-semibold text-foreground">Components</div>
          <div className="text-sm text-muted-foreground">Mode: {colorMode}</div>
        </div>
        <Button type="button" variant="outline" onClick={toggleColorMode}>
          Toggle mode
        </Button>
      </div>

      <AppCard className="max-w-[520px]">
        <div className="flex flex-col gap-4 items-stretch">
          <div className="text-base font-semibold text-foreground">Card</div>
          <FormField label="Email" required helperText="We’ll never share your email.">
            <Input placeholder="you@example.com" />
          </FormField>
          <FormField label="Password" required>
            <div className="flex gap-2">
              <Input className="flex-1" placeholder="••••••••" type="password" />
              <Button type="button" size="icon-sm" variant="ghost" className="text-muted-foreground" aria-label="Show password">
                <Eye className="size-4" />
              </Button>
            </div>
          </FormField>
          <div className="flex flex-row justify-end gap-2">
            <Button type="button" variant="outline">
              Cancel
            </Button>
            <Button type="button">Continue</Button>
          </div>
        </div>
      </AppCard>

      <div className="mt-8 max-w-[520px]">
        <div className="mb-3 text-base font-semibold text-foreground">StatCard (full)</div>
        <AppCard>
          <div className="flex flex-col gap-3 items-stretch">
            <StatCard variant="full" label="Tracked Symbols" value={512} helpText="Universe size" />
            <StatCard variant="full" label="Daily Coverage %" value="98.2%" helpText="502 / 511 bars" trend="up" color="green.400" />
            <StatCard variant="full" label="5m Coverage %" value="92.1%" helpText="470 / 511 bars" trend="down" color="red.400" />
          </div>
        </AppCard>
      </div>
    </div>
  );
};

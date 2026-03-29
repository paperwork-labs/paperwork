"use client";

import type { FormationData } from "@/lib/stores/formation";
import { useFormationStore } from "@/lib/stores/formation";
import { WizardNavigation } from "./wizard-navigation";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Input,
  Label,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@paperwork-labs/ui";

const NAME_SUFFIX_OPTIONS: FormationData["nameSuffix"][] = [
  "LLC",
  "L.L.C.",
  "Limited Liability Company",
];

export function NameStep() {
  const { data, updateData } = useFormationStore();
  const businessName = data.businessName ?? "";
  const nameSuffix = data.nameSuffix ?? "LLC";

  const trimmedName = businessName.trim();
  const previewText =
    trimmedName.length > 0
      ? `${trimmedName} ${nameSuffix}`
      : `Your business name ${nameSuffix}`;

  return (
    <div className="space-y-8 rounded-xl bg-slate-900 p-6 text-white md:p-8">
      <header className="space-y-2">
        <h1 className="text-2xl font-bold tracking-tight text-white md:text-3xl">
          Name your LLC
        </h1>
        <p className="max-w-2xl text-slate-400">
          Enter the legal name you want on file with the state. You can change
          details later if the name is available.
        </p>
      </header>

      <div className="space-y-6">
        <div className="space-y-2">
          <Label htmlFor="business-name" className="text-slate-200">
            Business name
          </Label>
          <Input
            id="business-name"
            value={businessName}
            onChange={(e) => updateData({ businessName: e.target.value })}
            placeholder="e.g. Acme Ventures"
            className="border-slate-600 bg-slate-800/60 text-white placeholder:text-slate-500 focus-visible:ring-teal-400"
            autoComplete="organization"
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="name-suffix" className="text-slate-200">
            Legal suffix
          </Label>
          <Select
            value={nameSuffix}
            onValueChange={(value) =>
              updateData({
                nameSuffix: value as FormationData["nameSuffix"],
              })
            }
          >
            <SelectTrigger
              id="name-suffix"
              className="border-slate-600 bg-slate-800/60 text-white focus:ring-teal-400"
            >
              <SelectValue placeholder="Choose suffix" />
            </SelectTrigger>
            <SelectContent className="border-slate-700 bg-slate-900 text-white">
              {NAME_SUFFIX_OPTIONS.map((option) => (
                <SelectItem
                  key={option}
                  value={option}
                  className="focus:bg-slate-800 focus:text-white"
                >
                  {option}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <Card className="border-slate-700 bg-slate-800/40">
          <CardHeader className="pb-2">
            <CardTitle className="text-base font-medium text-slate-200">
              Preview
            </CardTitle>
            <CardDescription className="text-slate-500">
              How your LLC name will read on the filing
            </CardDescription>
          </CardHeader>
          <CardContent>
            <p className="font-mono text-lg font-medium text-teal-300 md:text-xl">
              {previewText}
            </p>
          </CardContent>
        </Card>
      </div>

      <WizardNavigation />
    </div>
  );
}

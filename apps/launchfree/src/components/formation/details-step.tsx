"use client";

import {
  type FormationStore,
  useFormationStore,
} from "@/lib/stores/formation";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Label,
  RadioGroup,
  RadioGroupItem,
  Textarea,
} from "@paperwork-labs/ui";
import { useId } from "react";
import { WizardNavigation } from "./wizard-navigation";

const inputSurface =
  "border-slate-700 bg-slate-950/50 text-white placeholder:text-slate-500 focus-visible:ring-teal-500/40";

export function DetailsStep() {
  const id = useId();
  const data = useFormationStore((s: FormationStore) => s.data);
  const updateData = useFormationStore((s: FormationStore) => s.updateData);

  const businessPurpose = data.businessPurpose ?? "Any lawful purpose";
  const managementType = data.managementType ?? "member";

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <header className="space-y-2">
        <h1 className="text-2xl font-bold tracking-tight text-white">
          Business details
        </h1>
        <p className="text-sm text-slate-400">
          Describe what your LLC will do and how it will be managed. Most
          startups choose member-managed.
        </p>
      </header>

      <Card className="border-slate-800 bg-slate-900/50 text-white shadow-none">
        <CardHeader>
          <CardTitle className="text-lg text-white">Purpose & management</CardTitle>
          <CardDescription className="text-slate-400">
            These appear on your articles of organization where required by your
            state.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-8">
          <div className="space-y-2">
            <Label
              htmlFor={`${id}-purpose`}
              className="text-slate-200"
            >
              Business purpose
            </Label>
            <Textarea
              id={`${id}-purpose`}
              rows={4}
              value={businessPurpose}
              onChange={(e) =>
                updateData({ businessPurpose: e.target.value })
              }
              placeholder="Any lawful purpose"
              className={inputSurface}
            />
            <p className="text-xs text-slate-500">
              Many states accept a general purpose like &quot;Any lawful
              purpose&quot; unless you need something specific for licensing or
              banking.
            </p>
          </div>

          <div className="space-y-4">
            <Label className="text-slate-200">Management structure</Label>
            <RadioGroup
              value={managementType}
              onValueChange={(v) =>
                updateData({
                  managementType: v as "member" | "manager",
                })
              }
              className="grid gap-4"
            >
              <label
                htmlFor={`${id}-member`}
                className={`flex cursor-pointer gap-3 rounded-lg border p-4 transition-colors ${
                  managementType === "member"
                    ? "border-teal-500/40 bg-teal-950/20"
                    : "border-slate-800 bg-slate-950/30 hover:border-slate-700"
                }`}
              >
                <RadioGroupItem
                  value="member"
                  id={`${id}-member`}
                  className="mt-0.5 border-slate-600 text-teal-400"
                />
                <div className="space-y-1">
                  <span className="font-medium text-white">
                    Member-managed
                  </span>
                  <p className="text-sm text-slate-400">
                    Members (owners) run day-to-day operations and make
                    decisions together. Typical for small LLCs and solo
                    founders.
                  </p>
                </div>
              </label>

              <label
                htmlFor={`${id}-manager`}
                className={`flex cursor-pointer gap-3 rounded-lg border p-4 transition-colors ${
                  managementType === "manager"
                    ? "border-teal-500/40 bg-teal-950/20"
                    : "border-slate-800 bg-slate-950/30 hover:border-slate-700"
                }`}
              >
                <RadioGroupItem
                  value="manager"
                  id={`${id}-manager`}
                  className="mt-0.5 border-slate-600 text-teal-400"
                />
                <div className="space-y-1">
                  <span className="font-medium text-white">
                    Manager-managed
                  </span>
                  <p className="text-sm text-slate-400">
                    One or more appointed managers run the business; members
                    may be passive investors. Common when not all owners work
                    in the business.
                  </p>
                </div>
              </label>
            </RadioGroup>
          </div>
        </CardContent>
      </Card>

      <WizardNavigation />
    </div>
  );
}

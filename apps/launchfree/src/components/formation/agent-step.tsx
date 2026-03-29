"use client";

import {
  type Address,
  type FormationStore,
  type RegisteredAgent,
  useFormationStore,
} from "@/lib/stores/formation";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Input,
  Label,
  RadioGroup,
  RadioGroupItem,
} from "@paperwork-labs/ui";
import { BadgeCheck } from "lucide-react";
import { useId } from "react";
import { WizardNavigation } from "./wizard-navigation";

const emptyAddress = (): Address => ({
  street1: "",
  city: "",
  state: "",
  zip: "",
});

const inputSurface =
  "border-slate-700 bg-slate-950/50 text-white placeholder:text-slate-500 focus-visible:ring-teal-500/40";

export function AgentStep() {
  const id = useId();
  const data = useFormationStore((s: FormationStore) => s.data);
  const updateData = useFormationStore((s: FormationStore) => s.updateData);

  const ra: RegisteredAgent = data.registeredAgent ?? {
    type: "launchfree",
    name: "",
    address: emptyAddress(),
    isCommercial: false,
  };

  const agentType = ra.type;
  const showCustomFields = agentType === "self" || agentType === "other";

  type AgentPatch = Partial<Omit<RegisteredAgent, "address">> & {
    address?: Partial<Address>;
  };

  const applyAgentPatch = (patch: AgentPatch) => {
    updateData({
      registeredAgent: {
        ...ra,
        ...patch,
        address: { ...ra.address, ...(patch.address ?? {}) },
      },
    });
  };

  const onTypeChange = (value: string) => {
    const type = value as RegisteredAgent["type"];
    if (type === "launchfree") {
      updateData({
        registeredAgent: {
          type: "launchfree",
          name: "",
          address: emptyAddress(),
          isCommercial: false,
        },
      });
      return;
    }
    applyAgentPatch({
      type,
      address: {
        ...ra.address,
        state: ra.address.state || data.stateCode || "",
      },
    });
  };

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <header className="space-y-2">
        <h1 className="text-2xl font-bold tracking-tight text-white">
          Registered agent
        </h1>
        <p className="text-sm text-slate-400">
          Your registered agent receives legal and state mail on behalf of the
          LLC. The address must be a physical location in your formation state.
        </p>
      </header>

      <Card className="border-slate-800 bg-slate-900/50 text-white shadow-none">
        <CardHeader>
          <CardTitle className="text-lg text-white">Choose an option</CardTitle>
          <CardDescription className="text-slate-400">
            States require a registered agent with a reliable in-state address.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <RadioGroup
            value={agentType}
            onValueChange={onTypeChange}
            className="grid gap-4"
          >
            <label
              htmlFor={`${id}-launchfree`}
              className={`relative flex cursor-pointer gap-3 rounded-lg border p-4 transition-colors ${
                agentType === "launchfree"
                  ? "border-teal-500/50 bg-teal-950/25 ring-1 ring-teal-500/20"
                  : "border-slate-800 bg-slate-950/30 hover:border-slate-700"
              }`}
            >
              <RadioGroupItem
                value="launchfree"
                id={`${id}-launchfree`}
                className="mt-0.5 border-slate-600 text-teal-400"
              />
              <div className="flex flex-1 flex-col gap-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium text-white">
                    LaunchFree Registered Agent Service
                  </span>
                  <span className="inline-flex items-center gap-1 rounded-full bg-teal-500/15 px-2 py-0.5 text-xs font-medium text-teal-300">
                    <BadgeCheck className="h-3.5 w-3.5" />
                    Recommended
                  </span>
                </div>
                <p className="text-sm font-medium text-teal-200/90">
                  $49/year
                </p>
                <p className="text-sm text-slate-400">
                  We provide a compliant in-state address and forward official
                  notices so you do not have to list your home address on public
                  records.
                </p>
              </div>
            </label>

            <label
              htmlFor={`${id}-self`}
              className={`flex cursor-pointer gap-3 rounded-lg border p-4 transition-colors ${
                agentType === "self"
                  ? "border-teal-500/40 bg-teal-950/20"
                  : "border-slate-800 bg-slate-950/30 hover:border-slate-700"
              }`}
            >
              <RadioGroupItem
                value="self"
                id={`${id}-self`}
                className="mt-0.5 border-slate-600 text-teal-400"
              />
              <div className="space-y-1">
                <span className="font-medium text-white">
                  Act as your own registered agent
                </span>
                <p className="text-sm text-slate-400">
                  You must have a physical street address in your formation state
                  (no P.O. boxes) and be available during business hours to
                  accept service of process.
                </p>
              </div>
            </label>

            <label
              htmlFor={`${id}-other`}
              className={`flex cursor-pointer gap-3 rounded-lg border p-4 transition-colors ${
                agentType === "other"
                  ? "border-teal-500/40 bg-teal-950/20"
                  : "border-slate-800 bg-slate-950/30 hover:border-slate-700"
              }`}
            >
              <RadioGroupItem
                value="other"
                id={`${id}-other`}
                className="mt-0.5 border-slate-600 text-teal-400"
              />
              <div className="space-y-1">
                <span className="font-medium text-white">
                  Another registered agent service
                </span>
                <p className="text-sm text-slate-400">
                  Use a third-party registered agent company you already work
                  with. Enter their legal name and registered office address.
                </p>
              </div>
            </label>
          </RadioGroup>

          {showCustomFields ? (
            <div className="space-y-4 rounded-lg border border-slate-800 bg-slate-950/40 p-4">
              <p className="text-sm font-medium text-slate-200">
                Agent name & address
              </p>
              <div className="space-y-2">
                <Label htmlFor={`${id}-name`} className="text-slate-200">
                  Registered agent name
                </Label>
                <Input
                  id={`${id}-name`}
                  value={ra.name}
                  onChange={(e) => applyAgentPatch({ name: e.target.value })}
                  placeholder="Individual or company name"
                  className={inputSurface}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor={`${id}-street1`} className="text-slate-200">
                  Street address
                </Label>
                <Input
                  id={`${id}-street1`}
                  value={ra.address.street1}
                  onChange={(e) =>
                    applyAgentPatch({ address: { street1: e.target.value } })
                  }
                  placeholder="Street line 1"
                  className={inputSurface}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor={`${id}-street2`} className="text-slate-200">
                  Apt / suite (optional)
                </Label>
                <Input
                  id={`${id}-street2`}
                  value={ra.address.street2 ?? ""}
                  onChange={(e) =>
                    applyAgentPatch({
                      address: { street2: e.target.value || undefined },
                    })
                  }
                  placeholder="Line 2"
                  className={inputSurface}
                />
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2 sm:col-span-2">
                  <Label htmlFor={`${id}-city`} className="text-slate-200">
                    City
                  </Label>
                  <Input
                    id={`${id}-city`}
                    value={ra.address.city}
                    onChange={(e) =>
                      applyAgentPatch({ address: { city: e.target.value } })
                    }
                    placeholder="City"
                    className={inputSurface}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor={`${id}-state`} className="text-slate-200">
                    State
                  </Label>
                  <Input
                    id={`${id}-state`}
                    value={ra.address.state}
                    onChange={(e) =>
                      applyAgentPatch({
                        address: {
                          state: e.target.value.toUpperCase().slice(0, 2),
                        },
                      })
                    }
                    placeholder="CA"
                    maxLength={2}
                    className={inputSurface}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor={`${id}-zip`} className="text-slate-200">
                    ZIP code
                  </Label>
                  <Input
                    id={`${id}-zip`}
                    value={ra.address.zip}
                    onChange={(e) =>
                      applyAgentPatch({ address: { zip: e.target.value } })
                    }
                    placeholder="ZIP"
                    className={inputSurface}
                  />
                </div>
              </div>
            </div>
          ) : null}
        </CardContent>
      </Card>

      <WizardNavigation />
    </div>
  );
}

"use client";

import { useFormationStore, type Address } from "@/lib/stores/formation";
import { WizardNavigation } from "./wizard-navigation";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Checkbox,
  Input,
  Label,
} from "@paperwork-labs/ui";

function emptyAddress(): Address {
  return { street1: "", street2: "", city: "", state: "", zip: "" };
}

function isAddressComplete(a: Address | undefined): boolean {
  return Boolean(
    a?.street1?.trim() &&
      a?.city?.trim() &&
      a?.state?.trim() &&
      a?.zip?.trim()
  );
}

export function AddressStep() {
  const { data, updateData } = useFormationStore();
  const principal = data.principalAddress ?? emptyAddress();
  const sameMailing = data.sameMailingAddress !== false;
  const mailing = data.mailingAddress ?? emptyAddress();

  const patchPrincipal = (patch: Partial<Address>) => {
    updateData({
      principalAddress: { ...principal, ...patch },
    });
  };

  const patchMailing = (patch: Partial<Address>) => {
    updateData({
      mailingAddress: { ...mailing, ...patch },
    });
  };

  const setSameMailing = (checked: boolean) => {
    if (checked) {
      updateData({
        sameMailingAddress: true,
        mailingAddress: undefined,
      });
    } else {
      updateData({
        sameMailingAddress: false,
        mailingAddress: data.mailingAddress ?? emptyAddress(),
      });
    }
  };

  const mailingIncomplete = !sameMailing && !isAddressComplete(mailing);
  const inputClass =
    "border-slate-700 bg-slate-950/80 text-white placeholder:text-slate-500";

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div className="space-y-2">
        <h1 className="text-2xl font-bold tracking-tight text-white">
          Principal address
        </h1>
        <p className="text-sm text-slate-400">
          This is your LLC&apos;s main business location. States use it for
          public records and correspondence.
        </p>
      </div>

      <Card className="border-slate-800 bg-slate-900/50 text-white">
        <CardHeader>
          <CardTitle className="text-white">Business address</CardTitle>
          <CardDescription className="text-slate-400">
            Street and mailing details for your principal place of business.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="principal-street1" className="text-slate-200">
              Street address
            </Label>
            <Input
              id="principal-street1"
              value={principal.street1}
              onChange={(e) => patchPrincipal({ street1: e.target.value })}
              placeholder="123 Main St"
              className={inputClass}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="principal-street2" className="text-slate-200">
              Apt / suite (optional)
            </Label>
            <Input
              id="principal-street2"
              value={principal.street2 ?? ""}
              onChange={(e) => patchPrincipal({ street2: e.target.value })}
              placeholder="Suite 100"
              className={inputClass}
            />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2 sm:col-span-2">
              <Label htmlFor="principal-city" className="text-slate-200">
                City
              </Label>
              <Input
                id="principal-city"
                value={principal.city}
                onChange={(e) => patchPrincipal({ city: e.target.value })}
                placeholder="City"
                className={inputClass}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="principal-state" className="text-slate-200">
                State
              </Label>
              <Input
                id="principal-state"
                value={principal.state}
                onChange={(e) =>
                  patchPrincipal({ state: e.target.value.toUpperCase() })
                }
                placeholder="CA"
                maxLength={2}
                className={inputClass}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="principal-zip" className="text-slate-200">
                ZIP code
              </Label>
              <Input
                id="principal-zip"
                value={principal.zip}
                onChange={(e) => patchPrincipal({ zip: e.target.value })}
                placeholder="94102"
                className={inputClass}
              />
            </div>
          </div>

          <div className="flex items-start gap-3 rounded-lg border border-slate-800 bg-slate-950/40 p-4">
            <Checkbox
              id="same-mailing"
              checked={sameMailing}
              onCheckedChange={(v) => setSameMailing(v === true)}
              className="mt-0.5 border-slate-600 data-[state=checked]:bg-teal-500 data-[state=checked]:border-teal-500"
            />
            <div className="space-y-1">
              <Label
                htmlFor="same-mailing"
                className="cursor-pointer text-sm font-medium text-slate-200"
              >
                Mailing address is the same as principal address
              </Label>
              <p className="text-xs text-slate-500">
                Uncheck if you receive mail at a different location.
              </p>
            </div>
          </div>

          {!sameMailing && (
            <div className="space-y-4 border-t border-slate-800 pt-6">
              <h3 className="text-sm font-semibold text-teal-300">
                Mailing address
              </h3>
              <div className="space-y-2">
                <Label htmlFor="mailing-street1" className="text-slate-200">
                  Street address
                </Label>
                <Input
                  id="mailing-street1"
                  value={mailing.street1}
                  onChange={(e) => patchMailing({ street1: e.target.value })}
                  placeholder="PO Box or street"
                  className={inputClass}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="mailing-street2" className="text-slate-200">
                  Apt / suite (optional)
                </Label>
                <Input
                  id="mailing-street2"
                  value={mailing.street2 ?? ""}
                  onChange={(e) => patchMailing({ street2: e.target.value })}
                  className={inputClass}
                />
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2 sm:col-span-2">
                  <Label htmlFor="mailing-city" className="text-slate-200">
                    City
                  </Label>
                  <Input
                    id="mailing-city"
                    value={mailing.city}
                    onChange={(e) => patchMailing({ city: e.target.value })}
                    className={inputClass}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="mailing-state" className="text-slate-200">
                    State
                  </Label>
                  <Input
                    id="mailing-state"
                    value={mailing.state}
                    onChange={(e) =>
                      patchMailing({ state: e.target.value.toUpperCase() })
                    }
                    maxLength={2}
                    className={inputClass}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="mailing-zip" className="text-slate-200">
                    ZIP code
                  </Label>
                  <Input
                    id="mailing-zip"
                    value={mailing.zip}
                    onChange={(e) => patchMailing({ zip: e.target.value })}
                    className={inputClass}
                  />
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <WizardNavigation disabled={mailingIncomplete} />
    </div>
  );
}

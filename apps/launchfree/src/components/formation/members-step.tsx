"use client";

import { useState } from "react";
import {
  useFormationStore,
  type Address,
  type Member,
} from "@/lib/stores/formation";
import { WizardNavigation } from "./wizard-navigation";
import {
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Checkbox,
  Input,
  Label,
} from "@paperwork-labs/ui";
import { Plus, Trash2, UserCircle } from "lucide-react";

function emptyAddress(): Address {
  return { street1: "", street2: "", city: "", state: "", zip: "" };
}

type MemberDraft = {
  name: string;
  address: Address;
  role: "member" | "manager";
  ownershipPercentage: string;
  isOrganizer: boolean;
};

function emptyDraft(): MemberDraft {
  return {
    name: "",
    address: emptyAddress(),
    role: "member",
    ownershipPercentage: "",
    isOrganizer: false,
  };
}

function draftToMember(draft: MemberDraft): Member {
  const pct = draft.ownershipPercentage.trim();
  let ownershipPercentage: number | undefined;
  if (pct !== "") {
    const n = Number.parseFloat(pct);
    if (!Number.isNaN(n)) ownershipPercentage = n;
  }
  return {
    id: crypto.randomUUID(),
    name: draft.name.trim(),
    address: {
      ...draft.address,
      street2: draft.address.street2?.trim() || undefined,
    },
    role: draft.role,
    ownershipPercentage,
    isOrganizer: draft.isOrganizer,
  };
}

function isDraftValid(draft: MemberDraft): boolean {
  const a = draft.address;
  return Boolean(
    draft.name.trim() &&
      a.street1.trim() &&
      a.city.trim() &&
      a.state.trim() &&
      a.zip.trim()
  );
}

export function MembersStep() {
  const { data, updateData } = useFormationStore();
  const members = data.members ?? [];
  const [showAddForm, setShowAddForm] = useState(false);
  const [draft, setDraft] = useState<MemberDraft>(emptyDraft);

  const hasOrganizer = members.some((m: Member) => m.isOrganizer);
  const membersValid = members.length > 0 && hasOrganizer;

  const inputClass =
    "border-slate-700 bg-slate-950/80 text-white placeholder:text-slate-500";
  const selectClass =
    "flex h-9 w-full rounded-md border border-slate-700 bg-slate-950/80 px-3 py-1 text-sm text-white shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-teal-500";

  const removeMember = (id: string) => {
    updateData({ members: members.filter((m: Member) => m.id !== id) });
  };

  const addMember = () => {
    if (!isDraftValid(draft)) return;
    updateData({ members: [...members, draftToMember(draft)] });
    setDraft(emptyDraft());
    setShowAddForm(false);
  };

  const cancelAdd = () => {
    setDraft(emptyDraft());
    setShowAddForm(false);
  };

  const patchDraftAddress = (patch: Partial<Address>) => {
    setDraft((d) => ({
      ...d,
      address: { ...d.address, ...patch },
    }));
  };

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div className="space-y-2">
        <h1 className="text-2xl font-bold tracking-tight text-white">
          Members & managers
        </h1>
        <p className="text-sm text-slate-400">
          Add everyone who owns or manages the LLC. At least one person must be
          marked as an organizer.
        </p>
      </div>

      <Card className="border-slate-800 bg-slate-900/50 text-white">
        <CardHeader className="flex flex-row items-start justify-between space-y-0">
          <div className="space-y-1">
            <CardTitle className="text-white">People</CardTitle>
            <CardDescription className="text-slate-400">
              {members.length === 0
                ? "No members added yet."
                : `${members.length} member${members.length === 1 ? "" : "s"} on the filing.`}
            </CardDescription>
          </div>
          {!showAddForm && (
            <Button
              type="button"
              size="sm"
              onClick={() => setShowAddForm(true)}
              className="shrink-0 bg-gradient-to-r from-teal-400 to-cyan-500 text-slate-950 hover:from-teal-300 hover:to-cyan-400"
            >
              <Plus className="mr-1.5 h-4 w-4" />
              Add member
            </Button>
          )}
        </CardHeader>
        <CardContent className="space-y-4">
          {members.length > 0 && (
            <ul className="space-y-3">
              {members.map((m: Member) => (
                <li
                  key={m.id}
                  className="flex gap-3 rounded-lg border border-slate-800 bg-slate-950/40 p-4"
                >
                  <UserCircle className="h-10 w-10 shrink-0 text-teal-400/90" />
                  <div className="min-w-0 flex-1 space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium text-white">{m.name}</span>
                      <span className="rounded-md bg-slate-800 px-2 py-0.5 text-xs text-slate-300">
                        {m.role === "manager" ? "Manager" : "Member"}
                      </span>
                      {m.isOrganizer && (
                        <span className="rounded-md bg-teal-950/80 px-2 py-0.5 text-xs text-teal-300 ring-1 ring-teal-700/50">
                          Organizer
                        </span>
                      )}
                      {m.ownershipPercentage != null && (
                        <span className="text-xs text-slate-500">
                          {m.ownershipPercentage}% ownership
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-slate-400">
                      {m.address.street1}
                      {m.address.street2
                        ? `, ${m.address.street2}`
                        : ""}
                      <br />
                      {m.address.city}, {m.address.state} {m.address.zip}
                    </p>
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    onClick={() => removeMember(m.id)}
                    className="h-9 w-9 shrink-0 text-slate-400 hover:bg-red-950/40 hover:text-red-400"
                    aria-label={`Remove ${m.name}`}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </li>
              ))}
            </ul>
          )}

          {members.length > 0 && !hasOrganizer && (
            <p className="text-sm text-amber-400/90">
              Mark at least one person as an organizer to continue.
            </p>
          )}

          {showAddForm && (
            <div className="space-y-4 rounded-lg border border-teal-900/40 bg-slate-950/60 p-4">
              <h3 className="text-sm font-semibold text-teal-300">
                New member
              </h3>
              <div className="space-y-2">
                <Label htmlFor="draft-name" className="text-slate-200">
                  Full legal name
                </Label>
                <Input
                  id="draft-name"
                  value={draft.name}
                  onChange={(e) =>
                    setDraft((d) => ({ ...d, name: e.target.value }))
                  }
                  className={inputClass}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="draft-role" className="text-slate-200">
                  Role
                </Label>
                <select
                  id="draft-role"
                  value={draft.role}
                  onChange={(e) =>
                    setDraft((d) => ({
                      ...d,
                      role: e.target.value as "member" | "manager",
                    }))
                  }
                  className={selectClass}
                >
                  <option value="member">Member</option>
                  <option value="manager">Manager</option>
                </select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="draft-ownership" className="text-slate-200">
                  Ownership % (optional)
                </Label>
                <Input
                  id="draft-ownership"
                  type="number"
                  min={0}
                  max={100}
                  step={0.01}
                  value={draft.ownershipPercentage}
                  onChange={(e) =>
                    setDraft((d) => ({
                      ...d,
                      ownershipPercentage: e.target.value,
                    }))
                  }
                  placeholder="e.g. 50"
                  className={inputClass}
                />
              </div>
              <div className="flex items-start gap-3 rounded-lg border border-slate-800 bg-slate-900/30 p-3">
                <Checkbox
                  id="draft-organizer"
                  checked={draft.isOrganizer}
                  onCheckedChange={(v) =>
                    setDraft((d) => ({ ...d, isOrganizer: v === true }))
                  }
                  className="mt-0.5 border-slate-600 data-[state=checked]:bg-teal-500 data-[state=checked]:border-teal-500"
                />
                <Label
                  htmlFor="draft-organizer"
                  className="cursor-pointer text-sm text-slate-200"
                >
                  This person is an organizer of the LLC
                </Label>
              </div>
              <div className="space-y-3 border-t border-slate-800 pt-4">
                <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
                  Address
                </p>
                <div className="space-y-2">
                  <Label htmlFor="draft-street1" className="text-slate-200">
                    Street address
                  </Label>
                  <Input
                    id="draft-street1"
                    value={draft.address.street1}
                    onChange={(e) =>
                      patchDraftAddress({ street1: e.target.value })
                    }
                    className={inputClass}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="draft-street2" className="text-slate-200">
                    Apt / suite (optional)
                  </Label>
                  <Input
                    id="draft-street2"
                    value={draft.address.street2 ?? ""}
                    onChange={(e) =>
                      patchDraftAddress({ street2: e.target.value })
                    }
                    className={inputClass}
                  />
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="space-y-2 sm:col-span-2">
                    <Label htmlFor="draft-city" className="text-slate-200">
                      City
                    </Label>
                    <Input
                      id="draft-city"
                      value={draft.address.city}
                      onChange={(e) =>
                        patchDraftAddress({ city: e.target.value })
                      }
                      className={inputClass}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="draft-state" className="text-slate-200">
                      State
                    </Label>
                    <Input
                      id="draft-state"
                      value={draft.address.state}
                      onChange={(e) =>
                        patchDraftAddress({
                          state: e.target.value.toUpperCase(),
                        })
                      }
                      maxLength={2}
                      className={inputClass}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="draft-zip" className="text-slate-200">
                      ZIP
                    </Label>
                    <Input
                      id="draft-zip"
                      value={draft.address.zip}
                      onChange={(e) =>
                        patchDraftAddress({ zip: e.target.value })
                      }
                      className={inputClass}
                    />
                  </div>
                </div>
              </div>
              <div className="flex flex-wrap gap-2 pt-2">
                <Button
                  type="button"
                  onClick={addMember}
                  disabled={!isDraftValid(draft)}
                  className="bg-gradient-to-r from-teal-400 to-cyan-500 text-slate-950 hover:from-teal-300 hover:to-cyan-400"
                >
                  Save member
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  onClick={cancelAdd}
                  className="text-slate-400 hover:bg-slate-800 hover:text-white"
                >
                  Cancel
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <WizardNavigation disabled={!membersValid} />
    </div>
  );
}

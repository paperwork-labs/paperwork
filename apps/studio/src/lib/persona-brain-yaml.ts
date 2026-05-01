import fs from "fs";
import path from "path";

import yaml from "js-yaml";

import { getRepoRoot } from "@/lib/personas";

export type PersonaBrainYamlFields = {
  slug: string;
  ownerChannel: string | null;
  proactiveCadence: "never" | "daily" | "weekly" | "monthly";
  requiresTools: boolean;
  complianceFlagged: boolean;
  mode: "chat" | "task";
};

function asCadence(v: unknown): PersonaBrainYamlFields["proactiveCadence"] {
  if (v === "daily" || v === "weekly" || v === "monthly" || v === "never") return v;
  return "never";
}

function asMode(v: unknown): PersonaBrainYamlFields["mode"] {
  return v === "task" ? "task" : "chat";
}

export function loadPersonaBrainYamlMap(): Map<string, PersonaBrainYamlFields> {
  const map = new Map<string, PersonaBrainYamlFields>();
  let root: string;
  try {
    root = getRepoRoot();
  } catch {
    return map;
  }
  const dir = path.join(root, "apis", "brain", "app", "personas", "specs");
  if (!fs.existsSync(dir)) return map;
  for (const file of fs.readdirSync(dir)) {
    if (!file.endsWith(".yaml") && !file.endsWith(".yml")) continue;
    const full = path.join(dir, file);
    try {
      const raw = fs.readFileSync(full, "utf8");
      const doc = yaml.load(raw) as Record<string, unknown> | null;
      if (!doc || typeof doc !== "object") continue;
      const nameRaw = typeof doc.name === "string" ? doc.name.trim() : "";
      const slug = (nameRaw || file.replace(/\.ya?ml$/i, "")).toLowerCase();
      if (!slug) continue;
      const owner =
        typeof doc.owner_channel === "string" && doc.owner_channel.trim()
          ? doc.owner_channel.trim()
          : null;
      map.set(slug, {
        slug,
        ownerChannel: owner,
        proactiveCadence: asCadence(doc.proactive_cadence),
        requiresTools: doc.requires_tools === true,
        complianceFlagged: doc.compliance_flagged === true,
        mode: asMode(doc.mode),
      });
    } catch {
      // ignore malformed YAML
    }
  }
  return map;
}

export function personaDomainLabel(
  personaId: string,
  yamlFields: PersonaBrainYamlFields | undefined,
): string {
  if (yamlFields?.ownerChannel) return yamlFields.ownerChannel;
  return personaId.replace(/-/g, " ");
}

export function personaAutonomyLabel(
  yamlFields: PersonaBrainYamlFields | undefined,
): string {
  if (!yamlFields) return "Spec pending";
  if (yamlFields.complianceFlagged) return "Supervised (compliance)";
  if (yamlFields.mode === "task") return "Task (schema-bound)";
  if (yamlFields.requiresTools) {
    if (yamlFields.proactiveCadence !== "never") {
      return `Tool-enabled · proactive (${yamlFields.proactiveCadence})`;
    }
    return "Tool-enabled · reactive";
  }
  if (yamlFields.proactiveCadence !== "never") {
    return `Reactive · proactive (${yamlFields.proactiveCadence})`;
  }
  return "Reactive chat";
}

import type { ComponentType } from 'react';

export type CommandSection = 'navigation' | 'tickers' | 'actions' | 'settings' | 'recent';

export interface ActionContext {
  navigate: (to: string) => void;
  toast: (msg: string, opts?: { type?: 'success' | 'error' }) => void;
  openShortcutHelp?: () => void;
}

export interface CommandAction {
  id: string;
  label: string;
  description?: string;
  icon?: ComponentType<{ className?: string; size?: number }>;
  shortcut?: string[];
  keywords?: string[];
  section: CommandSection;
  run: (ctx: ActionContext) => void | Promise<void>;
}

export const RECENT_ACTIONS_STORAGE_KEY = 'axiomfolio:cmdk:recent';
const MAX_RECENT = 5;

function readRecentIds(): string[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = window.localStorage.getItem(RECENT_ACTIONS_STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((x): x is string => typeof x === 'string').slice(0, MAX_RECENT);
  } catch {
    return [];
  }
}

export function getRecentActionIds(): string[] {
  return readRecentIds();
}

export function pushRecentActionId(id: string): void {
  if (typeof window === 'undefined') return;
  try {
    const prev = readRecentIds().filter((x) => x !== id);
    const next = [id, ...prev].slice(0, MAX_RECENT);
    window.localStorage.setItem(RECENT_ACTIONS_STORAGE_KEY, JSON.stringify(next));
  } catch {
    // ignore quota / privacy mode
  }
}

function normalize(s: string): string {
  return s.toLowerCase().trim();
}

/** Token-wise substring match for palette filtering (fast, predictable). */
export function matchesActionQuery(query: string, action: CommandAction): boolean {
  const q = normalize(query);
  if (!q) return true;
  const hay = normalize(
    [action.label, action.description, ...(action.keywords || []), action.id].filter(Boolean).join(' ')
  );
  const tokens = q.split(/\s+/).filter(Boolean);
  return tokens.every((t) => hay.includes(t));
}

class ActionRegistry {
  private actions = new Map<string, CommandAction>();

  register(action: CommandAction): () => void {
    this.actions.set(action.id, action);
    return () => {
      this.actions.delete(action.id);
    };
  }

  /** Test / story isolation. */
  clear(): void {
    this.actions.clear();
  }

  getById(id: string): CommandAction | undefined {
    return this.actions.get(id);
  }

  getAll(): CommandAction[] {
    const sectionOrder: CommandSection[] = ['navigation', 'settings', 'actions', 'tickers', 'recent'];
    return [...this.actions.values()].sort((a, b) => {
      const ai = sectionOrder.indexOf(a.section);
      const bi = sectionOrder.indexOf(b.section);
      if (ai !== bi) return ai - bi;
      return a.label.localeCompare(b.label);
    });
  }

  search(query: string): CommandAction[] {
    return this.getAll().filter((a) => matchesActionQuery(query, a));
  }
}

export const actionRegistry = new ActionRegistry();

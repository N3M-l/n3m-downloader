import type { PlatformKey } from './platforms';
import type { StorageLike } from './prefs';

export interface HistoryEntry {
  id: string;
  url: string;
  title: string;
  platform: PlatformKey;
  filename: string;
  completedAt: number;
}

const HISTORY_KEY = 'n3m.history.v1';
const MAX_ENTRIES = 10;

function browserStorage(): StorageLike | null {
  if (typeof window === 'undefined') return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export function loadHistory(storage: StorageLike | null = browserStorage()): HistoryEntry[] {
  if (!storage) return [];
  try {
    const raw = storage.getItem(HISTORY_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((item): item is HistoryEntry => Boolean(item && typeof item.url === 'string'))
      .slice(0, MAX_ENTRIES);
  } catch {
    return [];
  }
}

export function pushHistory(
  storage: StorageLike | null,
  entry: HistoryEntry,
): HistoryEntry[] {
  if (!storage) return [entry];
  const existing = loadHistory(storage).filter((item) => item.url !== entry.url);
  const next = [entry, ...existing].slice(0, MAX_ENTRIES);
  try {
    storage.setItem(HISTORY_KEY, JSON.stringify(next));
  } catch {
    /* ignore quota errors */
  }
  return next;
}

export function clearHistory(storage: StorageLike | null = browserStorage()): void {
  if (!storage) return;
  try {
    storage.removeItem(HISTORY_KEY);
  } catch {
    /* ignore */
  }
}

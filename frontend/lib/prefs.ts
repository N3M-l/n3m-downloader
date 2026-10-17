export type Prefs = {
  sound: boolean;
  crt: boolean;
  quality: 'auto' | '1080' | '720' | 'audio';
};

const PREFS_KEY = 'n3m.prefs.v1';

export const DEFAULT_PREFS: Prefs = {
  sound: true,
  crt: true,
  quality: 'auto',
};

export interface StorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

function browserStorage(): StorageLike | null {
  if (typeof window === 'undefined') return null;
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export function loadPrefs(storage: StorageLike | null = browserStorage()): Prefs {
  if (!storage) return DEFAULT_PREFS;
  try {
    const raw = storage.getItem(PREFS_KEY);
    if (!raw) return DEFAULT_PREFS;
    const parsed = JSON.parse(raw) as Partial<Prefs>;
    return {
      sound: typeof parsed.sound === 'boolean' ? parsed.sound : DEFAULT_PREFS.sound,
      crt: typeof parsed.crt === 'boolean' ? parsed.crt : DEFAULT_PREFS.crt,
      quality:
        parsed.quality === '1080' || parsed.quality === '720' || parsed.quality === 'audio'
          ? parsed.quality
          : 'auto',
    };
  } catch {
    return DEFAULT_PREFS;
  }
}

export function savePrefs(prefs: Prefs, storage: StorageLike | null = browserStorage()): void {
  if (!storage) return;
  try {
    storage.setItem(PREFS_KEY, JSON.stringify(prefs));
  } catch {
    /* storage may be unavailable in private mode */
  }
}

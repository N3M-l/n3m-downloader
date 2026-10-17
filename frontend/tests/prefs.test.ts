import { describe, expect, it } from 'vitest';

import { DEFAULT_PREFS, loadPrefs, savePrefs } from '../lib/prefs';
import type { StorageLike } from '../lib/prefs';

class MemoryStorage implements StorageLike {
  private map = new Map<string, string>();

  getItem(key: string): string | null {
    return this.map.get(key) ?? null;
  }

  setItem(key: string, value: string): void {
    this.map.set(key, value);
  }

  removeItem(key: string): void {
    this.map.delete(key);
  }
}

describe('preferences', () => {
  it('returns defaults when empty', () => {
    expect(loadPrefs(new MemoryStorage())).toEqual(DEFAULT_PREFS);
  });

  it('round-trips preferences', () => {
    const storage = new MemoryStorage();
    const prefs = { sound: false, crt: false, quality: '1080' as const };
    savePrefs(prefs, storage);
    expect(loadPrefs(storage)).toEqual(prefs);
  });

  it('falls back for an invalid quality', () => {
    const storage = new MemoryStorage();
    storage.setItem('n3m.prefs.v1', JSON.stringify({ quality: '4k' }));
    expect(loadPrefs(storage).quality).toBe('auto');
  });

  it('survives malformed JSON', () => {
    const storage = new MemoryStorage();
    storage.setItem('n3m.prefs.v1', 'not-json');
    expect(loadPrefs(storage)).toEqual(DEFAULT_PREFS);
  });

  it('works without storage', () => {
    expect(loadPrefs(null)).toEqual(DEFAULT_PREFS);
    expect(() => savePrefs(DEFAULT_PREFS, null)).not.toThrow();
  });
});

import { describe, expect, it } from 'vitest';

import {
  clearHistory,
  loadHistory,
  pushHistory,
  type HistoryEntry,
} from '../lib/history';
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

function entry(id: string, url: string): HistoryEntry {
  return {
    id,
    url,
    title: `title-${id}`,
    platform: 'youtube',
    filename: `${id}.mp4`,
    completedAt: Number(id),
  };
}

describe('history', () => {
  it('starts empty', () => {
    expect(loadHistory(new MemoryStorage())).toEqual([]);
  });

  it('pushes newest first', () => {
    const storage = new MemoryStorage();
    pushHistory(storage, entry('1', 'https://a.com/1'));
    const next = pushHistory(storage, entry('2', 'https://a.com/2'));
    expect(next.map((item) => item.id)).toEqual(['2', '1']);
  });

  it('deduplicates by url', () => {
    const storage = new MemoryStorage();
    pushHistory(storage, entry('1', 'https://a.com/1'));
    pushHistory(storage, entry('2', 'https://a.com/1'));
    const loaded = loadHistory(storage);
    expect(loaded).toHaveLength(1);
    expect(loaded[0].id).toBe('2');
  });

  it('caps the list at ten entries', () => {
    const storage = new MemoryStorage();
    for (let index = 0; index < 15; index += 1) {
      pushHistory(storage, entry(String(index), `https://a.com/${index}`));
    }
    expect(loadHistory(storage)).toHaveLength(10);
  });

  it('clears entries', () => {
    const storage = new MemoryStorage();
    pushHistory(storage, entry('1', 'https://a.com/1'));
    clearHistory(storage);
    expect(loadHistory(storage)).toEqual([]);
  });

  it('ignores malformed storage', () => {
    const storage = new MemoryStorage();
    storage.setItem('n3m.history.v1', '{oops');
    expect(loadHistory(storage)).toEqual([]);
  });
});

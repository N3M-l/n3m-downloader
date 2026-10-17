'use client';

import type { HistoryEntry } from '@/lib/history';
import { formatDate, truncate } from '@/lib/format';
import { PLATFORMS } from '@/lib/platforms';

export function HistoryList({
  entries,
  onPick,
  onClear,
}: {
  entries: HistoryEntry[];
  onPick: (entry: HistoryEntry) => void;
  onClear: () => void;
}) {
  return (
    <section className="history">
      <header className="history__head">
        <h3>سجل التنزيلات</h3>
        {entries.length > 0 ? (
          <button type="button" className="link-btn" onClick={onClear}>
            مسح السجل
          </button>
        ) : null}
      </header>
      {entries.length === 0 ? (
        <p className="history__empty">لا توجد تنزيلات محفوظة بعد.</p>
      ) : (
        <ul className="history__list">
          {entries.map((entry) => {
            const platform = PLATFORMS[entry.platform] ?? PLATFORMS.unknown;
            return (
              <li key={`${entry.id}-${entry.completedAt}`}>
                <button type="button" className="history__item" onClick={() => onPick(entry)}>
                  <span className="history__emoji" aria-hidden>
                    {platform.emoji}
                  </span>
                  <span className="history__text">
                    <span className="history__title" dir="auto">
                      {truncate(entry.title || entry.filename, 52)}
                    </span>
                    <span className="history__meta">
                      {platform.label} · {formatDate(entry.completedAt)}
                    </span>
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

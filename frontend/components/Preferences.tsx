'use client';

import type { HistoryEntry } from '@/lib/history';
import type { Prefs } from '@/lib/prefs';
import { HistoryList } from './HistoryList';

export function Preferences({
  prefs,
  onChange,
  history,
  onClearHistory,
  onPickHistory,
}: {
  prefs: Prefs;
  onChange: (next: Prefs) => void;
  history: HistoryEntry[];
  onClearHistory: () => void;
  onPickHistory: (entry: HistoryEntry) => void;
}) {
  return (
    <details className="panel prefs">
      <summary className="prefs__summary">
        <span aria-hidden>⚙</span> التفضيلات والتأثيرات
        <span className="prefs__chevron" aria-hidden>
          ▾
        </span>
      </summary>

      <div className="prefs__body">
        <div className="prefs__grid">
          <label className="toggle">
            <input
              type="checkbox"
              checked={prefs.sound}
              onChange={(event) => onChange({ ...prefs, sound: event.target.checked })}
            />
            <span className="toggle__box" aria-hidden />
            <span>
              المؤثرات الصوتية
              <small>نغمات 8-بت عند الضغط والنجاح</small>
            </span>
          </label>

          <label className="toggle">
            <input
              type="checkbox"
              checked={prefs.crt}
              onChange={(event) => onChange({ ...prefs, crt: event.target.checked })}
            />
            <span className="toggle__box" aria-hidden />
            <span>
              فلتر شاشة CRT
              <small>خطوط المسح وتوهج الشاشة القديمة</small>
            </span>
          </label>

          <label className="select">
            <span>الجودة</span>
            <select
              value={prefs.quality}
              onChange={(event) =>
                onChange({ ...prefs, quality: event.target.value as Prefs['quality'] })
              }
            >
              <option value="auto">تلقائي — أفضل جودة</option>
              <option value="1080">فيديو 1080p</option>
              <option value="720">فيديو 720p</option>
              <option value="audio">صوت MP3 فقط</option>
            </select>
          </label>
        </div>

        <HistoryList entries={history} onPick={onPickHistory} onClear={onClearHistory} />
      </div>
    </details>
  );
}

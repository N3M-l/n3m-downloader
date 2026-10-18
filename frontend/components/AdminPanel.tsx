'use client';

import { useCallback, useEffect, useState } from 'react';

import {
  adminCleanup,
  adminStatus,
  type AdminStatus,
  type EngineStatus,
} from '@/lib/api';
import {
  formatBytes,
  formatUptime,
  messageFor,
} from '@/lib/format';

const TOKEN_KEY = 'n3m.admin.token';

const ENGINE_LABELS: Record<string, string> = {
  ytdlp: 'yt-dlp',
  gallerydl: 'gallery-dl',
  aria2c: 'aria2c',
  ffmpeg: 'FFmpeg',
};

function EngineCard({ name, engine }: { name: string; engine: EngineStatus }) {
  return (
    <div className={`engine ${engine.available ? 'engine--on' : 'engine--off'}`}>
      <div className="engine__head">
        <strong>{ENGINE_LABELS[name] ?? name}</strong>
        <span className={`pill ${engine.available ? 'pill--ok' : 'pill--bad'}`}>
          {engine.available ? 'متاح' : 'غائب'}
        </span>
      </div>
      <p className="engine__version" dir="ltr">
        {engine.version ?? '—'}
      </p>
      <p className="engine__path" dir="ltr" title={engine.path ?? ''}>
        {engine.path ?? 'غير مثبّت'}
      </p>
    </div>
  );
}

export function AdminPanel() {
  const [token, setToken] = useState('');
  const [draft, setDraft] = useState('');
  const [status, setStatus] = useState<AdminStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<number | null>(null);

  useEffect(() => {
    try {
      const saved = window.sessionStorage.getItem(TOKEN_KEY);
      if (saved) {
        setToken(saved);
        setDraft(saved);
      }
    } catch {
      /* sessionStorage may be disabled */
    }
  }, []);

  const refresh = useCallback(async (value: string) => {
    if (!value) return;
    setBusy(true);
    try {
      const data = await adminStatus(value);
      setStatus(data);
      setError(null);
      setUpdatedAt(Date.now());
    } catch (caught) {
      const apiError = caught as { code?: string; message?: string };
      setError(messageFor(apiError.code, apiError.message));
      setStatus(null);
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    if (!token) return;
    void refresh(token);
    const timer = window.setInterval(() => void refresh(token), 15000);
    return () => window.clearInterval(timer);
  }, [token, refresh]);

  const connect = (event: React.FormEvent) => {
    event.preventDefault();
    const value = draft.trim();
    if (!value) {
      setError('أدخل رمز الإدارة أولًا.');
      return;
    }
    try {
      window.sessionStorage.setItem(TOKEN_KEY, value);
    } catch {
      /* ignore */
    }
    setMessage(null);
    setError(null);
    setToken(value);
    if (value === token) void refresh(value);
  };

  const logout = () => {
    try {
      window.sessionStorage.removeItem(TOKEN_KEY);
    } catch {
      /* ignore */
    }
    setToken('');
    setDraft('');
    setStatus(null);
    setError(null);
    setMessage(null);
  };

  const cleanup = async () => {
    if (!token) return;
    if (!window.confirm('سيتم حذف الملفات المؤقتة القديمة. هل تريد المتابعة؟')) return;
    setBusy(true);
    try {
      const result = await adminCleanup(token);
      setMessage(
        `تم تحرير ${formatBytes(result.freedBytes)} وحذف ${result.removedJobs} مهمة قديمة.`,
      );
      await refresh(token);
    } catch (caught) {
      const apiError = caught as { code?: string; message?: string };
      setError(messageFor(apiError.code, apiError.message));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="admin">
      <header className="admin__head">
        <div>
          <p className="admin__eyebrow">N3M // CONTROL ROOM</p>
          <h1 className="admin__title">لوحة إدارة المحرك</h1>
        </div>
        <span className={`pill ${status?.status === 'online' ? 'pill--ok' : 'pill--bad'}`}>
          {status?.status === 'online' ? '● متصل' : '○ غير متصل'}
        </span>
      </header>

      <form className="panel admin__login" onSubmit={connect}>
        <label htmlFor="admin-token">رمز الإدارة (ADMIN_TOKEN)</label>
        <div className="input-row">
          <input
            id="admin-token"
            className="url-input"
            type="password"
            dir="ltr"
            autoComplete="current-password"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="••••••••••••"
          />
          <button type="submit" className="btn btn--primary" disabled={busy}>
            اتصال
          </button>
          {token ? (
            <button type="button" className="btn btn--ghost" onClick={logout}>
              خروج
            </button>
          ) : null}
        </div>
        <p className="hint">
          يُحفظ الرمز في جلسة المتصفح فقط، ويُرسل إلى خادم المحرك عبر HTTPS.
        </p>
      </form>

      {error ? (
        <p className="form__error" role="alert">
          {error}
        </p>
      ) : null}
      {message ? <p className="admin__notice">{message}</p> : null}

      {status ? (
        <>
          <div className="admin__grid">
            <section className="panel card">
              <h2>الخادم</h2>
              <dl className="kv">
                <div>
                  <dt>الإصدار</dt>
                  <dd dir="ltr">{status.version}</dd>
                </div>
                <div>
                  <dt>المعالج</dt>
                  <dd dir="ltr">{status.arch}</dd>
                </div>
                <div>
                  <dt>النظام</dt>
                  <dd dir="ltr">{status.system}</dd>
                </div>
                <div>
                  <dt>مدة التشغيل</dt>
                  <dd>{formatUptime(status.uptimeSeconds)}</dd>
                </div>
              </dl>
            </section>

            <section className="panel card">
              <h2>التخزين</h2>
              <p className="card__big">
                <span dir="ltr">{formatBytes(status.disk.freeGb * 1024 ** 3)}</span>{' '}
                <span>حرة</span>
              </p>
              <div className="diskbar" role="img" aria-label="استهلاك مساحة التخزين">
                <span
                  style={{
                    width: `${Math.max(
                      0,
                      Math.min(
                        100,
                        ((status.disk.totalGb - status.disk.freeGb) / (status.disk.totalGb || 1)) * 100,
                      ),
                    )}%`,
                  }}
                />
              </div>
              <p className="hint">
                الحد الأدنى الآمن: {status.disk.minFreeGb} GB ·{' '}
                <span className={status.disk.ok ? 'ok' : 'bad'}>
                  {status.disk.ok ? 'داخل الحد الآمن' : 'تحت الحد الآمن'}
                </span>
              </p>
            </section>

            <section className="panel card">
              <h2>المهام</h2>
              <dl className="kv">
                <div>
                  <dt>نشطة الآن</dt>
                  <dd>{status.jobs.active}</dd>
                </div>
                <div>
                  <dt>الحد المتزامن</dt>
                  <dd>{status.jobs.maxConcurrent}</dd>
                </div>
                <div>
                  <dt>محفوظة في الذاكرة</dt>
                  <dd>{status.jobs.retained}</dd>
                </div>
              </dl>
            </section>

            <section className="panel card">
              <h2>حدود الحماية</h2>
              <dl className="kv">
                <div>
                  <dt>فحص / دقيقة</dt>
                  <dd>{status.limits.inspectPerMinute}</dd>
                </div>
                <div>
                  <dt>تنزيل / دقيقة</dt>
                  <dd>{status.limits.downloadsPerMinute}</dd>
                </div>
                <div>
                  <dt>أقصى حجم</dt>
                  <dd dir="ltr">{status.limits.maxFilesizeMb} MB</dd>
                </div>
                <div>
                  <dt>صلاحية التذكرة</dt>
                  <dd>{status.limits.ticketTtlSeconds} ث</dd>
                </div>
              </dl>
            </section>
          </div>

          <section className="panel admin__engines">
            <div className="admin__section-head">
              <h2>محركات التنزيل</h2>
              <span className="hint" dir="ltr">
                {updatedAt ? new Date(updatedAt).toLocaleTimeString('ar') : '—'}
              </span>
            </div>
            <div className="engine-grid">
              {Object.entries(status.engines).map(([name, engine]) => (
                <EngineCard key={name} name={name} engine={engine} />
              ))}
            </div>
          </section>

          <div className="admin__actions">
            <button type="button" className="btn btn--primary" onClick={() => void refresh(token)} disabled={busy}>
              تحديث الحالة
            </button>
            <button type="button" className="btn btn--danger" onClick={() => void cleanup()} disabled={busy}>
              تنظيف الملفات المؤقتة
            </button>
          </div>
        </>
      ) : (
        <p className="admin__waiting">
          {busy ? 'جارٍ الاتصال بالخادم…' : 'أدخل رمز الإدارة لعرض حالة المحرك.'}
        </p>
      )}
    </div>
  );
}

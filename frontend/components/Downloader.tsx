'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import {
  absolutePath,
  cancelJob,
  getJob,
  startDownload,
  type JobStatus,
  type StartResponse,
} from '@/lib/api';
import {
  clearHistory,
  loadHistory,
  pushHistory,
  type HistoryEntry,
} from '@/lib/history';
import { messageFor } from '@/lib/format';
import {
  detectPlatform,
  isProbablyUrl,
  withScheme,
  type DownloadMode,
  type Platform,
} from '@/lib/platforms';
import { DEFAULT_PREFS, loadPrefs, savePrefs, type Prefs } from '@/lib/prefs';
import { playSound } from '@/lib/sounds';
import { PlatformBadge } from './PlatformBadge';
import { Preferences } from './Preferences';
import { ProgressPanel } from './ProgressPanel';

function storage(): Storage | null {
  try {
    return typeof window === 'undefined' ? null : window.localStorage;
  } catch {
    return null;
  }
}

function triggerSave(path: string): void {
  const link = document.createElement('a');
  link.href = absolutePath(path);
  link.rel = 'noopener';
  link.download = '';
  document.body.appendChild(link);
  link.click();
  link.remove();
}

const TERMINAL: JobStatus['status'][] = ['completed', 'failed', 'cancelled', 'expired'];

export function Downloader() {
  const [url, setUrl] = useState('');
  const [prefs, setPrefs] = useState<Prefs>(DEFAULT_PREFS);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const inputRef = useRef<HTMLInputElement>(null);
  const savedRef = useRef(false);
  const prefsRef = useRef(prefs);
  const platformRef = useRef<Platform | null>(null);

  const platform = useMemo(() => detectPlatform(url), [url]);
  const active = job?.status === 'queued' || job?.status === 'running';

  useEffect(() => {
    setPrefs(loadPrefs());
    setHistory(loadHistory());
  }, []);

  useEffect(() => {
    prefsRef.current = prefs;
    savePrefs(prefs);
    document.body.classList.toggle('crt-off', !prefs.crt);
  }, [prefs]);

  useEffect(() => {
    if (platform) platformRef.current = platform;
  }, [platform]);

  const addHistory = useCallback((next: JobStatus) => {
    const store = storage();
    if (!store) return;
    const platformValue = platformRef.current;
    const entry: HistoryEntry = {
      id: next.id,
      url: url.trim(),
      title: next.filename ?? platformValue?.label ?? 'ملف N3M',
      platform: platformValue?.key ?? 'unknown',
      filename: next.filename ?? 'ملف N3M',
      completedAt: Date.now(),
    };
    try {
      setHistory(pushHistory(store, entry));
    } catch {
      /* ignore history failures */
    }
  }, [url]);

  const handleJob = useCallback(
    (next: JobStatus) => {
      setJob(next);
      if (next.status === 'completed') {
        if (next.downloadPath && !savedRef.current) {
          savedRef.current = true;
          triggerSave(next.downloadPath);
          addHistory(next);
          playSound('success', prefsRef.current.sound);
        }
      } else if (next.status === 'failed' || next.status === 'expired') {
        playSound('error', prefsRef.current.sound);
      }
    },
    [addHistory],
  );

  useEffect(() => {
    if (!jobId) return;
    let source: EventSource | null = null;
    let timer: number | null = null;
    let finished = false;

    const stopPolling = () => {
      if (timer !== null) {
        window.clearInterval(timer);
        timer = null;
      }
    };

    const poll = async () => {
      try {
        const next = await getJob(jobId);
        handleJob(next);
        if (TERMINAL.includes(next.status)) {
          finished = true;
          stopPolling();
        }
      } catch (caught) {
        finished = true;
        stopPolling();
        const apiError = caught as { code?: string; message?: string };
        setError(messageFor(apiError.code, apiError.message));
      }
    };

    const fallback = () => {
      if (finished || timer !== null) return;
      void poll();
      timer = window.setInterval(() => void poll(), 900);
    };

    try {
      source = new EventSource(absolutePath(`/api/jobs/${jobId}/events`));
      source.onmessage = (event) => {
        try {
          const next = JSON.parse(event.data) as JobStatus;
          if (TERMINAL.includes(next.status)) {
            finished = true;
            source?.close();
          }
          handleJob(next);
        } catch {
          /* ignore malformed event */
        }
      };
      source.onerror = () => {
        source?.close();
        source = null;
        if (!finished) fallback();
      };
    } catch {
      fallback();
    }

    return () => {
      finished = true;
      source?.close();
      stopPolling();
    };
  }, [jobId, handleJob]);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (busy) return;
    const value = url.trim();
    if (!isProbablyUrl(value)) {
      setError('ألصق رابطًا صحيحًا يبدأ بـ https:// ثم أعد المحاولة.');
      playSound('error', prefs.sound);
      inputRef.current?.focus();
      return;
    }
    setError(null);
    setBusy(true);
    savedRef.current = false;
    try {
      const detected = detectPlatform(value);
      platformRef.current = detected;
      const mode: DownloadMode =
        detected?.kind === 'file'
          ? 'file'
          : detected?.kind === 'images'
            ? 'images'
            : prefs.quality === 'audio'
              ? 'audio'
              : 'video';
      const result: StartResponse = await startDownload({
        url: withScheme(value),
        mode,
        quality:
          prefs.quality === '1080' || prefs.quality === '720'
            ? prefs.quality
            : undefined,
      });
      setJobId(result.jobId);
      setJob({
        id: result.jobId,
        status: result.status,
        progress: 0,
        speedBps: 0,
        etaSeconds: null,
        downloadedBytes: 0,
        totalBytes: null,
        filename: null,
        error: null,
        message: 'في قائمة الانتظار…',
        downloadPath: null,
        createdAt: Date.now(),
      });
      playSound('click', prefs.sound);
    } catch (caught) {
      const apiError = caught as { code?: string; message?: string };
      setError(messageFor(apiError.code, apiError.message));
      playSound('error', prefs.sound);
    } finally {
      setBusy(false);
    }
  };

  const paste = async () => {
    playSound('click', prefs.sound);
    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        setUrl(text.trim());
        setError(null);
        playSound('tick', prefs.sound);
      }
    } catch {
      inputRef.current?.focus();
      setError('لم يسمح المتصفح بقراءة الحافظة. الصق الرابط يدويًا (Ctrl+V).');
    }
  };

  const reset = () => {
    setJob(null);
    setJobId(null);
    setError(null);
    savedRef.current = false;
    inputRef.current?.focus();
    playSound('click', prefs.sound);
  };

  const cancel = async () => {
    if (!jobId) return;
    try {
      await cancelJob(jobId);
      playSound('click', prefs.sound);
    } catch (caught) {
      const apiError = caught as { code?: string; message?: string };
      setError(messageFor(apiError.code, apiError.message));
    }
  };

  const pickHistory = (entry: HistoryEntry) => {
    setUrl(entry.url);
    setJob(null);
    setJobId(null);
    setError(null);
    inputRef.current?.focus();
    playSound('tick', prefs.sound);
  };

  return (
    <>
      <form className="panel form" onSubmit={submit}>
        <label className="sr-only" htmlFor="media-url">
          رابط الوسائط
        </label>
        <div className="input-row">
          <input
            id="media-url"
            ref={inputRef}
            className="url-input"
            type="text"
            inputMode="url"
            dir="ltr"
            spellCheck={false}
            autoComplete="off"
            placeholder="https://www.youtube.com/watch?v=..."
            value={url}
            onChange={(event) => {
              setUrl(event.target.value);
              if (error) setError(null);
            }}
            disabled={active || busy}
            aria-describedby="url-hint"
          />
          <button
            type="button"
            className="btn btn--paste"
            onClick={paste}
            disabled={active || busy}
            aria-label="لصق الرابط من الحافظة"
          >
            لصق
          </button>
        </div>

        <div className="form__meta">
          <PlatformBadge platform={platform} />
          <span className="hint" id="url-hint">
            {prefs.quality === 'audio'
              ? 'سيتم استخراج الصوت بصيغة MP3'
              : 'أفضل جودة متاحة تُختار تلقائيًا'}
          </span>
        </div>

        {error ? (
          <p className="form__error" role="alert">
            {error}
          </p>
        ) : null}

        <button
          type="submit"
          className="btn btn--primary btn--download"
          disabled={busy || active || !url.trim()}
        >
          {busy ? 'جارٍ الإرسال…' : '⚡ تحميل'}
        </button>
      </form>

      {job ? (
        <ProgressPanel
          job={job}
          onSave={() => (job.downloadPath ? triggerSave(job.downloadPath) : undefined)}
          onCancel={() => void cancel()}
          canCancel={active}
        />
      ) : null}

      {job && TERMINAL.includes(job.status) ? (
        <button type="button" className="btn btn--ghost btn--new" onClick={reset}>
          ＋ تنزيل جديد
        </button>
      ) : null}

      <Preferences
        prefs={prefs}
        onChange={(next) => {
          setPrefs(next);
          playSound('tick', next.sound);
        }}
        history={history}
        onClearHistory={() => {
          clearHistory(storage());
          setHistory([]);
          playSound('click', prefs.sound);
        }}
        onPickHistory={pickHistory}
      />
    </>
  );
}

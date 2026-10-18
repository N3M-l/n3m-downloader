'use client';

import type { JobStatus } from '@/lib/api';
import {
  clampPercent,
  formatBytes,
  formatEta,
  formatSpeed,
  progressBlocks,
} from '@/lib/format';

const LABELS: Record<JobStatus['status'], string> = {
  queued: 'في قائمة الانتظار',
  running: 'جارٍ التنزيل',
  completed: 'اكتمل التحميل',
  failed: 'فشل التحميل',
  cancelled: 'أُلغي التحميل',
  expired: 'انتهت الصلاحية',
};

const BLOCKS = 20;

export function ProgressPanel({
  job,
  onSave,
  onCancel,
  canCancel,
}: {
  job: JobStatus;
  onSave: () => void;
  onCancel: () => void;
  canCancel: boolean;
}) {
  const percent = clampPercent(job.progress);
  const filled = progressBlocks(percent, BLOCKS);
  const indeterminate = (job.status === 'queued' || job.status === 'running') && percent < 1;

  return (
    <section className="panel progress" aria-live="polite" aria-busy={job.status === 'running'}>
      <header className="progress__head">
        <span className={`status status--${job.status}`}>{LABELS[job.status]}</span>
        <span className="progress__percent">{percent.toFixed(0)}%</span>
      </header>

      <div
        className={`pixelbar ${indeterminate ? 'pixelbar--indeterminate' : ''} status--${job.status}`}
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(percent)}
        aria-label="نسبة التحميل"
      >
        {Array.from({ length: BLOCKS }, (_, index) => (
          <span key={index} className={index < filled ? 'pixelbar__block is-on' : 'pixelbar__block'} />
        ))}
      </div>

      <dl className="progress__stats">
        <div>
          <dt>السرعة</dt>
          <dd>{formatSpeed(job.speedBps)}</dd>
        </div>
        <div>
          <dt>الوقت المتبقي</dt>
          <dd>{formatEta(job.etaSeconds)}</dd>
        </div>
        <div>
          <dt>الحجم</dt>
          <dd dir="ltr">
            {formatBytes(job.downloadedBytes)}
            {job.totalBytes ? ` / ${formatBytes(job.totalBytes)}` : ''}
          </dd>
        </div>
      </dl>

      <p className="progress__message">{job.message}</p>
      {job.filename ? <p className="progress__file" dir="auto">{job.filename}</p> : null}
      {job.error ? (
        <p className="progress__error" role="alert">
          {job.error}
        </p>
      ) : null}

      <div className="progress__actions">
        {job.status === 'completed' && job.downloadPath ? (
          <button type="button" className="btn btn--primary" onClick={onSave}>
            ⤓ حفظ الملف
          </button>
        ) : null}
        {canCancel ? (
          <button type="button" className="btn btn--ghost" onClick={onCancel}>
            إلغاء
          </button>
        ) : null}
      </div>
    </section>
  );
}

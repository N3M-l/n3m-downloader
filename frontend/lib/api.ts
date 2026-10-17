import { messageFor } from './format';
import type { DownloadMode, PlatformKey } from './platforms';

export interface FormatOption {
  id: string;
  label: string;
  ext: string;
  height: number | null;
  audioBitrate: number | null;
  sizeBytes: number | null;
}

export interface InspectResult {
  url: string;
  platform: PlatformKey;
  platformLabel: string;
  platformEmoji: string;
  kind: string;
  title: string;
  uploader: string | null;
  durationSeconds: number | null;
  thumbnail: string | null;
  filesizeBytes: number | null;
  formats: FormatOption[];
  suggestedMode: DownloadMode;
  expiresAt: number;
}

export type JobState =
  | 'queued'
  | 'running'
  | 'completed'
  | 'failed'
  | 'cancelled'
  | 'expired';

export interface JobStatus {
  id: string;
  status: JobState;
  progress: number;
  speedBps: number;
  etaSeconds: number | null;
  downloadedBytes: number;
  totalBytes: number | null;
  filename: string | null;
  error: string | null;
  message: string;
  downloadPath: string | null;
  createdAt: number;
}

export interface StartResponse {
  jobId: string;
  status: JobState;
  pollUrl: string;
  eventsUrl: string;
  cancelUrl: string;
}

export interface EngineStatus {
  available: boolean;
  version: string | null;
  path: string | null;
}

export interface AdminStatus {
  status: string;
  version: string;
  arch: string;
  system: string;
  hostname: string;
  uptimeSeconds: number;
  engines: Record<'ytdlp' | 'gallerydl' | 'aria2c' | 'ffmpeg', EngineStatus>;
  disk: { freeGb: number; totalGb: number; minFreeGb: number; ok: boolean };
  jobs: { active: number; retained: number; maxConcurrent: number };
  limits: {
    inspectPerMinute: number;
    downloadsPerMinute: number;
    maxFilesizeMb: number;
    ticketTtlSeconds: number;
    retentionMinutes: number;
  };
  workDir: string;
}

const DEFAULT_BASE = 'http://127.0.0.1:8765';

export function engineBase(): string {
  return (process.env.NEXT_PUBLIC_ENGINE_URL || DEFAULT_BASE).replace(/\/+$/, '');
}

export function absolutePath(path: string): string {
  if (/^https?:\/\//i.test(path)) return path;
  return `${engineBase()}${path.startsWith('/') ? '' : '/'}${path}`;
}

export class ApiError extends Error {
  code: string;
  status: number;
  retryAfter: number | undefined;

  constructor(code: string, status: number, message?: string, retryAfter?: number) {
    super(message || messageFor(code));
    this.name = 'ApiError';
    this.code = code;
    this.status = status;
    this.retryAfter = retryAfter;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(absolutePath(path), {
      cache: 'no-store',
      ...init,
      headers: {
        ...(init.body ? { 'Content-Type': 'application/json' } : {}),
        ...(init.headers ?? {}),
      },
    });
  } catch {
    throw new ApiError('network', 0, 'تعذّر الوصول إلى خادم التنزيل. تحقّق من اتصالك.');
  }

  if (!response.ok) {
    let code = 'unknown';
    let message: string | undefined;
    try {
      const body = await response.json();
      code = body?.error?.code ?? code;
      message = body?.error?.message;
    } catch {
      /* non-JSON error body */
    }
    const retryHeader = response.headers.get('retry-after');
    throw new ApiError(
      code,
      response.status,
      message || messageFor(code),
      retryHeader ? Number(retryHeader) : undefined,
    );
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function inspectUrl(url: string): Promise<InspectResult> {
  return request<InspectResult>('/api/inspect', {
    method: 'POST',
    body: JSON.stringify({ url }),
  });
}

export function startDownload(input: {
  url: string;
  mode: DownloadMode;
  quality?: string;
}): Promise<StartResponse> {
  return request<StartResponse>('/api/download', {
    method: 'POST',
    body: JSON.stringify(input),
  });
}

export function getJob(jobId: string): Promise<JobStatus> {
  return request<JobStatus>(`/api/jobs/${encodeURIComponent(jobId)}`);
}

export function cancelJob(jobId: string): Promise<JobStatus> {
  return request<JobStatus>(`/api/jobs/${encodeURIComponent(jobId)}/cancel`, {
    method: 'POST',
  });
}

export function adminStatus(token: string): Promise<AdminStatus> {
  return request<AdminStatus>('/api/admin/status', {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export function adminCleanup(token: string): Promise<{
  freedBytes: number;
  removedJobs: number;
  disk: AdminStatus['disk'];
}> {
  return request('/api/admin/cleanup', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  });
}

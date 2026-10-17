import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  absolutePath,
  adminStatus,
  ApiError,
  getJob,
  startDownload,
} from '../lib/api';

function jsonResponse(body: unknown, status = 200, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...headers },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('api helpers', () => {
  it('builds absolute paths from the engine base', () => {
    expect(absolutePath('/api/jobs/1')).toMatch(/\/api\/jobs\/1$/);
    expect(absolutePath('https://example.com/x')).toBe('https://example.com/x');
  });

  it('encodes job ids', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        id: 'a/b',
        status: 'completed',
        progress: 100,
        speedBps: 0,
        etaSeconds: 0,
        downloadedBytes: 1,
        totalBytes: 1,
        filename: 'x.mp4',
        error: null,
        message: 'ok',
        downloadPath: null,
        createdAt: 1,
      }),
    );
    vi.stubGlobal('fetch', fetchMock);
    await getJob('a/b');
    expect(fetchMock.mock.calls[0][0]).toContain('/api/jobs/a%2Fb');
  });

  it('starts a download with JSON body', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(
        {
          jobId: 'job-1',
          status: 'queued',
          pollUrl: '/api/jobs/job-1',
          eventsUrl: '/api/jobs/job-1/events',
          cancelUrl: '/api/jobs/job-1/cancel',
        },
        202,
      ),
    );
    vi.stubGlobal('fetch', fetchMock);
    const result = await startDownload({
      url: 'https://youtube.com/watch?v=1',
      mode: 'video',
    });
    expect(result.jobId).toBe('job-1');
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain('/api/download');
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body)).toEqual({
      url: 'https://youtube.com/watch?v=1',
      mode: 'video',
    });
  });

  it('turns an error response into ApiError with retry-after', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(
        { error: { code: 'rate_limited', message: 'too many' } },
        429,
        { 'Retry-After': '12' },
      ),
    );
    vi.stubGlobal('fetch', fetchMock);
    await expect(
      startDownload({ url: 'https://youtube.com/watch?v=1', mode: 'video' }),
    ).rejects.toMatchObject({
      code: 'rate_limited',
      status: 429,
      retryAfter: 12,
    });
  });

  it('reports network failures', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockRejectedValue(new Error('connection refused')),
    );
    await expect(
      startDownload({ url: 'https://youtube.com/watch?v=1', mode: 'video' }),
    ).rejects.toBeInstanceOf(ApiError);
  });

  it('sends the admin bearer token', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        status: 'online',
        version: '1.0.0',
        arch: 'x86_64',
        system: 'Test',
        hostname: 'host',
        uptimeSeconds: 1,
        engines: {},
        disk: { freeGb: 1, totalGb: 2, minFreeGb: 1, ok: true },
        jobs: { active: 0, retained: 0, maxConcurrent: 2 },
        limits: {
          inspectPerMinute: 30,
          downloadsPerMinute: 6,
          maxFilesizeMb: 2048,
          ticketTtlSeconds: 300,
          retentionMinutes: 120,
        },
        workDir: '/tmp',
      }),
    );
    vi.stubGlobal('fetch', fetchMock);
    await adminStatus('secret-token');
    const [, init] = fetchMock.mock.calls[0];
    expect(init.headers.Authorization).toBe('Bearer secret-token');
  });
});

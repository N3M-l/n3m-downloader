import { describe, expect, it } from 'vitest';

import {
  clampPercent,
  formatBytes,
  formatDuration,
  formatEta,
  formatSpeed,
  formatUptime,
  messageFor,
  progressBlocks,
  truncate,
} from '../lib/format';

describe('formatting', () => {
  it('formats byte counts', () => {
    expect(formatBytes(0)).toBe('—');
    expect(formatBytes(512)).toBe('512 B');
    expect(formatBytes(1024)).toBe('1.0 KB');
    expect(formatBytes(3.5 * 1024 * 1024)).toBe('3.5 MB');
  });

  it('formats speed', () => {
    expect(formatSpeed(0)).toBe('—');
    expect(formatSpeed(1.5 * 1024 * 1024)).toBe('1.5 MB/s');
  });

  it('formats eta', () => {
    expect(formatEta(null)).toBe('—');
    expect(formatEta(5)).toBe('5 ثانية');
    expect(formatEta(65)).toBe('1:05 دقيقة');
    expect(formatEta(3700)).toBe('1 س 1 د');
  });

  it('formats media duration', () => {
    expect(formatDuration(0)).toBe('—');
    expect(formatDuration(65)).toBe('1:05');
    expect(formatDuration(3723)).toBe('1:02:03');
  });

  it('formats uptime', () => {
    expect(formatUptime(30)).toBe('30 ث');
    expect(formatUptime(120)).toBe('2 د');
    expect(formatUptime(7300)).toBe('2 س 1 د');
    expect(formatUptime(90000)).toBe('1 ي 1 س');
  });

  it('clamps progress and computes blocks', () => {
    expect(clampPercent(-5)).toBe(0);
    expect(clampPercent(150)).toBe(100);
    expect(progressBlocks(50, 20)).toBe(10);
    expect(progressBlocks(Number.NaN)).toBe(0);
  });

  it('maps error codes to Arabic messages', () => {
    expect(messageFor('blocked_host')).toContain('شبكة داخلية');
    expect(messageFor('unknown-code', 'رسالة')).toBe('رسالة');
    expect(messageFor(undefined)).toContain('غير متوقع');
  });

  it('truncates long strings', () => {
    expect(truncate('abcdef', 4)).toBe('abc…');
    expect(truncate('abc', 4)).toBe('abc');
  });
});

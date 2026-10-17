import { describe, expect, it } from 'vitest';

import {
  detectPlatform,
  isProbablyUrl,
  looksLikeDirectFile,
  suggestedMode,
  urlExtension,
  withScheme,
} from '../lib/platforms';

describe('platform detection', () => {
  it.each([
    ['https://www.youtube.com/watch?v=abc', 'youtube'],
    ['https://youtu.be/abc', 'youtube'],
    ['https://m.youtube.com/watch?v=abc', 'youtube'],
    ['https://vm.tiktok.com/abc', 'tiktok'],
    ['https://www.instagram.com/reel/abc', 'instagram'],
    ['https://x.com/user/status/1', 'x'],
    ['https://twitter.com/user/status/1', 'x'],
    ['https://soundcloud.com/artist/track', 'soundcloud'],
    ['https://www.pinterest.com/pin/1', 'pinterest'],
    ['https://pin.it/abc', 'pinterest'],
    ['https://www.reddit.com/r/test/comments/1', 'reddit'],
    ['https://vimeo.com/123456', 'vimeo'],
    ['https://cdn.example.com/file.zip', 'file'],
    ['https://example.com/watch', 'unknown'],
  ])('%s -> %s', (url, expected) => {
    expect(detectPlatform(url)?.key).toBe(expected);
  });

  it('accepts a URL without a scheme', () => {
    expect(detectPlatform('youtube.com/watch?v=1')?.key).toBe('youtube');
  });

  it('returns null for incomplete input', () => {
    expect(detectPlatform('')).toBeNull();
    expect(detectPlatform('hello')).toBeNull();
  });

  it('does not treat a lookalike domain as YouTube', () => {
    expect(detectPlatform('https://notyoutube.com/watch?v=1')?.key).toBe('unknown');
  });
});

describe('direct files', () => {
  it('detects known extensions with query strings', () => {
    expect(urlExtension('https://example.com/a.mp4?token=1')).toBe('mp4');
    expect(looksLikeDirectFile('https://example.com/a.ZIP')).toBe(true);
    expect(looksLikeDirectFile('https://example.com/a.mp3')).toBe(true);
    expect(looksLikeDirectFile('https://example.com/watch')).toBe(false);
  });
});

describe('modes and validation', () => {
  it('suggests the media mode from the platform', () => {
    expect(suggestedMode(detectPlatform('https://soundcloud.com/a/b'))).toBe('audio');
    expect(suggestedMode(detectPlatform('https://pinterest.com/pin/1'))).toBe('images');
    expect(suggestedMode(detectPlatform('https://example.com/a.zip'))).toBe('file');
    expect(suggestedMode(detectPlatform('https://youtube.com/watch?v=1'))).toBe('video');
    expect(suggestedMode(null)).toBe('video');
  });

  it('adds https when missing', () => {
    expect(withScheme('youtube.com/x')).toBe('https://youtube.com/x');
    expect(withScheme('http://a.com')).toBe('http://a.com');
  });

  it('recognizes plausible URLs', () => {
    expect(isProbablyUrl('https://youtube.com/watch?v=1')).toBe(true);
    expect(isProbablyUrl('youtube.com/watch?v=1')).toBe(true);
    expect(isProbablyUrl('not a url')).toBe(false);
    expect(isProbablyUrl('')).toBe(false);
  });
});

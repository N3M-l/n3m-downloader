export type PlatformKey =
  | 'youtube'
  | 'tiktok'
  | 'instagram'
  | 'x'
  | 'soundcloud'
  | 'pinterest'
  | 'reddit'
  | 'vimeo'
  | 'file'
  | 'unknown';

export type MediaKind = 'video' | 'audio' | 'images' | 'file' | 'auto';
export type DownloadMode = 'video' | 'audio' | 'images' | 'file';

export interface Platform {
  key: PlatformKey;
  label: string;
  emoji: string;
  kind: MediaKind;
}

export const PLATFORMS: Record<PlatformKey, Platform> = {
  youtube: { key: 'youtube', label: 'YouTube', emoji: '📺', kind: 'video' },
  tiktok: { key: 'tiktok', label: 'TikTok', emoji: '🎵', kind: 'video' },
  instagram: { key: 'instagram', label: 'Instagram', emoji: '📸', kind: 'video' },
  x: { key: 'x', label: 'X / Twitter', emoji: '🐦', kind: 'video' },
  soundcloud: { key: 'soundcloud', label: 'SoundCloud', emoji: '🎧', kind: 'audio' },
  pinterest: { key: 'pinterest', label: 'Pinterest', emoji: '📌', kind: 'images' },
  reddit: { key: 'reddit', label: 'Reddit', emoji: '👾', kind: 'video' },
  vimeo: { key: 'vimeo', label: 'Vimeo', emoji: '🎬', kind: 'video' },
  file: { key: 'file', label: 'ملف مباشر', emoji: '📁', kind: 'file' },
  unknown: { key: 'unknown', label: 'رابط عام', emoji: '🌐', kind: 'auto' },
};

const HOSTS: Array<[suffix: string, key: PlatformKey]> = [
  ['youtube.com', 'youtube'],
  ['youtu.be', 'youtube'],
  ['youtube-nocookie.com', 'youtube'],
  ['tiktok.com', 'tiktok'],
  ['instagram.com', 'instagram'],
  ['instagr.am', 'instagram'],
  ['x.com', 'x'],
  ['twitter.com', 'x'],
  ['t.co', 'x'],
  ['soundcloud.com', 'soundcloud'],
  ['snd.sc', 'soundcloud'],
  ['pinterest.com', 'pinterest'],
  ['pinterest.co.uk', 'pinterest'],
  ['pin.it', 'pinterest'],
  ['reddit.com', 'reddit'],
  ['redd.it', 'reddit'],
  ['vimeo.com', 'vimeo'],
];

export const DIRECT_EXTENSIONS = new Set([
  'mp4', 'mkv', 'webm', 'mov', 'avi', 'flv',
  'mp3', 'm4a', 'wav', 'flac', 'ogg', 'opus', 'aac',
  'zip', 'rar', '7z', 'tar', 'gz', 'pdf', 'doc', 'docx',
  'apk', 'exe', 'dmg', 'iso', 'img',
  'jpg', 'jpeg', 'png', 'gif', 'webp', 'avif', 'svg', 'bmp',
]);

export function normalizeHost(host: string): string {
  let value = host.trim().toLowerCase().replace(/\.$/, '');
  for (const prefix of ['www.', 'm.', 'mobile.', 'music.', 'open.']) {
    if (value.startsWith(prefix)) {
      value = value.slice(prefix.length);
      break;
    }
  }
  return value;
}

export function hostMatches(host: string, suffix: string): boolean {
  return host === suffix || host.endsWith(`.${suffix}`);
}

export function withScheme(raw: string): string {
  const value = raw.trim();
  if (!value) return '';
  if (/^[a-z][a-z0-9+.-]*:\/\//i.test(value)) return value;
  return `https://${value}`;
}

export function urlExtension(raw: string): string {
  try {
    const path = new URL(withScheme(raw)).pathname;
    const name = path.split('/').filter(Boolean).pop() ?? '';
    const index = name.lastIndexOf('.');
    return index === -1 ? '' : name.slice(index + 1).toLowerCase();
  } catch {
    return '';
  }
}

export function looksLikeDirectFile(raw: string): boolean {
  return DIRECT_EXTENSIONS.has(urlExtension(raw));
}

export function detectPlatform(raw: string): Platform | null {
  const value = raw.trim();
  if (value.length < 4) return null;
  let host = '';
  try {
    host = normalizeHost(new URL(withScheme(value)).hostname);
  } catch {
    return null;
  }
  if (!host || !host.includes('.')) return null;
  for (const [suffix, key] of HOSTS) {
    if (hostMatches(host, suffix)) return PLATFORMS[key];
  }
  if (looksLikeDirectFile(value)) return PLATFORMS.file;
  return PLATFORMS.unknown;
}

export function suggestedMode(platform: Platform | null): DownloadMode {
  if (!platform) return 'video';
  if (platform.kind === 'audio') return 'audio';
  if (platform.kind === 'images') return 'images';
  if (platform.kind === 'file') return 'file';
  return 'video';
}

export function isProbablyUrl(raw: string): boolean {
  const value = raw.trim();
  if (!value || /\s/.test(value)) return false;
  try {
    const parsed = new URL(withScheme(value));
    return parsed.hostname.includes('.') && ['http:', 'https:'].includes(parsed.protocol);
  } catch {
    return false;
  }
}

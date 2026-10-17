import type { Platform } from '@/lib/platforms';

export function PlatformBadge({ platform }: { platform: Platform | null }) {
  if (!platform) {
    return (
      <div className="platform platform--idle" aria-live="polite">
        <span className="platform__dot" aria-hidden />
        <span>بانتظار الرابط…</span>
      </div>
    );
  }
  return (
    <div className={`platform platform--on platform--${platform.key}`} aria-live="polite">
      <span className="platform__dot" aria-hidden />
      <span className="platform__emoji" aria-hidden>
        {platform.emoji}
      </span>
      <span>{platform.label}</span>
    </div>
  );
}

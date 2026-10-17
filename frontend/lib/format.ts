export const ERROR_MESSAGES: Record<string, string> = {
  invalid_url: 'الرابط غير صالح. تأكد من كتابته بشكل صحيح.',
  blocked_host: 'هذا الرابط يشير إلى شبكة داخلية محظورة لحماية الخادم.',
  unauthorized: 'هذا الطلب غير مصرّح به. افتح الأداة من الموقع الرسمي.',
  origin_denied: 'الوصول مسموح من موقع N3M فقط.',
  rate_limited: 'محاولات كثيرة في وقت قصير. انتظر لحظات ثم أعد المحاولة.',
  quota_exceeded: 'مساحة الخادم ممتلئة تقريبًا. جرّب لاحقًا.',
  queue_full: 'الخادم مشغول حاليًا. انتظر قليلًا ثم أعد المحاولة.',
  too_large: 'حجم الملف أكبر من الحد المسموح على الخادم.',
  engine_unavailable: 'محرّك التنزيل غير متاح مؤقتًا. جرّب لاحقًا.',
  inspect_failed: 'تعذّر تحليل هذا الرابط. تأكد أن المحتوى عام وليس محميًا.',
  download_failed: 'تعذّر إكمال التحميل. حاول مرة أخرى.',
  not_found: 'لم يعد هذا الطلب موجودًا. ابدأ من جديد.',
  not_ready: 'الملف غير جاهز بعد. انتظر اكتمال التحميل.',
  expired: 'انتهت صلاحية رابط التحميل. أعد المحاولة.',
  rate_limit: 'محاولات كثيرة في وقت قصير. انتظر لحظات.',
  network: 'تعذّر الوصول إلى خادم التنزيل. تحقّق من اتصالك.',
  timeout: 'استغرق التحميل وقتًا أطول من المسموح.',
  live_unsupported: 'البث المباشر غير مدعوم. انتظر انتهاء البث.',
};

export function messageFor(code: string | undefined, fallback?: string): string {
  if (code && ERROR_MESSAGES[code]) return ERROR_MESSAGES[code];
  return fallback?.trim() || 'حدث خطأ غير متوقع. حاول مرة أخرى.';
}

export function clampPercent(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(100, value));
}

export function formatBytes(bytes: number | null | undefined): string {
  if (!bytes || bytes <= 0) return '—';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let value = bytes;
  let index = 0;
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024;
    index += 1;
  }
  return `${value >= 10 ? value.toFixed(0) : value.toFixed(1)} ${units[index]}`;
}

export function formatSpeed(bytesPerSecond: number | null | undefined): string {
  if (!bytesPerSecond || bytesPerSecond <= 0) return '—';
  return `${formatBytes(bytesPerSecond)}/s`;
}

export function formatEta(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || seconds < 0) return '—';
  if (seconds < 60) return `${Math.ceil(seconds)} ثانية`;
  const minutes = Math.floor(seconds / 60);
  const rest = Math.round(seconds % 60);
  if (minutes < 60) return `${minutes}:${String(rest).padStart(2, '0')} دقيقة`;
  const hours = Math.floor(minutes / 60);
  return `${hours} س ${minutes % 60} د`;
}

export function formatDuration(seconds: number | null | undefined): string {
  if (!seconds || seconds <= 0) return '—';
  const total = Math.round(seconds);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  return `${m}:${String(s).padStart(2, '0')}`;
}

export function formatUptime(seconds: number): string {
  if (seconds < 60) return `${seconds} ث`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} د`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} س ${minutes % 60} د`;
  return `${Math.floor(hours / 24)} ي ${hours % 24} س`;
}

export function progressBlocks(percent: number, total = 20): number {
  return Math.round((clampPercent(percent) / 100) * total);
}

export function formatDate(timestamp: number): string {
  try {
    return new Intl.DateTimeFormat('ar', {
      dateStyle: 'short',
      timeStyle: 'short',
    }).format(new Date(timestamp));
  } catch {
    return new Date(timestamp).toLocaleString();
  }
}

export function truncate(value: string, max = 64): string {
  if (value.length <= max) return value;
  return `${value.slice(0, max - 1)}…`;
}

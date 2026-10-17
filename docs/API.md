# واجهة N3M Downloader (API)

**الأساس:** `http://127.0.0.1:8765` محليًا، أو `https://n3m-downloader-engine.onrender.com` في الإنتاج.

## المصادقة

| النوع | الطريقة | النطاق |
|---|---|---|
| متصفح | ترويسة `Origin` ضمن `TRUSTED_ORIGINS` | كل `/api/*` ما عدا رابط التحميل |
| إدارة | `Authorization: Bearer <ADMIN_TOKEN>` | `/api/admin/*` |
| ملف | تذكرة موقعة في المسار | `/api/download/{token}` |

أي طلب بلا Origin مسموح، أو بOrigin غير مسموح، يُرفض بـ `401` قبل قراءة الجسم. رمز الإدارة الخاطئ يُرفض بـ `403`.

## الأخطاء

كل خطأ يعود بصيغة موحدة:

```json
{ "error": { "code": "blocked_host", "message": "هذا الرابط يشير إلى شبكة داخلية محظورة لحماية الخادم." } }
```

| الرمز | HTTP | المعنى |
|---|---:|---|
| `invalid_url` | 400 | رابط غير صالح أو مخطط غير HTTP(S) أو منفذ غير مسموح |
| `blocked_host` | 400 | العنوان داخلي/محلي/محجوز |
| `invalid_request` | 400 | جسم الطلب لا يطابق المخطط |
| `unauthorized` | 401 | Origin غير مسموح أو تذكرة غير صالحة |
| `forbidden` | 403 | رمز إدارة خاطئ |
| `too_large` | 413 | الحجم يتجاوز `MAX_FILESIZE_MB` |
| `not_found` | 404 | مهمة غير موجودة/منتهية |
| `not_ready` | 409 | الملف غير مكتمل بعد |
| `expired` | 410 | تذكرة منتهية أو ملف محذوف |
| `rate_limited` | 429 | تجاوز النافذة؛ راجع `Retry-After` |
| `queue_full` | 429 | طابور المهام ممتلئ |
| `quota_exceeded` | 503 | مساحة الخادم تحت الحد الآمن |
| `inspect_failed` | 502 | فشل المحرك في قراءة الرابط |
| `download_failed` | 502 | فشل التنزيل |
| `engine_unavailable` | 502 | حزمة المحرك غير مثبتة |
| `live_unsupported` | 502 | بث مباشر غير مدعوم |

## الصحة

```bash
curl https://HOST/health
# {"status":"ok","version":"1.0.0"}
```

## فحص رابط

```bash
curl -X POST https://HOST/api/inspect \
  -H "Origin: https://n3m.fun" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://youtu.be/VIDEO_ID"}'
```

```json
{
  "url": "https://youtu.be/VIDEO_ID",
  "platform": "youtube",
  "platformLabel": "YouTube",
  "platformEmoji": "📺",
  "kind": "video",
  "title": "…",
  "uploader": "…",
  "durationSeconds": 213.0,
  "thumbnail": "https://…",
  "filesizeBytes": 18234567,
  "formats": [
    { "id": "best", "label": "أفضل جودة متاحة", "ext": "mp4", "height": 1080, "audioBitrate": null, "sizeBytes": 18234567 },
    { "id": "720", "label": "720p", "ext": "mp4", "height": 720, "audioBitrate": null, "sizeBytes": 9123456 },
    { "id": "audio", "label": "صوت MP3", "ext": "mp3", "height": null, "audioBitrate": 192, "sizeBytes": null }
  ],
  "suggestedMode": "video",
  "expiresAt": 1790000000000
}
```

## بدء تنزيل

```bash
curl -X POST https://HOST/api/download \
  -H "Origin: https://n3m.fun" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://youtu.be/VIDEO_ID","mode":"video","quality":"1080"}'
```

| الحقل | القيم | ملاحظات |
|---|---|---|
| `url` | نص | يُعاد التحقق منه |
| `mode` | `video` \| `audio` \| `images` \| `file` | `images` يستخدم gallery-dl وZIP |
| `quality` | `1080` \| `720` \| غائب | يُمرّر إلى yt-dlp |
| `formatId` | نص اختياري | محفوظ للتوسعة |

الاستجابة `202`:

```json
{
  "jobId": "4c25e529bb597e3a",
  "status": "queued",
  "pollUrl": "/api/jobs/4c25e529bb597e3a",
  "eventsUrl": "/api/jobs/4c25e529bb597e3a/events",
  "cancelUrl": "/api/jobs/4c25e529bb597e3a/cancel"
}
```

## حالة المهمة

```bash
curl -H "Origin: https://n3m.fun" https://HOST/api/jobs/4c25e529bb597e3a
```

```json
{
  "id": "4c25e529bb597e3a",
  "status": "completed",
  "progress": 100.0,
  "speedBps": 0,
  "etaSeconds": 0,
  "downloadedBytes": 15770,
  "totalBytes": 15770,
  "filename": "python-logo.png",
  "error": null,
  "message": "اكتمل التحميل — جارٍ الحفظ.",
  "downloadPath": "/api/download/eyJqIjoi…",
  "createdAt": 1790000000000
}
```

`status`: `queued` → `running` → `completed` \| `failed` \| `cancelled`.

عند الاكتمال يُصدر `downloadPath` تذكرة جديدة صالحة `TICKET_TTL_SECONDS` (5 دقائق افتراضيًا). أعد طلب الحالة للحصول على تذكرة جديدة.

## بث التقدم (SSE)

```bash
curl -N -H "Origin: https://n3m.fun" \
  https://HOST/api/jobs/4c25e529bb597e3a/events
```

```text
data: {"id":"…","status":"running","progress":42.5,"speedBps":3145728,…}

data: {"id":"…","status":"completed","progress":100,"downloadPath":"/api/download/…"}

event: end
data: {}
```

الواجهة تستخدم SSE افتراضيًا، وتتحول تلقائيًا إلى Polling كل 900ms إذا فشل الاتصال.

## حفظ الملف

```bash
curl -L -o output.mp4 "https://HOST/api/download/TOKEN"
```

- لا يتطلب Origin (تنزيل مباشر).
- يعيد `Content-Disposition: attachment` مع اسم الملف الأصلي.
- يتحقق أن المسار داخل مجلد المهام، وأن المهمة مكتملة.

## الإلغاء

```bash
curl -X POST -H "Origin: https://n3m.fun" \
  https://HOST/api/jobs/4c25e529bb597e3a/cancel
```

يُنهي العملية الفرعية ويعيد المهمة `cancelled`.

## الإدارة

```bash
curl -H "Authorization: Bearer $ADMIN_TOKEN" https://HOST/api/admin/status
curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" https://HOST/api/admin/cleanup
```

`status` يعيد: `version`, `arch`, `system`, `hostname`, `uptimeSeconds`,
`engines.{ytdlp,gallerydl,aria2c,ffmpeg}`, `disk`, `jobs`, `limits`, `workDir`.

`cleanup` يعيد `freedBytes`, `removedJobs`, و`disk` بعد التنظيف.

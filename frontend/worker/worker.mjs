/**
 * Serves the static Next.js export at https://n3m.fun/downloader/.
 * The Worker strips the /downloader prefix and delegates to the assets binding.
 */
const PREFIX = '/downloader';
const ENGINE = 'https://n3m-downloader-engine.onrender.com';

const SECURITY_HEADERS = {
  'X-Content-Type-Options': 'nosniff',
  'X-Frame-Options': 'DENY',
  'Referrer-Policy': 'no-referrer',
  'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
  'Content-Security-Policy': [
    "default-src 'self'",
    "img-src 'self' data: https:",
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    "font-src 'self' https://fonts.gstatic.com data:",
    "script-src 'self' 'unsafe-inline'",
    `connect-src 'self' ${ENGINE}`,
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
  ].join('; '),
};

export default {
  async fetch(request, env) {    const url = new URL(request.url);

    if (url.pathname === PREFIX) {
      url.pathname = `${PREFIX}/`;
      return Response.redirect(url.toString(), 308);
    }

    let path = url.pathname.startsWith(PREFIX)
      ? url.pathname.slice(PREFIX.length)
      : url.pathname;

    if (!path || path === '/') {
      path = '/index.html';
    } else if (path.endsWith('/')) {
      path += 'index.html';
    } else if (!/\.[^/]+$/.test(path)) {
      path += '/index.html';
    }

    const assetUrl = new URL(request.url);
    assetUrl.pathname = path;
    const response = await env.ASSETS.fetch(new Request(assetUrl.toString(), request));

    const headers = new Headers(response.headers);
    for (const [key, value] of Object.entries(SECURITY_HEADERS)) {
      headers.set(key, value);
    }
    headers.set('Cache-Control', path.startsWith('/_next/') ? 'public, max-age=31536000, immutable' : 'no-cache');

    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers,
    });
  },

  /**
   * Keeps the free Render instance awake while the site is published.
   * Runs on the Cron Trigger declared in wrangler.jsonc.
   */
  async scheduled(_controller, _env, ctx) {
    ctx.waitUntil(
      fetch(`${ENGINE}/health`, { cf: { cacheTtl: 0 } }).catch(() => undefined),
    );
  },
};

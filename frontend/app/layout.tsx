import type { Metadata, Viewport } from 'next';
import './globals.css';

const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';

export const metadata: Metadata = {
  title: 'N3M Downloader — تحميل وسائط بضغطة واحدة',
  description:
    'أداة تحميل وسائط بهوية 8-بت: ألصق الرابط، اكتشف المنصة تلقائيًا، وحمّل أفضل جودة مباشرة إلى جهازك.',
  applicationName: 'N3M Downloader',
  icons: { icon: `${basePath}/favicon.svg` },
  robots: { index: true, follow: true },
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  themeColor: '#070b12',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ar" dir="rtl">
      <body>
        <div className="crt-overlay" aria-hidden="true" />
        <div className="shell">{children}</div>
      </body>
    </html>
  );
}

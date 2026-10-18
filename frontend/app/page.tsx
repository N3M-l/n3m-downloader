import { Downloader } from '@/components/Downloader';

const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';

export default function HomePage() {
  return (
    <main className="page">
      <header className="hero">
        <p className="hero__badge" dir="ltr">
          [ 8-BIT MEDIA TOOL ]
        </p>
        <h1 className="hero__title" dir="ltr">
          <span>N3M</span> DOWNLOADER
        </h1>
        <p className="hero__sub">
          ألصق الرابط. اكتشف المنصة تلقائيًا. حمّل أفضل جودة مباشرة إلى جهازك.
        </p>
      </header>

      <Downloader />

      <footer className="foot">
        <span dir="ltr">N3M Downloader · v1.0</span>
        <a href={`${basePath}/admin/`}>لوحة الإدارة ←</a>
      </footer>
    </main>
  );
}

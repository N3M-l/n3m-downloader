import type { Metadata } from 'next';

import { AdminPanel } from '@/components/AdminPanel';

const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';

export const metadata: Metadata = {
  title: 'لوحة إدارة N3M Downloader',
  robots: { index: false, follow: false },
};

export default function AdminPage() {
  return (
    <main className="page page--admin">
      <a className="back" href={`${basePath}/`}>
        → رجوع إلى الأداة
      </a>
      <AdminPanel />
    </main>
  );
}

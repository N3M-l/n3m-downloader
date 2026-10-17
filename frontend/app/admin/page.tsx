import type { Metadata } from 'next';

import { AdminPanel } from '@/components/AdminPanel';

export const metadata: Metadata = {
  title: 'لوحة إدارة N3M Downloader',
  robots: { index: false, follow: false },
};

export default function AdminPage() {
  return (
    <main className="page page--admin">
      <a className="back" href="/">
        → رجوع إلى الأداة
      </a>
      <AdminPanel />
    </main>
  );
}

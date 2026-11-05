import { PurchaseCheckSessionProvider } from '@/features/eligibility/session/PurchaseCheckSession';
import { QueryProvider } from '@/components/providers/QueryProvider';
import type { Metadata } from 'next';
import './globals.css';
import { SiteHeader } from '@/components/layout/SiteHeader';
import { SiteFooter } from '@/components/layout/SiteFooter';

export const metadata: Metadata = {
  title: 'BenefitScout',
  description:
    'Check your purchase details for published manufacturer promotions with BenefitScout.',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en-GB">
      <body className="m-0 flex min-h-svh flex-col bg-page font-sans leading-[1.6] text-ink">
        <a
          className="absolute top-3 left-4 z-10 -translate-y-[200%] bg-surface p-3 text-ink focus:translate-y-0"
          href="#main-content"
        >
          Skip to main content
        </a>
        <SiteHeader />
        <QueryProvider>
          <PurchaseCheckSessionProvider>{children}</PurchaseCheckSessionProvider>
        </QueryProvider>
        <SiteFooter />
      </body>
    </html>
  );
}

import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'BenefitScout',
  description:
    'The BenefitScout web application foundation for future post-purchase benefits checking.',
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en-GB">
      <body>{children}</body>
    </html>
  );
}

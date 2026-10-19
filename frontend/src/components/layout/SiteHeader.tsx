import Link from 'next/link';
import { Container } from '../ui/Container';
import { SiteNavigation, type NavigationItem } from './SiteNavigation';
export function SiteHeader({ navigation = [] }: { navigation?: readonly NavigationItem[] }) {
  return (
    <header className="border-b border-border bg-page">
      <Container className="flex flex-wrap items-center justify-between gap-4 py-6">
        <Link
          className="inline-flex min-h-11 items-center text-card font-[750] tracking-[-0.035em] text-ink no-underline wrap-anywhere"
          href="/"
        >
          BenefitScout
          <span className="text-brand" aria-hidden="true">
            .
          </span>
        </Link>
        {navigation.length > 0 && <SiteNavigation items={navigation} />}
      </Container>
    </header>
  );
}

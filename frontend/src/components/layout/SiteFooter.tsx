import Link from 'next/link';
import { Container } from '../ui/Container';
import type { NavigationItem } from './SiteNavigation';

export function SiteFooter({ links = [] }: { links?: readonly NavigationItem[] }) {
  return (
    <footer className="border-t border-border py-8 text-small text-ink-muted">
      <Container className="grid gap-2">
        <p className="mb-2 font-bold text-ink">BenefitScout</p>
        <p>A UK post-purchase benefits service in development.</p>
        <p>
          Promotion eligibility and claims are determined by the manufacturer; always check the
          official terms.
        </p>
        {links.length > 0 && (
          <nav aria-label="Footer">
            <ul className="m-0 flex list-none flex-wrap gap-4 p-0">
              {links.map(({ href, label }) => (
                <li key={href}>
                  <Link href={href} className="inline-block py-3 text-inherit">
                    {label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
        )}
        <p>© {new Date().getFullYear()} BenefitScout</p>
      </Container>
    </footer>
  );
}

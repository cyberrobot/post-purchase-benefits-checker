import Link from 'next/link';
import { Container } from '../ui/Container';
import type { NavigationItem } from './SiteNavigation';

export function SiteFooter({ links = [] }: { links?: readonly NavigationItem[] }) {
  return (
    <footer className="site-footer">
      <Container>
        <p className="footer-brand">BenefitScout</p>
        <p>A UK post-purchase benefits service in development.</p>
        <p>
          Promotion eligibility and claims are determined by the manufacturer; always check the
          official terms.
        </p>
        {links.length > 0 && (
          <nav aria-label="Footer">
            <ul>
              {links.map(({ href, label }) => (
                <li key={href}>
                  <Link href={href}>{label}</Link>
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

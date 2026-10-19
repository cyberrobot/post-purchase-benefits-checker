import Link from 'next/link';
import { Container } from '../ui/Container';
import { SiteNavigation, type NavigationItem } from './SiteNavigation';
export function SiteHeader({ navigation = [] }: { navigation?: readonly NavigationItem[] }) {
  return (
    <header className="site-header">
      <Container className="header-content">
        <Link className="wordmark" href="/">
          BenefitScout
          <span className="brand-dot" aria-hidden="true">
            .
          </span>
        </Link>
        {navigation.length > 0 && <SiteNavigation items={navigation} />}
      </Container>
    </header>
  );
}

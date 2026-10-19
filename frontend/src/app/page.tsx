import { Badge } from '@/components/ui/Badge';
import { Card } from '@/components/ui/Card';
import { Container } from '@/components/ui/Container';
export default function Home() {
  return (
    <main id="main-content" tabIndex={-1} className="placeholder-main">
      <Container width="narrow">
        <Card className="placeholder-card">
          <Badge variant="accent">Application in development</Badge>
          <h1 className="type-display">BenefitScout</h1>
          <p className="body-copy">
            We are establishing the BenefitScout web application. Purchase checking is not available
            yet.
          </p>
        </Card>
      </Container>
    </main>
  );
}

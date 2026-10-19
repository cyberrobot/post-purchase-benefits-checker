import { Badge } from '@/components/ui/Badge';
import { Card } from '@/components/ui/Card';
import { Container } from '@/components/ui/Container';
export default function Home() {
  return (
    <main id="main-content" tabIndex={-1} className="grid items-center py-16">
      <Container width="narrow">
        <Card className="p-8 md:p-12">
          <Badge variant="accent">Application in development</Badge>
          <h1 className="my-6 text-display leading-[1.15] font-bold tracking-tight">
            BenefitScout
          </h1>
          <p className="max-w-[70ch] text-body text-ink-muted">
            We are establishing the BenefitScout web application. Purchase checking is not available
            yet.
          </p>
        </Card>
      </Container>
    </main>
  );
}

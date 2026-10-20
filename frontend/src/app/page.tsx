import { Card } from '@/components/ui/Card';
import { Container } from '@/components/ui/Container';
import { PurchaseInputForm } from '@/features/eligibility/components/PurchaseInputForm';
export default function Home() {
  return (
    <main
      id="main-content"
      tabIndex={-1}
      className="bg-linear-to-b from-brand/5 to-page py-10 md:py-14"
    >
      <Container width="narrow">
        <div className="mb-8 text-center">
          <h1 className="text-display leading-[1.15] font-bold tracking-tight">
            Find benefits from a <span className="text-brand">purchase</span>
          </h1>
          <p className="mt-4 text-body text-ink-muted">
            Enter the manufacturer, exact model, retailer and purchase date to check for published
            promotions.
          </p>
        </div>
        <Card className="p-6 md:p-8">
          <PurchaseInputForm />
        </Card>
      </Container>
    </main>
  );
}

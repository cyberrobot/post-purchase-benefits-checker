import { Card } from '@/components/ui/Card';
import { Container } from '@/components/ui/Container';
import { PurchaseInputForm } from '@/features/eligibility/components/PurchaseInputForm';
import { BenefitGuide } from '@/features/benefits/BenefitGuide';
export default function Home() {
  return (
    <main
      id="main-content"
      tabIndex={-1}
      className="bg-linear-to-b from-brand/5 to-page py-10 md:py-20"
    >
      <Container>
        <div className="mb-8 text-center">
          <h1 className="text-display leading-[1.15] font-bold tracking-tight">
            Find <span className="text-brand">benefits</span> from a purchase
          </h1>
        </div>
      </Container>
      <Container width="narrow">
        <Card className="p-6 md:p-8">
          <PurchaseInputForm />
        </Card>
      </Container>
      <Container>
        <ol className="mt-10 grid list-decimal gap-6 border-t border-border pt-8 pl-6 text-ink-muted md:grid-cols-3 md:gap-10">
          <li>
            <strong className="block text-ink">Enter purchase details</strong>
            Provide the manufacturer, model, retailer and purchase date.
          </li>
          <li>
            <strong className="block text-ink">Review matching published promotions</strong>
            Check any matching promotions and their recorded conditions.
          </li>
          <li>
            <strong className="block text-ink">Follow official claim instructions</strong>
            If you decide to claim, follow the promotion&apos;s official instructions.
          </li>
        </ol>
      </Container>
      <BenefitGuide />
    </main>
  );
}

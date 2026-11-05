import { Container } from '@/components/ui/Container';
import { ResultsOverview } from '@/features/eligibility/results/ResultsOverview';
export default function ResultsPage() {
  return (
    <main
      id="main-content"
      tabIndex={-1}
      className="bg-linear-to-b from-brand/5 to-page py-10 md:py-14"
    >
      <Container>
        <h1 className="mb-8 text-display leading-tight font-bold">Your eligibility results</h1>
        <ResultsOverview />
      </Container>
    </main>
  );
}

import { Container } from '@/components/ui/Container';
import { ButtonLink } from '@/components/ui/ButtonLink';

export default function PromotionNotFound() {
  return (
    <main id="main-content" tabIndex={-1} className="py-14">
      <Container width="narrow" className="space-y-5">
        <h1 className="text-display font-bold">Promotion not found</h1>
        <p>This promotion page is unavailable. You can still check a purchase.</p>
        <ButtonLink href="/check">Check my purchase</ButtonLink>
      </Container>
    </main>
  );
}

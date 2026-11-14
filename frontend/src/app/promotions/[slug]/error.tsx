'use client';

import { useRouter } from 'next/navigation';
import { startTransition } from 'react';
import { Container } from '@/components/ui/Container';
import { Button } from '@/components/ui/Button';
import { ButtonLink } from '@/components/ui/ButtonLink';

export default function PromotionError({ reset }: { reset: () => void }) {
  const router = useRouter();
  return (
    <main id="main-content" tabIndex={-1} className="py-14">
      <Container width="narrow" className="space-y-5">
        <h1 className="text-display font-bold">Promotion details unavailable</h1>
        <p>We could not load the published terms. Try again in a moment.</p>
        <div className="flex flex-wrap gap-3">
          <Button
            type="button"
            onClick={() =>
              startTransition(() => {
                router.refresh();
                reset();
              })
            }
          >
            Try again
          </Button>
          <ButtonLink href="/check" variant="secondary">
            Check my purchase
          </ButtonLink>
        </div>
      </Container>
    </main>
  );
}

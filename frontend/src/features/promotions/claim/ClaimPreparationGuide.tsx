import Link from 'next/link';
import { Card } from '@/components/ui/Card';
import { Container } from '@/components/ui/Container';
import type { PromotionDetails } from '@/lib/api/promotion-details.contract';
import { ClaimPeriod, OfficialLink, Timestamp } from '../recordedTerms';
import { ClaimChecklist } from './ClaimChecklist';
import { claimGuidePath } from './claimGuidePath';

type Variant = PromotionDetails['variants'][number];

function variantLabel(variant: Variant) {
  return variant.name ? `${variant.name} (variant code: ${variant.code})` : variant.code;
}

function variantChoiceLabels(variants: Variant[]) {
  const labels = variants.map((variant) => {
    const product = variant.products[0];
    return [variantLabel(variant), variant.retailer?.name, product.model_number || product.name]
      .filter(Boolean)
      .join(' · ');
  });
  const counts = new Map<string, number>();
  for (const label of labels) counts.set(label, (counts.get(label) ?? 0) + 1);

  return labels.map((label, index) =>
    (counts.get(label) ?? 0) > 1
      ? `${label} · Variant ID ${variants[index].promotion_variant_id}`
      : label,
  );
}

export function ClaimPreparationGuide({
  promotion,
  selected,
}: {
  promotion: PromotionDetails;
  selected: Variant | undefined;
}) {
  const detailsPath = '/promotions/' + promotion.public_slug;
  const selectedId = selected?.promotion_variant_id;
  const choiceLabels = variantChoiceLabels(promotion.variants);
  return (
    <main
      id="main-content"
      tabIndex={-1}
      className="bg-linear-to-b from-brand/5 to-page py-10 md:py-14"
    >
      <Container className="space-y-6 wrap-anywhere">
        <header className="space-y-3">
          <Link
            href={selectedId ? detailsPath + '#variant-' + selectedId : detailsPath}
            prefetch={false}
            className="font-semibold text-brand underline"
          >
            Back to promotion details
          </Link>
          <h1 className="text-display leading-tight font-bold">Prepare your claim</h1>
          <p className="text-card font-semibold">{promotion.name}</p>
          <p className="text-ink-muted">
            {promotion.manufacturer.name} ·{' '}
            {promotion.status === 'active' ? 'Recorded as active' : 'Recorded as expired'}
          </p>
          <p>
            Use this checklist to prepare the requirements recorded for this promotion. The official
            provider confirms eligibility and handles your claim.
          </p>
        </header>
        {promotion.variants.length > 1 && (
          <Card className="space-y-3">
            <nav aria-label="Promotion variants" className="space-y-3">
              <h2 className="text-card font-bold">Promotion variants</h2>
              <ul className="flex flex-wrap gap-x-6 gap-y-2">
                {promotion.variants.map((variant, index) => {
                  const current = variant.promotion_variant_id === selectedId;
                  return (
                    <li key={variant.promotion_variant_id} className="min-w-0">
                      <Link
                        aria-current={current ? 'page' : undefined}
                        href={claimGuidePath(promotion.public_slug, variant.promotion_variant_id)}
                        prefetch={false}
                        className="inline-block py-2 font-semibold text-brand underline"
                      >
                        {choiceLabels[index]}
                        {current && ' — selected'}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </nav>
            {!selected && <p>Choose a promotion variant to see its requirements.</p>}
          </Card>
        )}
        <div
          className={
            selected ? 'grid min-w-0 gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]' : undefined
          }
        >
          {selected && (
            <Card className="min-w-0 space-y-4">
              <h2 className="text-card font-bold">Evidence and actions</h2>
              <div className="space-y-2">
                <p className="font-semibold">{variantLabel(selected)}</p>
                <p>
                  {selected.retailer
                    ? `Qualifying retailer: ${selected.retailer.name}`
                    : 'No retailer restriction recorded.'}
                </p>
                <ul aria-label="Recorded products and models" className="list-disc pl-6">
                  {selected.products.map((product) => (
                    <li key={product.id}>
                      {product.name}
                      {product.model_number && <> · Model {product.model_number}</>}
                    </li>
                  ))}
                </ul>
              </div>
              <ClaimChecklist key={selectedId} requirements={selected.requirements} />
            </Card>
          )}
          <Card className="min-w-0 space-y-4 self-start">
            <h2 className="text-card font-bold">Official next steps</h2>
            <OfficialLink href={promotion.provenance.claim_url}>
              Open official claim site
            </OfficialLink>
            <p>The official provider controls eligibility, submission, deadlines and acceptance.</p>
            <OfficialLink href={promotion.provenance.official_source_url}>
              Read official terms
            </OfficialLink>
            <p>
              Last official source verified{' '}
              <Timestamp value={promotion.provenance.last_verified_at} />. Check the provider’s
              current terms.
            </p>
            <section className="space-y-2">
              <h3 className="text-lg font-bold">Recorded claim timing</h3>
              <ClaimPeriod window={promotion.claim_window} />
            </section>
          </Card>
        </div>
      </Container>
    </main>
  );
}

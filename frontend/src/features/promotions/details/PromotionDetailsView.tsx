import { ButtonLink } from '@/components/ui/ButtonLink';
import { Card } from '@/components/ui/Card';
import { Container } from '@/components/ui/Container';
import { gbp, words } from '@/features/eligibility/results/presentation';
import type { PromotionDetails } from '@/lib/api/promotion-details.contract';
import { ClaimPeriod, DateValue, OfficialLink, Timestamp } from '../recordedTerms';
import { claimGuidePath } from '../claim/claimGuidePath';
import { requirementLabels } from '../claim/requirements';
import { VariantHashFocus } from './VariantHashFocus';

const categories = {
  cashback: 'Cashback',
  extended_warranty: 'Extended warranty',
  free_gift: 'Free gift',
};
const sourceRoles = {
  primary: 'Official promotion source',
  terms: 'Terms',
  claim: 'Claim site',
  supporting: 'Supporting source',
};
type Variant = PromotionDetails['variants'][number];

function Reward({
  benefit,
  products,
}: {
  benefit: Variant['benefits'][number];
  products: Variant['products'];
}) {
  const { reward } = benefit;
  if (!reward)
    return benefit.benefit_type === 'cashback' ? <p>Cashback amount not recorded.</p> : null;
  switch (reward.kind) {
    case 'fixed_amount':
      return <p>{gbp(reward.amount_gbp)} cashback</p>;
    case 'percentage':
      return <p>{reward.percentage}% cashback (subject to qualifying purchase price)</p>;
    case 'product_specific': {
      const amounts = new Map(reward.values.map((item) => [item.product_id, item.amount_gbp]));
      return (
        <ul className="list-disc pl-6">
          {products.map((product) => (
            <li key={product.id}>
              <ProductName product={product} />: {gbp(amounts.get(product.id)!)} cashback
            </li>
          ))}
        </ul>
      );
    }
  }
}

function ProductName({ product }: { product: Variant['products'][number] }) {
  return (
    <>
      {product.name}
      {product.model_number && <> · Model {product.model_number}</>}
    </>
  );
}

function VariantDetails({ variant, slug }: { variant: Variant; slug: string }) {
  const id = 'variant-' + variant.promotion_variant_id;
  return (
    <Card
      id={id}
      tabIndex={-1}
      role="region"
      aria-labelledby={id + '-title'}
      className="min-w-0 scroll-mt-6 space-y-8 wrap-anywhere md:p-10"
    >
      <div>
        <h2 id={id + '-title'} className="text-card font-bold">
          {variant.name || variant.code}
        </h2>
        {variant.name && <p className="text-small text-ink-muted">Variant code: {variant.code}</p>}
      </div>
      <section className="space-y-4">
        <h3 className="text-lg font-bold">Qualifying products and models</h3>
        <ul className="grid gap-3 sm:grid-cols-2">
          {variant.products.map((product) => (
            <li key={product.id} className="rounded-control bg-surface-muted p-4 font-semibold">
              <ProductName product={product} />
            </li>
          ))}
        </ul>
      </section>
      <section className="space-y-3">
        <h3 className="text-lg font-bold">Participating retailers</h3>
        <p>
          {variant.retailer ? (
            <>Qualifying retailer: {variant.retailer.name}</>
          ) : (
            'No retailer restriction recorded.'
          )}
        </p>
      </section>
      <section className="space-y-4">
        <h3 className="text-lg font-bold">Benefits</h3>
        <ul className="flex flex-col gap-3">
          {variant.benefits.map((benefit) => (
            <li key={benefit.benefit_id} className="space-y-1 rounded-control bg-surface-muted p-4">
              <p className="text-small text-ink-muted">{categories[benefit.benefit_type]}</p>
              <h4 className="font-semibold">{benefit.name}</h4>
              <p>{benefit.description ?? 'Description not recorded.'}</p>
              <Reward benefit={benefit} products={variant.products} />
            </li>
          ))}
        </ul>
      </section>
      <section className="space-y-4">
        <h3 className="text-lg font-bold">What you need to claim</h3>
        {variant.requirements.length ? (
          <ul className="space-y-3">
            {variant.requirements.map((item) => (
              <li key={item.requirement_id} className="rounded-control bg-surface-muted p-4">
                <strong>{requirementLabels[item.requirement_type]}</strong>
                {item.description && <p>{item.description}</p>}
              </li>
            ))}
          </ul>
        ) : (
          <p>No claim requirements recorded here; check the official terms.</p>
        )}
        <ButtonLink href={claimGuidePath(slug, variant.promotion_variant_id)} prefetch={false}>
          Prepare claim checklist
        </ButtonLink>
      </section>
    </Card>
  );
}

export function PromotionDetailsView({ promotion }: { promotion: PromotionDetails }) {
  const benefitTypes = new Set(
    promotion.variants.flatMap((variant) =>
      variant.benefits.map((benefit) => benefit.benefit_type),
    ),
  );
  return (
    <main
      id="main-content"
      tabIndex={-1}
      className="bg-linear-to-b from-brand/5 to-page py-10 md:py-14"
    >
      <VariantHashFocus />
      <Container className="space-y-6 wrap-anywhere">
        <Card className="space-y-8 md:p-10">
          <header className="space-y-4">
            <ul className="flex flex-wrap gap-2" aria-label="Benefit categories">
              {Array.from(benefitTypes, (type) => (
                <li
                  key={type}
                  className="rounded-control border border-border px-3 py-1 text-small font-semibold text-brand"
                >
                  {categories[type]}
                </li>
              ))}
            </ul>
            <p className="font-semibold text-ink-muted">
              {promotion.manufacturer.name} ·{' '}
              {promotion.status === 'active' ? 'Recorded as active' : 'Recorded as expired'}
            </p>
            <p className="text-small text-ink-muted">
              Last official source verified{' '}
              <Timestamp value={promotion.provenance.last_verified_at} />.
            </p>
            <h1 className="text-display leading-tight font-bold">{promotion.name}</h1>
          </header>
          <div className="grid gap-6 border-t border-border pt-6 md:grid-cols-2">
            <section>
              <h2 className="text-ink-muted">Purchase window</h2>
              <span className="font-bold">
                <DateValue value={promotion.purchase_window.starts_on} />
              </span>{' '}
              -{' '}
              <span className="font-bold">
                <DateValue value={promotion.purchase_window.ends_on} />
              </span>
            </section>
            <section>
              <h2 className="text-ink-muted">Claim period</h2>
              <ClaimPeriod window={promotion.claim_window} />
            </section>
          </div>
          <div className="flex flex-wrap gap-3">
            <ButtonLink variant="secondary" href="/check">
              Check my purchase
            </ButtonLink>
          </div>
        </Card>
        <div id="promotion-variants" className="space-y-6 scroll-mt-6">
          {promotion.variants.map((variant) => (
            <VariantDetails
              key={variant.promotion_variant_id}
              variant={variant}
              slug={promotion.public_slug}
            />
          ))}
        </div>
        <Card className="space-y-4 md:p-10">
          <h2 className="text-card font-bold">Official sources and terms</h2>
          <p>
            Last official source verified{' '}
            <Timestamp value={promotion.provenance.last_verified_at} />.
          </p>
          <p>The official provider controls eligibility, dates and claim acceptance.</p>
          <ul className="space-y-4">
            {promotion.sources.map((source) => (
              <li key={source.source_id}>
                <OfficialLink href={source.url}>{sourceRoles[source.role]}</OfficialLink>
                <p className="capitalize">
                  {source.source_type === 'pdf' ? 'PDF' : words(source.source_type)}
                </p>
                <p>
                  Retrieved <Timestamp value={source.retrieved_at} />
                </p>
                <p>
                  {source.verified_at ? (
                    <>
                      Verified <Timestamp value={source.verified_at} />
                    </>
                  ) : (
                    'Verification not recorded'
                  )}
                </p>
              </li>
            ))}
          </ul>
        </Card>
      </Container>
    </main>
  );
}

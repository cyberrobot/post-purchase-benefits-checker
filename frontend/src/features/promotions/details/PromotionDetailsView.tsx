import type { ReactNode } from 'react';
import { ButtonLink } from '@/components/ui/ButtonLink';
import { Card } from '@/components/ui/Card';
import { Container } from '@/components/ui/Container';
import { calendarDate, gbp, timestamp, words } from '@/features/eligibility/results/presentation';
import type { PromotionDetails } from '@/lib/api/promotion-details.contract';
import { VariantHashFocus } from './VariantHashFocus';

const categories = {
  cashback: 'Cashback',
  extended_warranty: 'Extended warranty',
  free_gift: 'Free gift',
};
const requirements = {
  receipt: 'Receipt',
  serial_number: 'Serial number',
  registration: 'Registration',
  invoice: 'Invoice',
  barcode: 'Barcode',
  imei: 'IMEI',
  installation_evidence: 'Installation evidence',
};
const sourceRoles = {
  primary: 'Official promotion source',
  terms: 'Terms',
  claim: 'Claim site',
  supporting: 'Supporting source',
};
type Variant = PromotionDetails['variants'][number];

function DateValue({ value }: { value: string | null }) {
  return value ? <time dateTime={value}>{calendarDate(value)}</time> : 'Not specified';
}

function Timestamp({ value }: { value: string }) {
  return <time dateTime={value}>{timestamp(value)}</time>;
}

function OfficialLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="font-semibold text-brand underline"
    >
      {children} <span className="text-small">(opens in a new tab)</span>
    </a>
  );
}

function ClaimPeriod({ window }: { window: PromotionDetails['claim_window'] }) {
  if (!window) return <p>Claim timing not recorded. Check the official terms.</p>;
  if (window.kind === 'relative') {
    return (
      <>
        <ul className="list-disc pl-6">
          <li>Opens {window.opens_after_purchase_days} calendar days after purchase.</li>
          <li>Deadline {window.deadline_after_purchase_days} calendar days after purchase.</li>
        </ul>
        <p>
          Individual dates depend on the purchase date. The opening and deadline days are included.
        </p>
      </>
    );
  }
  return (
    <>
      <p>
        Recorded claim period: <DateValue value={window.opens_on} /> to{' '}
        <DateValue value={window.deadline_on} />, inclusive.
      </p>
      {window.minimum_days_after_purchase !== null && (
        <p>
          At least {window.minimum_days_after_purchase} days after purchase. The earliest claim date
          for a purchase may be later than the recorded start.
        </p>
      )}
    </>
  );
}

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

function VariantDetails({ variant }: { variant: Variant }) {
  const id = 'variant-' + variant.promotion_variant_id;
  return (
    <Card
      id={id}
      tabIndex={-1}
      role="region"
      aria-labelledby={id + '-title'}
      className="min-w-0 scroll-mt-6 space-y-6 wrap-anywhere"
    >
      <div>
        <h2 id={id + '-title'} className="text-card font-bold">
          {variant.name || variant.code}
        </h2>
        {variant.name && <p className="text-small text-ink-muted">Variant code: {variant.code}</p>}
      </div>
      <section className="space-y-2">
        <h3 className="text-lg font-bold">Who qualifies</h3>
        <p>
          {variant.retailer ? (
            <>Qualifying retailer: {variant.retailer.name}</>
          ) : (
            'No retailer restriction recorded.'
          )}
        </p>
        <p className="font-semibold">Qualifying products and models</p>
        <ul className="list-disc pl-6">
          {variant.products.map((product) => (
            <li key={product.id}>
              <ProductName product={product} />
            </li>
          ))}
        </ul>
      </section>
      <section className="space-y-2">
        <h3 className="text-lg font-bold">Benefits</h3>
        <ul className="space-y-4">
          {variant.benefits.map((benefit) => (
            <li key={benefit.benefit_id}>
              <p className="text-small text-ink-muted">{categories[benefit.benefit_type]}</p>
              <h4 className="font-semibold">{benefit.name}</h4>
              <p>{benefit.description ?? 'Description not recorded.'}</p>
              <Reward benefit={benefit} products={variant.products} />
            </li>
          ))}
        </ul>
      </section>
      <section className="space-y-2">
        <h3 className="text-lg font-bold">What you need to claim</h3>
        {variant.requirements.length ? (
          <ul className="list-disc space-y-2 pl-6">
            {variant.requirements.map((item) => (
              <li key={item.requirement_id}>
                <strong>{requirements[item.requirement_type]}</strong>
                {item.description && <p>{item.description}</p>}
              </li>
            ))}
          </ul>
        ) : (
          <p>No claim requirements recorded here; check the official terms.</p>
        )}
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
      <Container className="wrap-anywhere">
        <header className="mb-8 space-y-3">
          <p className="font-semibold text-ink-muted">
            {promotion.manufacturer.name} ·{' '}
            {promotion.status === 'active' ? 'Recorded as active' : 'Recorded as expired'}
          </p>
          <h1 className="text-display leading-tight font-bold">{promotion.name}</h1>
          <ul className="flex flex-wrap gap-2" aria-label="Benefit categories">
            {Array.from(benefitTypes, (type) => (
              <li
                key={type}
                className="rounded-control border border-border px-3 py-1 text-small font-semibold"
              >
                {categories[type]}
              </li>
            ))}
          </ul>
          <p>
            These are recorded promotion terms. Check your purchase for an individual eligibility
            result.
          </p>
          <OfficialLink href={promotion.provenance.official_source_url}>
            Read official terms
          </OfficialLink>
        </header>
        <div className="grid min-w-0 gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
          <div className="min-w-0 space-y-6">
            <Card className="space-y-4">
              <section className="space-y-2">
                <h2 className="text-card font-bold">Qualifying purchase dates</h2>
                <p>
                  Start: <DateValue value={promotion.purchase_window.starts_on} />
                </p>
                <p>
                  End: <DateValue value={promotion.purchase_window.ends_on} />
                </p>
                <p>Recorded start and end days are included.</p>
              </section>
              <section className="space-y-2">
                <h2 className="text-card font-bold">Claim period</h2>
                <ClaimPeriod window={promotion.claim_window} />
              </section>
              <p>
                Only recorded conditions are shown here. Check the official terms for the full
                requirements.
              </p>
            </Card>
            {promotion.variants.map((variant) => (
              <VariantDetails key={variant.promotion_variant_id} variant={variant} />
            ))}
          </div>
          <div className="min-w-0 space-y-6">
            <Card className="space-y-4">
              <h2 className="text-card font-bold">Official sources and terms</h2>
              <p>
                Last official source verified{' '}
                <Timestamp value={promotion.provenance.last_verified_at} />.
              </p>
              <OfficialLink href={promotion.provenance.claim_url}>
                Visit official claim site
              </OfficialLink>
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
            <ButtonLink href="/check">Check my purchase</ButtonLink>
          </div>
        </div>
      </Container>
    </main>
  );
}

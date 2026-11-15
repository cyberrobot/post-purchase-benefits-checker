'use client';
import { useEffect, useRef, useState } from 'react';
import { Card } from '@/components/ui/Card';
import { ButtonLink } from '@/components/ui/ButtonLink';
import { usePurchaseCheckSession } from '../session/PurchaseCheckSession';
import type { PurchaseRequest } from '@/lib/api/eligibility.contract';
import { EligibilityExplanation } from './EligibilityExplanation';
import { RewardDetails } from './RewardDetails';
import { ClaimWindowSummary } from './ClaimWindowSummary';
import { reasonLabels, ruleStatusLabels } from './explanations';
import { completion } from '../components/purchaseForm';
import {
  calendarDate,
  counts,
  gbp,
  selectPromotions,
  statuses,
  timestamp,
  words,
  type Classification,
  type Promotion,
} from './presentation';
function RuleDetails({ promotion }: { promotion: Promotion }) {
  return (
    <details className="mt-5 rounded-control border border-border p-4">
      <summary className="cursor-pointer font-semibold">Recorded rules</summary>
      <h4 className="mt-3 font-semibold">Rule outcomes</h4>
      {promotion.eligibility.rule_evaluations.length ? (
        <ul className="mt-2 space-y-3">
          {promotion.eligibility.rule_evaluations.map((rule, i) => (
            <li key={i}>
              {words(rule.kind)}: <strong>{ruleStatusLabels[rule.status]}</strong>
              <span className="block text-small">{reasonLabels[rule.reason_code]}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p>Not supplied</p>
      )}
      <h4 className="mt-4 font-semibold">Recorded reasons</h4>
      {promotion.eligibility.reasons.length ? (
        <ul className="mt-2 space-y-2">
          {promotion.eligibility.reasons.map((reason, i) => (
            <li key={i}>{reasonLabels[reason.code]}</li>
          ))}
        </ul>
      ) : (
        <p>Not supplied</p>
      )}
    </details>
  );
}
function PromotionCard({
  promotion,
  manufacturer,
  evaluationDate,
  submittedPurchase,
  promotionDisambiguator,
}: {
  promotion: Promotion;
  manufacturer: string;
  evaluationDate: string;
  submittedPurchase: PurchaseRequest;
  promotionDisambiguator?: string;
}) {
  const status = statuses.find((s) => s.value === promotion.eligibility.classification)!;
  const [detailsOpen, setDetailsOpen] = useState(false);
  const supplemental = supplementalExplanations(promotion);
  const id = `promotion-${promotion.promotion_variant_id}`;
  const promotionName = normalizedPromotionName(promotion);
  const variantName = normalizedVariantName(promotion);
  const variantLabel = variantName && variantName !== promotionName;
  const promotionLabelledBy = `${id}${variantLabel ? ` ${id}-variant` : ''}${promotionDisambiguator ? ` ${id}-disambiguator` : ''}`;
  const failed = promotion.eligibility.classification === 'NOT_ELIGIBLE';
  const actionClass =
    'flex min-h-12 w-full cursor-pointer items-center justify-center gap-2 rounded-control px-4 py-3 text-center text-small font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-brand';
  const explanation = (
    <EligibilityExplanation
      promotion={promotion}
      submittedPurchase={submittedPurchase}
      promotionLabelledBy={promotionLabelledBy}
    />
  );
  return (
    <article
      aria-labelledby={promotionLabelledBy}
      className="min-w-0 rounded-feature border border-border bg-surface p-5 shadow-sm wrap-anywhere md:p-8 lg:p-10"
    >
      <div className="grid min-w-0 gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,1fr)] lg:gap-8">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
            <span
              className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold tracking-wide uppercase ${status.accent}`}
            >
              <span aria-hidden="true">{status.icon}</span>
              {status.label}
            </span>
            <p className="text-small text-ink-muted">
              {manufacturer && <>{manufacturer} · </>}Verified{' '}
              <time dateTime={promotion.last_verified_at}>
                {calendarDate(new Date(promotion.last_verified_at).toISOString().slice(0, 10))}
              </time>
            </p>
          </div>
          <h2 id={id} className="mt-3 text-xl leading-tight font-bold text-ink">
            {promotionName}
          </h2>
          {variantLabel && (
            <p id={`${id}-variant`} className="mt-1 font-semibold text-ink-muted">
              {variantName}
            </p>
          )}
          {promotionDisambiguator && (
            <span id={`${id}-disambiguator`} hidden>
              {promotionDisambiguator}
            </span>
          )}
          {failed && explanation}
          <RewardDetails
            benefits={promotion.benefits}
            hasPurchasePrice={submittedPurchase.purchase_price != null}
          />
          <ClaimWindowSummary promotion={promotion} evaluationDate={evaluationDate} />
          {!failed && explanation}
        </div>
        <div className="min-w-0 space-y-3 lg:pt-2">
          {promotion.public_slug && (
            <ButtonLink
              href={`/promotions/${promotion.public_slug}#variant-${promotion.promotion_variant_id}`}
              prefetch={false}
              className="w-full text-center"
            >
              View promotion page
            </ButtonLink>
          )}
          <button
            type="button"
            aria-expanded={detailsOpen}
            aria-controls={`${id}-details`}
            onClick={() => setDetailsOpen(!detailsOpen)}
            className={`${actionClass} bg-surface-muted text-ink-muted hover:bg-border`}
          >
            Show quick details
          </button>
          <a
            href={promotion.provenance.official_source_url}
            target="_blank"
            rel="noopener noreferrer"
            aria-label="Official Portal Terms (opens in a new tab)"
            className={`${actionClass} border border-border bg-surface text-ink-muted hover:bg-surface-muted`}
          >
            Official Portal Terms <span aria-hidden="true">↗</span>
          </a>
        </div>
      </div>
      <section
        id={`${id}-details`}
        hidden={!detailsOpen}
        aria-label="Full promotion details"
        className="mt-6 border-t border-border pt-5 text-small"
      >
        <h3 className="font-bold">Full promotion details</h3>
        <h4 className="mt-3 font-semibold">Supplemental recorded explanation</h4>
        {supplemental.length ? (
          supplemental.map((line, index) => (
            <p key={index} className="mt-2">
              {line}
            </p>
          ))
        ) : (
          <p>
            {promotion.explanation.length === 0
              ? 'No explanation supplied.'
              : 'No additional explanation supplied.'}
          </p>
        )}
        <p className="mt-2">Publication status: {words(promotion.promotion_status)}</p>
        <h4 className="mt-5 font-semibold">Claim requirements</h4>
        {promotion.requirements.length ? (
          <ul className="mt-2 list-disc space-y-2 pl-5">
            {promotion.requirements.map((requirement, i) => (
              <li key={i}>
                <span className="font-semibold">{words(requirement.requirement_type)}</span>
                {requirement.description && <p>{requirement.description}</p>}
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-2">
            The response lists no requirements. Check the official terms for what is needed.
          </p>
        )}
        <RuleDetails promotion={promotion} />
        <h4 className="mt-5 font-semibold">Source metadata</h4>
        <p className="mt-2">
          Source last verified:{' '}
          <time dateTime={promotion.last_verified_at}>{timestamp(promotion.last_verified_at)}</time>
        </p>
        <p>
          Source type: {words(promotion.provenance.source_type)} · Retrieved{' '}
          {timestamp(promotion.provenance.retrieved_at)} · Verified{' '}
          {timestamp(promotion.provenance.verified_at)}
        </p>
        <a
          href={promotion.provenance.claim_url}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-3 inline-block min-h-11 py-2 font-semibold text-ink underline underline-offset-4"
        >
          Open official claim site{' '}
          <span className="sr-only">
            (opens in a new tab; claim availability is subject to recorded timing and official
            terms)
          </span>
          <span aria-hidden="true"> ↗</span>
        </a>
        <ul className="mt-3 space-y-3">
          {promotion.sources.map((source) => (
            <li key={source.source_id}>
              <a
                href={source.url}
                target="_blank"
                rel="noopener noreferrer"
                className="underline underline-offset-4"
              >
                {words(source.role)} source<span className="sr-only"> (opens in a new tab)</span>
              </a>{' '}
              · {words(source.source_type)} · Retrieved {timestamp(source.retrieved_at)} · Verified{' '}
              {source.verified_at ? timestamp(source.verified_at) : 'Not supplied'}
            </li>
          ))}
        </ul>
      </section>
    </article>
  );
}
function normalizedPromotionName(promotion: Promotion) {
  return promotion.promotion_name.trim().replace(/\s+/g, ' ') || 'Promotion name not supplied';
}
function normalizedVariantName(promotion: Promotion) {
  return promotion.variant_name?.trim().replace(/\s+/g, ' ') || '';
}
function supplementalExplanations(promotion: Promotion) {
  const status = promotion.eligibility.claim_window_status;
  const window = promotion.claim_window;
  // Keep the original evidence when the structured timing fields disagree.
  if (window && window.status !== status) return promotion.explanation;

  // Match only the exact sentences generated by the backend.
  const redundant = {
    open: 'The claim window is open.',
    expired: 'The claim deadline has passed.',
    not_yet_open: window ? `Claiming opens on ${window.opens_on}.` : undefined,
    unspecified: 'The claim period is not available.',
  }[status ?? 'unspecified'];
  return promotion.explanation.filter((line) => line !== redundant);
}
function promotionAccessibleLabel(promotion: Promotion) {
  const name = normalizedPromotionName(promotion);
  const variant = normalizedVariantName(promotion);
  return variant && variant !== name ? `${name} ${variant}` : name;
}
function promotionDisambiguator(promotions: Promotion[], promotion: Promotion, index: number) {
  const label = promotionAccessibleLabel(promotion);
  const collisionCount = promotions.filter(
    (candidate) => promotionAccessibleLabel(candidate) === label,
  ).length;
  return collisionCount > 1 ? `Promotion result ${index + 1}` : undefined;
}
function RuleMatrix({
  promotions,
  submittedPurchase,
  showCards,
}: {
  promotions: Promotion[];
  showCards: () => void;
  submittedPurchase: PurchaseRequest;
}) {
  return (
    <div className="overflow-x-auto rounded-card border border-border bg-surface shadow-card">
      <p className="px-4 pt-4 text-small sm:px-6">
        <button
          type="button"
          onClick={showCards}
          className="min-h-11 cursor-pointer font-semibold underline underline-offset-4"
        >
          View benefits and claim periods in Cards
        </button>
      </p>
      <table className="w-full table-fixed text-left text-small">
        <caption className="px-6 py-5 text-left font-semibold">
          Recorded rule matrix — outcomes supplied by the eligibility check
        </caption>
        <thead className="border-y border-border bg-surface-muted">
          <tr>
            <th scope="col" className="w-1/3 px-4 py-3 sm:px-6">
              Promotion variant
            </th>
            <th scope="col" className="px-4 py-3 sm:px-6">
              Eligibility
            </th>
            <th scope="col" className="px-4 py-3 sm:px-6">
              Recorded rules
            </th>
          </tr>
        </thead>
        <tbody>
          {promotions.map((promotion, index) => {
            const id = `matrix-promotion-${promotion.promotion_variant_id}`;
            const status = statuses.find(
              (item) => item.value === promotion.eligibility.classification,
            )!;
            return (
              <tr
                key={promotion.promotion_variant_id}
                className="border-b border-border last:border-0"
              >
                <th scope="row" className="px-4 py-5 align-top font-semibold wrap-anywhere sm:px-6">
                  <h2 id={id}>{normalizedPromotionName(promotion)}</h2>
                  {normalizedVariantName(promotion) && (
                    <span id={`${id}-variant`} className="mt-1 block font-normal text-ink-muted">
                      {normalizedVariantName(promotion)}
                    </span>
                  )}
                </th>
                <td className="px-4 py-5 align-top wrap-anywhere sm:px-6">
                  <span
                    className={`inline-block rounded-control border px-2 py-1 font-semibold ${status.accent}`}
                  >
                    <span aria-hidden="true">{status.icon} </span>
                    {status.label}
                  </span>
                  <EligibilityExplanation
                    promotion={promotion}
                    submittedPurchase={submittedPurchase}
                    promotionLabelledBy={`${id}${normalizedVariantName(promotion) && normalizedVariantName(promotion) !== normalizedPromotionName(promotion) ? ` ${id}-variant` : ''}`}
                    promotionDisambiguator={promotionDisambiguator(promotions, promotion, index)}
                  />
                </td>
                <td className="px-4 py-5 align-top wrap-anywhere sm:px-6">
                  {promotion.eligibility.rule_evaluations.length ? (
                    <ul className="space-y-3">
                      {promotion.eligibility.rule_evaluations.map((rule, index) => (
                        <li key={index}>
                          <span className="font-semibold">
                            {words(rule.kind)}: {ruleStatusLabels[rule.status]}
                          </span>
                          <span className="mt-1 block text-ink-muted">
                            {reasonLabels[rule.reason_code]}
                          </span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    'No individual rule checks were supplied.'
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
export function ResultsOverview() {
  const { snapshot } = usePurchaseCheckSession();
  const [filter, setFilter] = useState<Classification | 'all'>('all');
  const [viewMode, setViewMode] = useState<'cards' | 'matrix'>('cards');
  const cardsViewRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    document.getElementById('main-content')?.focus();
  }, []);
  if (!snapshot)
    return (
      <Card>
        <h2 className="text-card font-bold">No results in this tab</h2>
        <p className="mt-3">
          Results stay in memory in this tab. Reloading or opening another tab clears them. Start a
          purchase check to see your results.
        </p>
        <ButtonLink href="/check" prefetch={false} className="mt-6">
          Start a purchase check
        </ButtonLink>
      </Card>
    );
  const { submittedPurchase: purchase, response } = snapshot;
  const promotions = response.outcome === 'resolved' ? response.promotions : [];
  const totals = counts(promotions);
  const selected = selectPromotions(promotions, filter);
  return (
    <div className="space-y-8">
      <section
        aria-label="Checked purchase summary"
        className="rounded-card border border-brand/10 bg-surface p-6 shadow-xl shadow-brand/5 wrap-anywhere md:p-8"
      >
        <div className="flex flex-col justify-between gap-4 border-b border-border pb-6 md:flex-row md:items-center">
          <div className="min-w-0">
            <p className="block text-[11px] font-bold tracking-wider text-brand uppercase">
              Purchase details checked
            </p>
            <h2 className="mt-0.5 text-xl font-bold md:text-2xl">
              {purchase.brand} · {purchase.model}
            </h2>
            <dl className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-2 text-xs text-ink-muted">
              <div className="flex min-w-0 flex-wrap gap-x-1">
                <dt>Retailer:</dt>
                <dd className="min-w-0 font-bold text-ink wrap-anywhere">{purchase.retailer}</dd>
              </div>
              <div className="flex flex-wrap gap-x-1">
                <dt>Purchase date:</dt>
                <dd className="font-bold text-ink">
                  <time dateTime={purchase.purchase_date}>
                    {calendarDate(purchase.purchase_date)}
                  </time>
                </dd>
              </div>
              {purchase.purchase_price != null && (
                <div className="flex flex-wrap gap-x-1">
                  <dt>Paid amount:</dt>
                  <dd className="font-bold text-ink">{gbp(purchase.purchase_price)}</dd>
                </div>
              )}
              <div className="flex flex-wrap gap-x-1">
                <dt>Evaluated on:</dt>
                <dd className="font-bold text-ink">
                  <time dateTime={response.evaluation_date}>
                    {calendarDate(response.evaluation_date)}
                  </time>
                </dd>
              </div>
            </dl>
          </div>
          <div className="flex shrink-0 flex-wrap items-center gap-3 md:max-lg:max-w-56">
            <ButtonLink
              href="/check"
              prefetch={false}
              variant="ghost"
              className="gap-1.5 border-transparent bg-surface-muted px-4 py-2.5 text-xs font-bold"
            >
              <svg
                aria-hidden="true"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.8"
                className="h-3.5 w-3.5 text-ink-muted"
              >
                <path d="m16 3 5 5-12 12-6 1 1-6L16 3Z" />
                <path d="m13 6 5 5" />
              </svg>
              Edit purchase details
            </ButtonLink>
            {promotions.length > 0 && (
              <div
                role="group"
                aria-label="Results view"
                className="flex items-center rounded-control bg-surface-muted p-1 text-xs font-bold"
              >
                {(['cards', 'matrix'] as const).map((mode) => (
                  <button
                    type="button"
                    key={mode}
                    aria-pressed={viewMode === mode}
                    ref={mode === 'cards' ? cardsViewRef : undefined}
                    onClick={() => setViewMode(mode)}
                    className={`min-h-11 cursor-pointer rounded-control px-3 py-1.5 transition-colors ${viewMode === mode ? 'bg-surface text-ink shadow-xs' : 'text-ink-muted hover:text-ink'}`}
                  >
                    {mode === 'cards' ? 'Cards' : 'Rule Matrix'}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
        {promotions.length > 0 && (
          <div className="flex flex-col justify-between gap-4 pt-6 xl:flex-row xl:items-center">
            <h2 className="shrink-0 text-small font-semibold text-ink-muted">
              {promotions.length} promotion variant matches
            </h2>
            <div
              className="flex flex-wrap gap-1 rounded-control bg-surface-muted p-1"
              role="group"
              aria-label="Filter promotion results"
            >
              {[{ value: 'all' as const, label: 'All' }, ...statuses].map(({ value, label }) => (
                <button
                  type="button"
                  key={value}
                  aria-pressed={filter === value}
                  onClick={() => setFilter(value)}
                  className={`min-h-11 max-w-full cursor-pointer rounded-control px-3 py-2 text-xs font-bold transition-colors ${filter === value ? 'bg-surface text-ink shadow-xs' : 'text-ink-muted hover:text-ink'}`}
                >
                  {label} ({value === 'all' ? promotions.length : totals[value]})
                </button>
              ))}
            </div>
          </div>
        )}
      </section>
      {response.outcome === 'unresolved_identity' ? (
        <Card>
          <h2 className="text-card font-bold">
            Check your{' '}
            {response.unresolved_identity.field === 'model'
              ? 'product model or SKU'
              : response.unresolved_identity.field}
          </h2>
          <p className="mt-3">{completion(response)[0]}</p>
          <ButtonLink href="/check" prefetch={false} className="mt-6">
            Edit purchase details
          </ButtonLink>
        </Card>
      ) : promotions.length === 0 ? (
        <Card>
          <h2 className="text-card font-bold">No matching published promotions</h2>
          <p className="mt-3">
            No matching published promotions were found for these purchase details. Other offers may
            exist outside the published data checked.
          </p>
        </Card>
      ) : (
        <>
          <p
            role="status"
            aria-live="polite"
            aria-atomic="true"
            className="text-small text-ink-muted"
          >
            Showing {selected.length} of {promotions.length} promotion variant matches
            {filter !== 'all' ? `: ${statuses.find((s) => s.value === filter)!.label}` : ''}.
          </p>
          {selected.length ? (
            viewMode === 'matrix' ? (
              <RuleMatrix
                promotions={selected}
                showCards={() => {
                  setViewMode('cards');
                  cardsViewRef.current?.focus();
                }}
                submittedPurchase={purchase}
              />
            ) : (
              selected.map((promotion, index) => (
                <PromotionCard
                  key={promotion.promotion_variant_id}
                  promotion={promotion}
                  manufacturer={purchase.brand}
                  evaluationDate={response.evaluation_date}
                  submittedPurchase={purchase}
                  promotionDisambiguator={promotionDisambiguator(selected, promotion, index)}
                />
              ))
            )
          ) : (
            <Card>
              <h2 className="text-card font-bold">No results in this category</h2>
              <button
                type="button"
                onClick={() => setFilter('all')}
                className="mt-4 min-h-11 rounded-control border border-brand px-4 py-2 font-semibold text-brand"
              >
                Show all results
              </button>
            </Card>
          )}
        </>
      )}
    </div>
  );
}

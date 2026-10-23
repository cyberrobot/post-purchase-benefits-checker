'use client';
import { useEffect, useState } from 'react';
import { Card } from '@/components/ui/Card';
import { ButtonLink } from '@/components/ui/ButtonLink';
import { usePurchaseCheckSession } from '../session/PurchaseCheckSession';
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
              {words(rule.kind)}: <strong>{words(rule.status)}</strong>
              <span className="block text-small">{words(rule.reason_code)}</span>
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
            <li key={i}>{words(reason.code)}</li>
          ))}
        </ul>
      ) : (
        <p>Not supplied</p>
      )}
    </details>
  );
}
function criterionLabel(reason: string) {
  const labels: Record<string, string> = {
    retailer_match: 'Retailer matches recorded promotion rules',
    purchase_date_match: 'Purchase date meets the recorded date rule',
    purchase_price_unknown: 'Purchase price could not be evaluated',
    product_match: 'Product matches recorded promotion rules',
    manufacturer_match: 'Manufacturer matches recorded promotion rules',
    purchase_channel_match: 'Purchase channel matches recorded promotion rules',
    country_match: 'Country matches recorded promotion rules',
    condition_match: 'Product condition matches recorded promotion rules',
    purchase_price_match: 'Purchase price meets the recorded price rule',
    purchase_date_before_start: 'Purchase date is before the recorded promotion starts',
    purchase_date_after_end: 'Purchase date is after the recorded promotion ends',
    purchase_price_below_minimum: 'Purchase price is below the recorded minimum',
    purchase_price_above_maximum: 'Purchase price is above the recorded maximum',
  };
  if (labels[reason]) return labels[reason];
  if (reason.endsWith('_unknown'))
    return `${words(reason.replace('_unknown', ''))} could not be evaluated`;
  if (reason.endsWith('_mismatch'))
    return `${words(reason.replace('_mismatch', ''))} does not match recorded promotion rules`;
  return words(reason);
}
function ClockIcon() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      className="h-5 w-5 shrink-0"
    >
      <circle cx="12" cy="12" r="9" />
      <path d="M12 6v6l4 2" />
    </svg>
  );
}
function PromotionCard({
  promotion,
  manufacturer,
}: {
  promotion: Promotion;
  manufacturer: string;
}) {
  const status = statuses.find((s) => s.value === promotion.eligibility.classification)!;
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [guideOpen, setGuideOpen] = useState(false);
  const id = `promotion-${promotion.promotion_variant_id}`;
  const upcoming = promotion.eligibility.classification === 'CLAIM_NOT_YET_OPEN';
  const actionClass =
    'flex min-h-12 w-full cursor-pointer items-center justify-center gap-2 rounded-control px-4 py-3 text-center text-small font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-brand';
  return (
    <article
      aria-labelledby={id}
      className="min-w-0 rounded-feature border border-border bg-surface p-5 shadow-sm wrap-anywhere md:p-8 lg:p-10"
    >
      <div className="grid min-w-0 gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,1fr)] lg:gap-8">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
            <span
              className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold tracking-wide uppercase ${status.accent}`}
            >
              <span aria-hidden="true">{status.icon}</span>
              {upcoming ? 'Claim not yet open' : status.label}
            </span>
            <p className="text-small text-ink-muted">
              {manufacturer && <>{manufacturer} · </>}Verified{' '}
              <time dateTime={promotion.last_verified_at}>
                {calendarDate(new Date(promotion.last_verified_at).toISOString().slice(0, 10))}
              </time>
            </p>
          </div>
          <h2 id={id} className="mt-3 text-2xl leading-tight font-bold text-ink md:text-[1.875rem]">
            {promotion.promotion_name || 'Promotion name not supplied'}
          </h2>
          {promotion.variant_name && promotion.variant_name !== promotion.promotion_name && (
            <p className="mt-1 font-semibold text-ink-muted">{promotion.variant_name}</p>
          )}
          <div className="mt-5 space-y-3">
            {promotion.benefits.length ? (
              promotion.benefits.map((benefit, index) => (
                <div key={benefit.benefit_id}>
                  <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                    <h3
                      className={
                        index === 0
                          ? 'text-3xl leading-tight font-bold text-ink md:text-[2.5rem]'
                          : 'text-xl leading-snug font-bold text-ink'
                      }
                    >
                      {benefit.benefit_type === 'cashback' && benefit.cashback_reward_gbp !== null
                        ? `${gbp(benefit.cashback_reward_gbp)} cashback`
                        : benefit.name || words(benefit.benefit_type)}
                    </h3>
                    {benefit.benefit_type === 'cashback' &&
                      benefit.cashback_reward_gbp !== null && (
                        <span className="text-small text-ink-muted">recorded cashback benefit</span>
                      )}
                  </div>
                  {benefit.benefit_type === 'cashback' && benefit.cashback_reward_gbp === null && (
                    <p className="mt-1 text-small text-ink-muted">
                      {benefit.reward_unavailable_explanation ||
                        (benefit.reward_unavailable_reason
                          ? words(benefit.reward_unavailable_reason)
                          : 'No monetary reward amount supplied.')}
                    </p>
                  )}
                </div>
              ))
            ) : (
              <p>No benefit details supplied.</p>
            )}
          </div>
          <div className="mt-5 rounded-control border border-border/60 bg-surface-muted p-4 text-small leading-relaxed md:p-5">
            <p>
              <strong className="text-ink">Rule explanation: </strong>
              {promotion.explanation[0] || 'No explanation supplied.'}
            </p>
            {promotion.explanation.slice(1).map((line, i) => (
              <p key={i} className="mt-1">
                {line}
              </p>
            ))}
          </div>
          <section
            aria-label="Evaluated criteria points"
            className="mt-5 border-t border-border pt-4"
          >
            <h3 className="text-xs font-bold tracking-wider text-ink-muted uppercase">
              Evaluated criteria points:
            </h3>
            <ul className="mt-3 grid gap-x-6 gap-y-2 text-small text-ink-muted sm:grid-cols-2">
              {promotion.eligibility.rule_evaluations.map((rule, i) => (
                <li key={i} className="flex items-start gap-2">
                  <span
                    aria-hidden="true"
                    className={`shrink-0 font-semibold ${rule.status === 'satisfied' ? 'text-success' : rule.status === 'unknown' ? 'text-amber-700' : 'text-red-700'}`}
                  >
                    {rule.status === 'satisfied' ? '✓' : rule.status === 'unknown' ? '?' : '×'}
                  </span>
                  <span>
                    <span className="sr-only">{words(rule.status)}: </span>
                    {criterionLabel(rule.reason_code)}
                  </span>
                </li>
              ))}
              {!promotion.eligibility.rule_evaluations.length && (
                <li>Rule evaluations: Not supplied</li>
              )}
              {promotion.claim_window ? (
                <>
                  <li className="flex items-start gap-2">
                    <ClockIcon />
                    <span>
                      Claim window opens{' '}
                      <time dateTime={promotion.claim_window.opens_on}>
                        {calendarDate(promotion.claim_window.opens_on)}
                      </time>
                    </span>
                  </li>
                  <li className="flex items-start gap-2">
                    <ClockIcon />
                    <span>
                      Claim deadline{' '}
                      <time dateTime={promotion.claim_window.deadline_on}>
                        {calendarDate(promotion.claim_window.deadline_on)}
                      </time>
                    </span>
                  </li>
                </>
              ) : (
                <li className="flex items-start gap-2">
                  <ClockIcon />
                  <span>
                    Claim timing:{' '}
                    {promotion.eligibility.claim_window_status
                      ? words(promotion.eligibility.claim_window_status)
                      : 'Not supplied'}
                  </span>
                </li>
              )}
            </ul>
          </section>
        </div>
        <div className="min-w-0 space-y-3 lg:pt-2">
          {upcoming && (
            <button
              type="button"
              aria-expanded={guideOpen}
              aria-controls={`${id}-guide`}
              onClick={() => setGuideOpen(!guideOpen)}
              className={`${actionClass} bg-ink text-white hover:bg-ink/90`}
            >
              <ClockIcon />
              Claim Window Guide
            </button>
          )}
          <button
            type="button"
            aria-expanded={detailsOpen}
            aria-controls={`${id}-details`}
            onClick={() => setDetailsOpen(!detailsOpen)}
            className={`${actionClass} bg-surface-muted text-ink-muted hover:bg-border`}
          >
            View Full Promotion Details
          </button>
          <a
            href={promotion.provenance.official_source_url}
            target="_blank"
            rel="noopener noreferrer"
            className={`${actionClass} border border-border bg-surface text-ink-muted hover:bg-surface-muted`}
          >
            Official Portal Terms <span aria-hidden="true">↗</span>
            <span className="sr-only">(opens in a new tab)</span>
          </a>
        </div>
      </div>
      {upcoming && (
        <section
          id={`${id}-guide`}
          hidden={!guideOpen}
          aria-label="Claim window guide"
          className="mt-6 rounded-control border border-border bg-surface-muted p-5 text-small"
        >
          <h3 className="font-bold">Claim window guide</h3>
          <p className="mt-2">{status.meaning}</p>
          {promotion.claim_window ? (
            <p className="mt-2">
              Recorded opening date: {calendarDate(promotion.claim_window.opens_on)}. Recorded
              deadline: {calendarDate(promotion.claim_window.deadline_on)}.
            </p>
          ) : (
            <p className="mt-2">Opening and deadline dates were not supplied.</p>
          )}
        </section>
      )}
      <section
        id={`${id}-details`}
        hidden={!detailsOpen}
        aria-label="Full promotion details"
        className="mt-6 border-t border-border pt-5 text-small"
      >
        <h3 className="font-bold">Full promotion details</h3>
        <p className="mt-2">{status.meaning}</p>
        <p className="mt-2">Publication status: {words(promotion.promotion_status)}</p>
        {promotion.benefits.map((benefit) => (
          <div key={benefit.benefit_id} className="mt-4">
            <h4 className="font-semibold">
              {benefit.name || words(benefit.benefit_type)} · {words(benefit.benefit_type)}
            </h4>
            {benefit.description && <p className="mt-1">{benefit.description}</p>}
          </div>
        ))}
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
function RuleMatrix({ promotions }: { promotions: Promotion[] }) {
  return (
    <div className="overflow-x-auto rounded-card border border-border bg-surface shadow-card">
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
          {promotions.map((promotion) => {
            const status = statuses.find(
              (item) => item.value === promotion.eligibility.classification,
            )!;
            return (
              <tr
                key={promotion.promotion_variant_id}
                className="border-b border-border last:border-0"
              >
                <th scope="row" className="px-4 py-5 align-top font-semibold wrap-anywhere sm:px-6">
                  {promotion.promotion_name || 'Promotion name not supplied'}
                  {promotion.variant_name && (
                    <span className="mt-1 block font-normal text-ink-muted">
                      {promotion.variant_name}
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
                </td>
                <td className="px-4 py-5 align-top wrap-anywhere sm:px-6">
                  {promotion.eligibility.rule_evaluations.length ? (
                    <ul className="space-y-3">
                      {promotion.eligibility.rule_evaluations.map((rule, index) => (
                        <li key={index}>
                          <span className="font-semibold">
                            {words(rule.kind)}: {words(rule.status)}
                          </span>
                          <span className="mt-1 block text-ink-muted">
                            {words(rule.reason_code)}
                          </span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    'Not supplied'
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
              <RuleMatrix promotions={selected} />
            ) : (
              selected.map((promotion) => (
                <PromotionCard
                  key={promotion.promotion_variant_id}
                  promotion={promotion}
                  manufacturer={purchase.brand}
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

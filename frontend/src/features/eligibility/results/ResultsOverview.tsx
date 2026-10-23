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
function PromotionCard({ promotion }: { promotion: Promotion }) {
  const status = statuses.find((s) => s.value === promotion.eligibility.classification)!;
  return (
    <article
      aria-labelledby={`promotion-${promotion.promotion_variant_id}`}
      className={`min-w-0 rounded-feature border-2 bg-surface p-5 shadow-card wrap-anywhere md:p-8 ${promotion.eligibility.classification === 'ELIGIBLE' ? 'border-success' : 'border-border'}`}
    >
      <div className="grid min-w-0 gap-8 lg:grid-cols-[minmax(0,1fr)_minmax(14rem,19rem)]">
        <div className="min-w-0">
          <span
            className={`inline-block rounded-full border px-3 py-1 text-small font-semibold ${status.accent}`}
          >
            <span aria-hidden="true">{status.icon} </span>
            {status.label}
          </span>
          <p className="mt-3 text-small text-ink-muted">
            Source last verified:{' '}
            <time dateTime={promotion.last_verified_at}>
              {timestamp(promotion.last_verified_at)}
            </time>
          </p>
          <h2
            id={`promotion-${promotion.promotion_variant_id}`}
            className="mt-4 text-card font-bold md:text-[2rem]"
          >
            {promotion.promotion_name || 'Promotion name not supplied'}
          </h2>
          {promotion.variant_name && (
            <p className="mt-1 font-semibold text-ink-muted">{promotion.variant_name}</p>
          )}
          <p className="mt-3 text-small">{status.meaning}</p>
          <div className="mt-6 space-y-5">
            {promotion.benefits.length ? (
              promotion.benefits.map((benefit) => (
                <div key={benefit.benefit_id}>
                  <h3 className="text-card font-bold">
                    {benefit.cashback_reward_gbp !== null
                      ? `${gbp(benefit.cashback_reward_gbp)} cashback`
                      : benefit.name || words(benefit.benefit_type)}
                  </h3>
                  <p className="text-small text-ink-muted">
                    {benefit.name} · {words(benefit.benefit_type)}
                  </p>
                  {benefit.description && <p className="mt-1">{benefit.description}</p>}
                  {benefit.benefit_type === 'cashback' && benefit.cashback_reward_gbp === null && (
                    <p className="mt-1 text-small">
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
          <div className="mt-6 rounded-control bg-surface-muted p-4">
            <h3 className="font-semibold">Recorded explanation</h3>
            {promotion.explanation.length ? (
              promotion.explanation.map((line, i) => (
                <p className="mt-2" key={i}>
                  {line}
                </p>
              ))
            ) : (
              <p className="mt-2">No explanation supplied.</p>
            )}
          </div>
          <div className="mt-6 border-t border-border pt-4 text-small">
            <p>
              Recorded claim timing:{' '}
              {promotion.eligibility.claim_window_status === 'open'
                ? 'Claim period open'
                : promotion.eligibility.claim_window_status
                  ? words(promotion.eligibility.claim_window_status)
                  : 'Not supplied'}
            </p>
            {promotion.claim_window && (
              <dl className="mt-2 grid gap-2 sm:grid-cols-2">
                <div>
                  <dt className="font-semibold">Claim opens</dt>
                  <dd>
                    <time dateTime={promotion.claim_window.opens_on}>
                      {calendarDate(promotion.claim_window.opens_on)}
                    </time>
                  </dd>
                </div>
                <div>
                  <dt className="font-semibold">Claim deadline</dt>
                  <dd>
                    <time dateTime={promotion.claim_window.deadline_on}>
                      {calendarDate(promotion.claim_window.deadline_on)}
                    </time>
                  </dd>
                </div>
              </dl>
            )}
            <p className="mt-2">Publication status: {words(promotion.promotion_status)}</p>
          </div>
        </div>
        <div className="min-w-0 space-y-4">
          <details className="rounded-control border border-border p-4">
            <summary className="cursor-pointer font-semibold">View claim requirements</summary>
            {promotion.requirements.length ? (
              <ul className="mt-3 list-disc space-y-3 pl-5">
                {promotion.requirements.map((requirement, i) => (
                  <li key={i}>
                    <span className="font-semibold">{words(requirement.requirement_type)}</span>
                    {requirement.description && <p>{requirement.description}</p>}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-3 text-small">
                The response lists no requirements. Check the official terms for what is needed.
              </p>
            )}
          </details>
          <details className="rounded-control border border-border p-4">
            <summary className="cursor-pointer font-semibold">Recorded rules</summary>
            <h3 className="mt-3 font-semibold">Rule outcomes</h3>
            {promotion.eligibility.rule_evaluations.length ? (
              <ul className="mt-2 space-y-3">
                {promotion.eligibility.rule_evaluations.map((rule, i) => (
                  <li key={i}>
                    {words(rule.kind)}: <strong>{words(rule.status)}</strong>
                    <br />
                    <span className="text-small">{words(rule.reason_code)}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p>Not supplied</p>
            )}
            <h3 className="mt-4 font-semibold">Recorded reasons</h3>
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
          <ButtonLink
            href={promotion.provenance.official_source_url}
            target="_blank"
            variant="secondary"
            className="w-full"
          >
            Official promotion source / terms <span className="sr-only">(opens in a new tab)</span>
            <span aria-hidden="true"> ↗</span>
          </ButtonLink>
          <ButtonLink
            href={promotion.provenance.claim_url}
            target="_blank"
            variant="secondary"
            className="w-full"
          >
            Open official claim site <span className="sr-only">(opens in a new tab)</span>
            <span aria-hidden="true"> ↗</span>
          </ButtonLink>
        </div>
      </div>
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
                <PromotionCard key={promotion.promotion_variant_id} promotion={promotion} />
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

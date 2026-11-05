import type { PurchaseRequest } from '@/lib/api/eligibility.contract';
import { calendarDate, type Promotion } from './presentation';
import { explainPromotion } from './explanations';
export function EligibilityExplanation({
  promotion,
  evaluationDate,
  submittedPurchase,
}: {
  promotion: Promotion;
  evaluationDate: string;
  submittedPurchase: PurchaseRequest;
}) {
  const view = explainPromotion(promotion, { evaluationDate, submittedPurchase });
  return (
    <section
      aria-label="Eligibility explanation"
      className="mt-5 space-y-4 rounded-control border border-border/60 bg-surface-muted p-4 text-small leading-relaxed"
    >
      <h3 className="font-bold text-ink">Why this result?</h3>
      <p>{view.summary}</p>
      {view.decisions.length ? (
        <div>
          <h4 className="font-semibold">Decision reasons</h4>
          <ul className="mt-2 list-disc space-y-2 pl-5">
            {view.decisions.map((item) => (
              <li key={item.key}>{item.text}</li>
            ))}
          </ul>
        </div>
      ) : (
        <p>Detailed reasons were not supplied.</p>
      )}
      {view.groups
        .filter((group) => group.items.length > 0)
        .map((group) => {
          const content = (
            <ul className="mt-2 list-disc space-y-2 pl-5">
              {group.items.map((item) => (
                <li key={item.key}>{item.text}</li>
              ))}
            </ul>
          );
          return group.status === 'satisfied' ? (
            <details key={group.status}>
              <summary className="min-h-11 cursor-pointer py-2 font-semibold">
                {group.heading}
              </summary>
              {content}
            </details>
          ) : (
            <div key={group.status}>
              <h4 className="font-semibold">{group.heading}</h4>
              {group.status === 'unknown' &&
                promotion.eligibility.classification === 'NOT_ELIGIBLE' && (
                  <p>These unknown facts are not the reason for this decision.</p>
                )}
              {content}
            </div>
          );
        })}
      {!promotion.eligibility.rule_evaluations.length && (
        <p>No individual rule checks were supplied.</p>
      )}
      <div>
        <h4 className="font-semibold">Claim period</h4>
        <p>
          {view.claimTiming} {view.evaluatedOn}
        </p>
        {promotion.claim_window ? (
          <dl className="mt-2 space-y-1">
            <div>
              <dt className="inline font-semibold">Claim window opens: </dt>
              <dd className="inline">
                <time dateTime={promotion.claim_window.opens_on}>
                  {calendarDate(promotion.claim_window.opens_on)}
                </time>
              </dd>
            </div>
            <div>
              <dt className="inline font-semibold">Claim deadline: </dt>
              <dd className="inline">
                <time dateTime={promotion.claim_window.deadline_on}>
                  {calendarDate(promotion.claim_window.deadline_on)}
                </time>
              </dd>
            </div>
          </dl>
        ) : (
          <p>Opening and deadline dates were not supplied.</p>
        )}
      </div>
      {view.guidance.map((line, index) => (
        <p key={index}>{line}</p>
      ))}
    </section>
  );
}

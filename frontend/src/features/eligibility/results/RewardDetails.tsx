import Link from 'next/link';
import { presentBenefit, type Promotion } from './presentation';

export function RewardDetails({
  benefits,
  hasPurchasePrice,
}: {
  benefits: Promotion['benefits'];
  hasPurchasePrice: boolean;
}) {
  return (
    <div className="mt-5">
      <h3 className="font-bold">Benefits</h3>
      {benefits.length ? (
        <ul className="mt-2 list-disc space-y-3 pl-5">
          {benefits.map((benefit) => {
            const view = presentBenefit(benefit, hasPurchasePrice);
            return (
              <li key={benefit.benefit_id}>
                <h4 className="font-semibold">{view.category}</h4>
                {view.title !== view.category && <p>{view.title}</p>}
                {view.description && <p className="text-small">{view.description}</p>}
                {view.amountLabel && (
                  <p className="text-xl font-bold">
                    <span>{view.amountLabel}</span>{' '}
                    <span className="text-small font-normal text-ink-muted">recorded benefit</span>
                  </p>
                )}
                {view.unavailableLabel && <p className="font-semibold">{view.unavailableLabel}</p>}
                {view.unavailableExplanation && (
                  <p className="text-small">{view.unavailableExplanation}</p>
                )}
                {view.canRecheckWithPurchasePrice && (
                  <p className="text-small">
                    <Link
                      href="/check"
                      prefetch={false}
                      className="font-semibold underline underline-offset-4"
                    >
                      Edit purchase details
                    </Link>{' '}
                    to add the optional purchase price, then submit a new check for an updated
                    result.
                  </p>
                )}
              </li>
            );
          })}
        </ul>
      ) : (
        <p>No benefit details supplied.</p>
      )}
    </div>
  );
}

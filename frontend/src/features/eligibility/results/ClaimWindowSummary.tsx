import { calendarDate, presentClaimPeriod, type Promotion } from './presentation';

export function ClaimWindowSummary({
  promotion,
  evaluationDate,
}: {
  promotion: Promotion;
  evaluationDate: string;
}) {
  const { timingLabel, opensOn, deadlineOn } = presentClaimPeriod(promotion);
  return (
    <div className="mt-5 rounded-control border border-border/60 p-4 text-small">
      <h3 className="font-bold">Claim period</h3>
      <p>{timingLabel}</p>
      <p>
        As evaluated on <time dateTime={evaluationDate}>{calendarDate(evaluationDate)}</time>.
      </p>
      {opensOn || deadlineOn ? (
        <dl className="mt-2 space-y-1">
          {opensOn && (
            <div>
              <dt className="inline font-semibold">Claim period opens</dt>
              <dd className="inline">
                : <time dateTime={opensOn}>{calendarDate(opensOn)}</time>
              </dd>
            </div>
          )}
          {deadlineOn && (
            <div>
              <dt className="inline font-semibold">Claim deadline</dt>
              <dd className="inline">
                : <time dateTime={deadlineOn}>{calendarDate(deadlineOn)}</time>
              </dd>
            </div>
          )}
        </dl>
      ) : (
        <p className="mt-2">Opening and deadline dates not supplied.</p>
      )}
    </div>
  );
}

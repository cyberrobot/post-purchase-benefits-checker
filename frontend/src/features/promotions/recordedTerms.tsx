import type { ReactNode } from 'react';
import { calendarDate, timestamp } from '@/features/eligibility/results/presentation';
import type { PromotionDetails } from '@/lib/api/promotion-details.contract';

export function DateValue({ value }: { value: string | null }) {
  return value ? <time dateTime={value}>{calendarDate(value)}</time> : 'Not specified';
}

export function Timestamp({ value }: { value: string }) {
  return <time dateTime={value}>{timestamp(value)}</time>;
}

export function OfficialLink({ href, children }: { href: string; children: ReactNode }) {
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

export function ClaimPeriod({ window }: { window: PromotionDetails['claim_window'] }) {
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

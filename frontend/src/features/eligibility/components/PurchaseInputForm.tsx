'use client';
import { useEffect, useId, useRef, useState, type FormEvent } from 'react';
import { Button } from '@/components/ui/Button';
import { useCheckPurchaseMutation } from '../api/useCheckPurchaseMutation';
import { purchaseRequestSchema, type CheckPurchaseResponse } from '@/lib/api/eligibility.contract';
import { ApiError } from '@/lib/api/errors';
const fields = [
  { name: 'brand', label: 'Manufacturer', help: 'e.g. Samsung', type: 'text' },
  {
    name: 'model',
    label: 'Model number',
    help: 'Find the exact model/SKU on the product or receipt',
    type: 'text',
  },
  { name: 'retailer', label: 'Retailer', help: 'Where did you buy it?', type: 'text' },
  {
    name: 'purchase_date',
    label: 'Purchase date',
    help: 'Choose the date shown on your receipt',
    type: 'date',
  },
] as const;
type Field = (typeof fields)[number]['name'];
type Draft = Record<Field, string>;
type Errors = Partial<Record<Field, string>>;
const empty: Draft = { brand: '', model: '', retailer: '', purchase_date: '' };
export function validatePurchase(draft: Draft): Errors {
  const result = purchaseRequestSchema.safeParse(draft);
  const errors: Errors = {};
  if (!result.success)
    for (const issue of result.error.issues) {
      const field = fields.find((item) => item.name === issue.path[0]);
      if (!field) continue;
      errors[field.name] =
        field.type === 'date'
          ? 'Enter a valid purchase date'
          : draft[field.name].normalize('NFKC').trim().length === 0
            ? `Enter the ${field.label.toLowerCase()}`
            : draft[field.name].length > 255
              ? 'Use 255 characters or fewer'
              : 'Remove unsupported control characters';
    }
  return errors;
}
function completion(data: CheckPurchaseResponse): string {
  if (data.outcome === 'unresolved_identity') {
    const label = fields
      .find((field) => field.name === data.unresolved_identity.field)!
      .label.toLowerCase();
    return data.unresolved_identity.status === 'ambiguous'
      ? `More than one ${label} matched. Check and clarify the ${label}, then try again.`
      : `The ${label} could not be found. Check the ${label}, then try again.`;
  }
  if (!data.promotions.length)
    return 'No matching published promotion was found for these purchase details.';
  return `The check returned ${data.promotions.length} promotion ${data.promotions.length === 1 ? 'record' : 'records'} requiring eligibility review. Detailed results are not yet shown.`;
}
function failure(error: unknown): string {
  if (!(error instanceof ApiError))
    return 'The checker encountered a service problem. Please try again.';
  switch (error.kind) {
    case 'validation':
      return 'The checker could not accept these details. Check the manufacturer, model, retailer and purchase date against your receipt, then try again.';
    case 'rate_limited': {
      const seconds = error.retryAfterSeconds;
      if (seconds === undefined || !Number.isFinite(seconds) || seconds < 0 || seconds > 86400)
        return 'Too many checks. Please wait before trying again.';
      const wait =
        seconds < 60
          ? `${Math.ceil(seconds)} seconds`
          : seconds < 3600
            ? `${Math.ceil(seconds / 60)} minutes`
            : `${Math.ceil(seconds / 3600)} hours`;
      return `Too many checks. Please wait ${wait} before trying again.`;
    }
    case 'timeout':
      return 'The check took too long. Please try again.';
    case 'cancelled':
      return 'The check was cancelled. You can try again.';
    case 'unavailable':
      return 'The checker is temporarily unavailable. Please try again later.';
    case 'server':
    case 'contract':
      return 'The checker encountered a service problem. Please try again.';
  }
}
export function PurchaseInputForm() {
  const id = useId();
  const [draft, setDraft] = useState<Draft>(empty);
  const [attempted, setAttempted] = useState(false);
  const [focusRequest, setFocusRequest] = useState<{ field: Field }>();
  const [feedback, setFeedback] = useState<{ text: string; failed: boolean }>();
  const [pending, setPending] = useState(false);
  const inFlight = useRef(false);
  const inputs = useRef<Partial<Record<Field, HTMLInputElement | null>>>({});
  const mutation = useCheckPurchaseMutation();
  const errors = attempted ? validatePurchase(draft) : {};
  useEffect(() => {
    if (focusRequest) inputs.current[focusRequest.field]?.focus();
  }, [focusRequest]);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (inFlight.current) return;
    setAttempted(true);
    setFeedback(undefined);
    const result = purchaseRequestSchema.safeParse(draft);
    if (!result.success) {
      const invalid = validatePurchase(draft);
      const firstInvalid = fields.find((field) => invalid[field.name]);
      if (firstInvalid) setFocusRequest({ field: firstInvalid.name });
      return;
    }
    inFlight.current = true;
    setPending(true);
    try {
      setFeedback({ text: completion(await mutation.mutateAsync(result.data)), failed: false });
    } catch (error) {
      setFeedback({ text: failure(error), failed: true });
    } finally {
      inFlight.current = false;
      setPending(false);
    }
  }
  return (
    <form id="purchase-checker" aria-label="Check a purchase" noValidate onSubmit={submit}>
      <p className="mb-6 text-small text-ink-muted">
        Enter names as free text. All four fields are required.
      </p>
      <div className="grid min-w-0 gap-6 md:grid-cols-2">
        {fields.map((field) => (
          <div key={field.name} className="min-w-0">
            <label htmlFor={`${id}-${field.name}`} className="mb-2 block font-semibold">
              {field.label}
            </label>
            <input
              ref={(element) => {
                inputs.current[field.name] = element;
              }}
              id={`${id}-${field.name}`}
              name={field.name}
              type={field.type}
              required
              autoComplete="off"
              disabled={pending}
              value={draft[field.name]}
              aria-invalid={errors[field.name] ? true : undefined}
              aria-describedby={`${id}-${field.name}-help${errors[field.name] ? ` ${id}-${field.name}-error` : ''}`}
              onChange={(event) => {
                setDraft({ ...draft, [field.name]: event.target.value });
                setFeedback(undefined);
                mutation.reset();
              }}
              className="min-h-12 w-full min-w-0 rounded-control border border-border bg-surface px-3 py-3 text-ink focus-visible:outline-3 focus-visible:outline-offset-4 focus-visible:outline-brand disabled:bg-surface-muted"
            />
            <p id={`${id}-${field.name}-help`} className="mt-2 text-small text-ink-muted">
              {field.help}
            </p>
            {errors[field.name] && (
              <p
                id={`${id}-${field.name}-error`}
                className="mt-2 text-small font-semibold text-ink"
              >
                {errors[field.name]}
              </p>
            )}
          </div>
        ))}
      </div>
      <Button type="submit" disabled={pending} className="mt-8 w-full">
        {pending ? 'Checking…' : 'Find My Benefits'}
      </Button>
      <div role="status" aria-live="polite" className="mt-4 text-small">
        {pending
          ? 'Checking your purchase. Please wait.'
          : feedback && !feedback.failed
            ? feedback.text
            : null}
      </div>
      {feedback?.failed && (
        <p role="alert" className="mt-4 text-small">
          {feedback.text}
        </p>
      )}
    </form>
  );
}

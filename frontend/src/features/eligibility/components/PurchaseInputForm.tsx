'use client';
import { useEffect, useId, useRef, useState, type FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import { usePurchaseCheckSession } from '../session/PurchaseCheckSession';
import { Button } from '@/components/ui/Button';
import { useCheckPurchaseMutation } from '../api/useCheckPurchaseMutation';
import { purchaseRequestSchema } from '@/lib/api/eligibility.contract';
import {
  completion,
  failure,
  fields,
  requestFromDraft,
  validatePurchase,
  type Draft,
  type Field,
} from './purchaseForm';
export { validatePurchase } from './purchaseForm';
export function PurchaseInputForm() {
  const id = useId();
  const router = useRouter();
  const session = usePurchaseCheckSession();
  const [draft, setDraft] = useState<Draft>(session.draft);
  const [attempted, setAttempted] = useState(false);
  const [focusRequest, setFocusRequest] = useState<{ field: Field }>();
  const [feedback, setFeedback] = useState<{ lines: string[]; failed: boolean }>();
  const [pending, setPending] = useState(false);
  const [priceOpen, setPriceOpen] = useState(Boolean(session.draft.purchase_price));
  const inFlight = useRef(false);
  const mounted = useRef(true);
  const revision = useRef(0);
  const inputs = useRef<Partial<Record<Field, HTMLInputElement | null>>>({});
  const mutation = useCheckPurchaseMutation();
  const errors = attempted ? validatePurchase(draft) : {};
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  useEffect(() => {
    if (focusRequest) inputs.current[focusRequest.field]?.focus();
  }, [focusRequest]);
  function edit(field: Field, value: string) {
    revision.current++;
    const next = { ...draft, [field]: value };
    setDraft(next);
    session.edit(next);
    setFeedback(undefined);
    mutation.reset();
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (inFlight.current) return;
    setAttempted(true);
    setFeedback(undefined);
    const invalid = validatePurchase(draft);
    const firstInvalid = [...fields.map((field) => field.name), 'purchase_price' as const].find(
      (field) => invalid[field],
    );
    if (firstInvalid) {
      if (firstInvalid === 'purchase_price') setPriceOpen(true);
      setFocusRequest({ field: firstInvalid });
      return;
    }
    const result = purchaseRequestSchema.safeParse(requestFromDraft(draft));
    if (!result.success) return;
    const submittedRevision = revision.current;
    inFlight.current = true;
    setPending(true);
    try {
      const data = await mutation.mutateAsync(result.data);
      if (mounted.current && submittedRevision === revision.current) {
        session.publish(result.data, data);
        setFeedback({ lines: completion(data), failed: false });
        router.push('/results');
      }
    } catch (error) {
      if (mounted.current && submittedRevision === revision.current)
        setFeedback({ lines: [failure(error)], failed: true });
    } finally {
      inFlight.current = false;
      if (mounted.current) setPending(false);
    }
  }
  const inputClass = (field: Field) =>
    `min-h-12 w-full min-w-0 rounded-control border bg-surface px-4 py-3 text-ink focus-visible:outline-3 focus-visible:outline-offset-4 focus-visible:outline-brand disabled:cursor-not-allowed disabled:bg-surface-muted ${errors[field] ? 'border-red-700 border-2' : 'border-ink-muted'}`;
  return (
    <form id="purchase-checker" aria-label="Check a purchase" noValidate onSubmit={submit}>
      <p className="mb-6 text-small text-ink-muted">
        All four fields marked * are required. Enter names as free text.
      </p>
      <div className="grid min-w-0 gap-x-6 gap-y-4 md:grid-cols-2">
        {fields.map((field) => (
          <div key={field.name} className="min-w-0">
            <div className="mb-2 flex gap-1 font-semibold">
              <label htmlFor={`${id}-${field.name}`}>{field.label}</label>
              <span aria-hidden="true">*</span>
            </div>
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
              onChange={(event) => edit(field.name, event.target.value)}
              className={inputClass(field.name)}
            />
            <div className="mt-2 min-h-14">
              <p id={`${id}-${field.name}-help`} className="text-small text-ink-muted">
                {field.help}
              </p>
              {errors[field.name] && (
                <p
                  id={`${id}-${field.name}-error`}
                  className="mt-1 text-small font-semibold text-red-800"
                >
                  {errors[field.name]}
                </p>
              )}
            </div>
          </div>
        ))}
      </div>
      <details
        open={priceOpen}
        onToggle={(event) => setPriceOpen(event.currentTarget.open)}
        className="mt-4 border-t border-border pt-5"
      >
        <summary className="w-fit max-w-full cursor-pointer rounded-control py-2 font-semibold text-brand">
          Add optional purchase price
        </summary>
        <div className="mt-4 min-w-0 md:max-w-[calc(50%-0.75rem)]">
          <label htmlFor={`${id}-purchase_price`} className="mb-2 block font-semibold">
            Purchase price (GBP)
          </label>
          <input
            ref={(element) => {
              inputs.current.purchase_price = element;
            }}
            id={`${id}-purchase_price`}
            name="purchase_price"
            type="text"
            inputMode="decimal"
            autoComplete="off"
            value={draft.purchase_price ?? ''}
            disabled={pending}
            aria-invalid={errors.purchase_price ? true : undefined}
            aria-describedby={`${id}-price-help${errors.purchase_price ? ` ${id}-price-error` : ''}`}
            onChange={(event) => edit('purchase_price', event.target.value)}
            className={inputClass('purchase_price')}
          />
          <p id={`${id}-price-help`} className="mt-2 text-small text-ink-muted">
            Optional. Enter pounds and pence, for example 799.99, without £ signs or commas.
          </p>
          {errors.purchase_price && (
            <p id={`${id}-price-error`} className="mt-1 text-small font-semibold text-red-800">
              {errors.purchase_price}
            </p>
          )}
        </div>
      </details>
      <div className="mt-8 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <p className="text-small text-ink-muted">
          No account required.
          <br />
          Checked against published promotion data.
        </p>
        <Button
          type="submit"
          disabled={pending}
          aria-busy={pending}
          className="min-h-12 w-full enabled:hover:bg-brand md:w-auto"
        >
          {pending ? 'Checking…' : 'Find My Benefits'}
        </Button>
      </div>
      {attempted && Object.keys(errors).length > 0 && (
        <p role="alert" className="mt-4 text-small font-semibold text-red-800">
          Check the highlighted fields and try again.
        </p>
      )}
      <div role="status" aria-live="polite" aria-atomic="true" className="mt-4 min-h-6 text-small">
        {pending
          ? 'Checking your purchase…'
          : feedback && !feedback.failed
            ? feedback.lines.map((line) => (
                <span key={line} className="mt-2 block">
                  {line}
                </span>
              ))
            : null}
      </div>
      {feedback?.failed && (
        <p role="alert" className="mt-4 text-small">
          {feedback.lines[0]}
        </p>
      )}
    </form>
  );
}

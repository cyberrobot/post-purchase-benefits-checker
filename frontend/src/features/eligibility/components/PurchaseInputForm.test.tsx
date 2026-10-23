import {
  PurchaseCheckSessionProvider,
  usePurchaseCheckSession,
} from '../session/PurchaseCheckSession';
import type { ReactNode } from 'react';
import { useRouter } from 'next/navigation';
import { act, fireEvent, render as rtlRender, screen, waitFor } from '@testing-library/react';
import { PurchaseInputForm, validatePurchase } from './PurchaseInputForm';
import { useCheckPurchaseMutation } from '../api/useCheckPurchaseMutation';
import { ApiError, type ApiErrorKind } from '@/lib/api/errors';
import { resolved, unresolved } from '@/lib/api/fixtures';
import { populatedClaim } from '@/lib/api/promotion.fixture';
import { checkPurchaseResponseSchema } from '@/lib/api/eligibility.contract';
jest.mock('../api/useCheckPurchaseMutation');
jest.mock('next/navigation');
const push = jest.fn();
const replace = jest.fn();
function render(ui: ReactNode) {
  return rtlRender(ui, { wrapper: PurchaseCheckSessionProvider });
}
const mutateAsync = jest.fn();
const reset = jest.fn();
const draft = {
  brand: 'Example',
  model: ' SKU /-1 ',
  retailer: 'Shop',
  purchase_date: '2024-02-29',
};
const labels = ['Manufacturer / Brand', 'Product model or SKU', 'Retailer', 'Purchase date'];
function fill() {
  labels.forEach((label, index) =>
    fireEvent.change(screen.getByLabelText(label), {
      target: { value: Object.values(draft)[index] },
    }),
  );
}
function submit() {
  fireEvent.submit(screen.getByRole('form'));
}
beforeEach(() => {
  jest.clearAllMocks();
  jest
    .mocked(useRouter)
    .mockReturnValue({ push, replace } as unknown as ReturnType<typeof useRouter>);
  jest
    .mocked(useCheckPurchaseMutation)
    .mockReturnValue({ mutateAsync, reset } as unknown as ReturnType<
      typeof useCheckPurchaseMutation
    >);
  mutateAsync.mockResolvedValue(resolved);
});
it('starts empty with four labelled required controls in order and no automatic requests', () => {
  const { container, rerender } = render(<PurchaseInputForm />);
  expect(
    Array.from(container.querySelectorAll<HTMLInputElement>('input[required]')).map(
      (input) => input.name,
    ),
  ).toEqual(Object.keys(draft));
  labels.forEach((label) => {
    const input = screen.getByLabelText(label);
    expect(input).toHaveValue('');
    expect(input).toBeRequired();
    expect(input).toHaveAccessibleDescription();
    expect(input).not.toHaveAttribute('aria-invalid');
  });
  expect(screen.getByRole('button')).toHaveAttribute('type', 'submit');
  rerender(<PurchaseInputForm />);
  fill();
  fireEvent.focus(screen.getByLabelText('Retailer'));
  expect(mutateAsync).not.toHaveBeenCalled();
});
it('focuses and describes invalid fields, updates errors on correction and blocks requests', () => {
  render(<PurchaseInputForm />);
  submit();
  const input = screen.getByLabelText('Manufacturer / Brand');
  expect(input).toHaveFocus();
  expect(input).toHaveAttribute('aria-invalid', 'true');
  expect(input).toHaveAccessibleDescription(/Enter the manufacturer \/ brand/);
  fireEvent.change(input, { target: { value: 'Example' } });
  expect(input).not.toHaveAttribute('aria-invalid');
  expect(mutateAsync).not.toHaveBeenCalled();
});
it('commits error descriptions before focusing on every invalid submission', async () => {
  render(<PurchaseInputForm />);
  const observations: { label: string; invalid: string | null; error: string | null }[] = [];
  const controls = labels.map((label) => screen.getByLabelText(label));
  controls.forEach((control, index) => {
    control.addEventListener('focus', () => {
      const errorId = control
        .getAttribute('aria-describedby')
        ?.split(' ')
        .find((id) => id.endsWith('-error'));
      observations.push({
        label: labels[index],
        invalid: control.getAttribute('aria-invalid'),
        error: errorId ? (document.getElementById(errorId)?.textContent ?? null) : null,
      });
    });
  });
  const button = screen.getByRole('button');
  const expectInvalidFocus = (label: string, error: string) => {
    button.focus();
    submit();
    expect(observations.at(-1)).toEqual({ label, invalid: 'true', error });
    expect(screen.getByLabelText(label)).toHaveFocus();
    expect(mutateAsync).not.toHaveBeenCalled();
  };
  expectInvalidFocus('Manufacturer / Brand', 'Enter the manufacturer / brand');
  expectInvalidFocus('Manufacturer / Brand', 'Enter the manufacturer / brand');
  labels.forEach((label, index) => {
    fireEvent.change(controls[index], { target: { value: Object.values(draft)[index] } });
    if (index < labels.length - 1) {
      const next = labels[index + 1];
      expectInvalidFocus(
        next,
        next === 'Purchase date'
          ? 'Enter a valid purchase date'
          : `Enter the ${next.toLowerCase()}`,
      );
    }
  });
  expect(observations.map(({ label }) => label)).toEqual([
    'Manufacturer / Brand',
    'Manufacturer / Brand',
    'Product model or SKU',
    'Retailer',
    'Purchase date',
  ]);
  button.focus();
  const focusCount = observations.length;
  submit();
  await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('No matching'));
  expect(mutateAsync).toHaveBeenCalledTimes(1);
  expect(observations).toHaveLength(focusCount);
  expect(button).toHaveFocus();
});
it.each([' ', 'x'.repeat(256), 'bad\u0001value'])('blocks invalid identity %p', (brand) => {
  render(<PurchaseInputForm />);
  fill();
  fireEvent.change(screen.getByLabelText('Manufacturer / Brand'), { target: { value: brand } });
  submit();
  expect(mutateAsync).not.toHaveBeenCalled();
  expect(screen.getByLabelText('Manufacturer / Brand')).toHaveAttribute('aria-invalid', 'true');
});
it.each(['2026-02-29', '2024-04-31', 'not-a-date', '2024-2-29', ''])(
  'rejects invalid date %p',
  (purchase_date) => {
    expect(validatePurchase({ ...draft, purchase_date })).toEqual({
      purchase_date: 'Enter a valid purchase date',
    });
  },
);
it.each(['2024-02-29', '1900-01-01'])(
  'accepts historical real calendar date %p',
  (purchase_date) => {
    expect(validatePurchase({ ...draft, purchase_date })).toEqual({});
  },
);
it('blocks invalid date in rendered form', () => {
  render(<PurchaseInputForm />);
  fill();
  fireEvent.change(screen.getByLabelText('Purchase date'), { target: { value: '2026-02-29' } });
  submit();
  expect(mutateAsync).not.toHaveBeenCalled();
  expect(screen.getByLabelText('Purchase date')).toHaveFocus();
});
it('submits exact raw keys once, locks fields while pending, clears stale results and permits resubmit', async () => {
  let complete!: (value: unknown) => void;
  mutateAsync.mockReturnValueOnce(
    new Promise((resolve) => {
      complete = resolve;
    }),
  );
  render(<PurchaseInputForm />);
  fill();
  submit();
  submit();
  expect(mutateAsync).toHaveBeenCalledTimes(1);
  expect(mutateAsync).toHaveBeenCalledWith(draft);
  labels.forEach((label) => expect(screen.getByLabelText(label)).toBeDisabled());
  expect(screen.getByRole('status')).toHaveTextContent('Checking your purchase');
  expect(screen.getByRole('button')).toBeDisabled();
  await act(async () => complete(resolved));
  expect(screen.getByRole('status')).toHaveTextContent('No matching published promotion');
  expect(push).toHaveBeenCalledWith('/results');
  expect(push).toHaveBeenCalledTimes(1);
  expect(screen.getByLabelText('Product model or SKU')).toHaveValue(draft.model);
  fireEvent.click(screen.getByRole('button', { name: 'Return to purchase form' }));
  expect(replace).toHaveBeenCalledWith('/check');
  fireEvent.change(screen.getByLabelText('Product model or SKU'), {
    target: { value: 'corrected' },
  });
  expect(screen.getByRole('status')).toBeEmptyDOMElement();
  expect(reset).toHaveBeenCalled();
  expect(mutateAsync).toHaveBeenCalledTimes(1);
  submit();
  await waitFor(() => expect(mutateAsync).toHaveBeenCalledTimes(2));
});
it.each(['not_found', 'ambiguous'])(
  'guides unresolved %s correction without UUIDs',
  async (status) => {
    mutateAsync.mockResolvedValue({
      ...unresolved,
      unresolved_identity: {
        field: 'model',
        status,
        candidate_ids: ['00000000-0000-0000-0000-000000000009'],
      },
    });
    render(<PurchaseInputForm />);
    fill();
    submit();
    await waitFor(() =>
      expect(screen.getByRole('status')).toHaveTextContent(
        status === 'ambiguous'
          ? 'More than one product model or sku matched'
          : 'product model or sku could not be found',
      ),
    );
    expect(screen.getByRole('status')).toHaveTextContent('try again');
    expect(screen.queryByText(/00000000/)).not.toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  },
);
it('counts NOT_ELIGIBLE records without promising benefits', async () => {
  if (populatedClaim.outcome !== 'resolved') throw new Error('fixture');
  const promotion = {
    ...populatedClaim.promotions[0],
    eligibility: {
      classification: 'NOT_ELIGIBLE',
      reasons: [{ code: 'purchase_date_before_start', rule_kind: 'purchase_date' }],
      rule_evaluations: [
        {
          kind: 'purchase_date',
          status: 'not_satisfied',
          reason_code: 'purchase_date_before_start',
        },
      ],
      claim_window_status: 'open',
    },
    explanation: ['The purchase date is before the recorded purchase period.'],
  };
  mutateAsync.mockResolvedValue({
    ...populatedClaim,
    promotions: [
      promotion,
      { ...promotion, promotion_variant_id: '00000000-0000-0000-0000-000000000010' },
    ],
  });
  render(<PurchaseInputForm />);
  fill();
  submit();
  await waitFor(() =>
    expect(screen.getByRole('status')).toHaveTextContent(
      '2 promotion matches: does not meet recorded rules.',
    ),
  );
  expect(screen.getByRole('status')).not.toHaveTextContent(/cashback|claimable|qualify|£/i);
});
it.each<[ApiErrorKind, string]>([
  ['validation', 'against your receipt'],
  ['rate_limited', 'wait before trying again'],
  ['unavailable', 'temporarily unavailable'],
  ['timeout', 'took too long'],
  ['cancelled', 'cancelled'],
  ['server', 'service problem'],
  ['contract', 'service problem'],
])('handles %s safely and allows manual retry', async (kind, message) => {
  mutateAsync.mockRejectedValueOnce(new ApiError(kind));
  render(<PurchaseInputForm />);
  fill();
  submit();
  expect(await screen.findByRole('alert')).toHaveTextContent(message);
  expect(screen.getByRole('status')).toBeEmptyDOMElement();
  expect(screen.getByLabelText('Product model or SKU')).toHaveValue(draft.model);
  expect(mutateAsync).toHaveBeenCalledTimes(1);
  fireEvent.change(screen.getByLabelText('Product model or SKU'), {
    target: { value: 'corrected' },
  });
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  submit();
  await waitFor(() =>
    expect(screen.getByRole('status')).toHaveTextContent('No matching published promotion'),
  );
  expect(mutateAsync).toHaveBeenCalledTimes(2);
});
it.each<[number, string]>([
  [15, '15 seconds'],
  [86400, '24 hours'],
  [Infinity, 'wait before'],
  [-1, 'wait before'],
])('bounds retry guidance %p', async (seconds, message) => {
  mutateAsync.mockRejectedValue(new ApiError('rate_limited', 429, undefined, undefined, seconds));
  render(<PurchaseInputForm />);
  fill();
  submit();
  expect(await screen.findByRole('alert')).toHaveTextContent(message);
});
it('discloses optional price, validates it and sends the exact fifth string key only when entered', async () => {
  render(<PurchaseInputForm />);
  fill();
  const disclosure = screen.getByText('Add optional purchase price');
  expect(disclosure.closest('details')).not.toHaveAttribute('open');
  fireEvent.click(disclosure);
  const price = screen.getByLabelText('Purchase price (GBP)');
  fireEvent.change(price, { target: { value: '£799.99' } });
  submit();
  expect(price).toHaveFocus();
  expect(price).toHaveAttribute('aria-invalid', 'true');
  expect(price).toHaveAccessibleDescription(/GBP amount/);
  expect(mutateAsync).not.toHaveBeenCalled();
  fireEvent.change(price, { target: { value: '799.99' } });
  expect(price).not.toHaveAttribute('aria-invalid');
  submit();
  await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('No matching'));
  expect(mutateAsync).toHaveBeenCalledWith({ ...draft, purchase_price: '799.99' });
  fireEvent.click(screen.getByRole('button', { name: 'Return to purchase form' }));
  expect(replace).toHaveBeenCalledWith('/check');
  fireEvent.change(price, { target: { value: '' } });
  expect(screen.getByRole('status')).toBeEmptyDOMElement();
  submit();
  await waitFor(() => expect(mutateAsync).toHaveBeenCalledTimes(2));
  expect(mutateAsync).toHaveBeenLastCalledWith(draft);
});
it('does not present a late result after a draft revision or unmount', async () => {
  let complete!: (value: unknown) => void;
  mutateAsync.mockReturnValueOnce(
    new Promise((resolve) => {
      complete = resolve;
    }),
  );
  const { unmount } = render(<PurchaseInputForm />);
  fill();
  submit();
  // Programmatic edits also invalidate an already submitted snapshot.
  fireEvent.change(screen.getByLabelText('Product model or SKU'), {
    target: { value: 'corrected' },
  });
  await act(async () => complete(resolved));
  expect(screen.getByRole('status')).toBeEmptyDOMElement();
  expect(push).not.toHaveBeenCalled();
  mutateAsync.mockReturnValueOnce(
    new Promise((resolve) => {
      complete = resolve;
    }),
  );
  submit();
  unmount();
  await act(async () => complete(resolved));
  expect(screen.queryByRole('status')).not.toBeInTheDocument();
});
it('retains values and permits manual retry without requiring edits', async () => {
  mutateAsync.mockRejectedValueOnce(new ApiError('timeout'));
  render(<PurchaseInputForm />);
  fill();
  submit();
  expect(await screen.findByRole('alert')).toHaveTextContent('incomplete');
  expect(screen.getByLabelText('Product model or SKU')).toHaveValue(draft.model);
  submit();
  await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('No matching'));
  expect(mutateAsync).toHaveBeenCalledTimes(2);
});

it('publishes the exact matching submitted snapshot and invalidates it on an edit', async () => {
  function Probe() {
    const { snapshot } = usePurchaseCheckSession();
    return <output data-testid="snapshot">{JSON.stringify(snapshot)}</output>;
  }
  render(
    <>
      <PurchaseInputForm />
      <Probe />
    </>,
  );
  fill();
  submit();
  await waitFor(() => expect(push).toHaveBeenCalledTimes(1));
  expect(JSON.parse(screen.getByTestId('snapshot').textContent!)).toEqual({
    submittedPurchase: draft,
    response: resolved,
  });
  fireEvent.click(screen.getByRole('button', { name: 'Return to purchase form' }));
  expect(replace).toHaveBeenCalledWith('/check');
  fireEvent.change(screen.getByLabelText('Retailer'), { target: { value: 'Another shop' } });
  expect(screen.getByTestId('snapshot')).toHaveTextContent('null');
  expect(mutateAsync).toHaveBeenCalledTimes(1);
});

it('supersedes pending navigation, invalidates its snapshot and publishes only an explicit retry', async () => {
  function Probe() {
    return (
      <output data-testid="snapshot">{JSON.stringify(usePurchaseCheckSession().snapshot)}</output>
    );
  }
  render(
    <>
      <PurchaseInputForm />
      <Probe />
    </>,
  );
  fill();
  submit();
  await waitFor(() => expect(push).toHaveBeenCalledTimes(1));
  fireEvent.click(screen.getByRole('button', { name: 'Return to purchase form' }));
  expect(replace).toHaveBeenCalledWith('/check');
  expect(screen.getByTestId('snapshot')).toHaveTextContent('null');
  expect(screen.getByLabelText('Retailer')).toHaveValue(draft.retailer);
  expect(screen.getByLabelText('Retailer')).toBeEnabled();
  expect(mutateAsync).toHaveBeenCalledTimes(1);
  mutateAsync.mockResolvedValueOnce(unresolved);
  submit();
  await waitFor(() => expect(push).toHaveBeenCalledTimes(2));
  expect(mutateAsync).toHaveBeenCalledTimes(2);
  expect(JSON.parse(screen.getByTestId('snapshot').textContent!).response).toEqual(unresolved);
});

it('keeps submission locked if recovery navigation throws and permits another recovery attempt', async () => {
  replace.mockImplementationOnce(() => {
    throw new Error('Navigation unavailable');
  });
  render(<PurchaseInputForm />);
  fill();
  submit();
  await waitFor(() => expect(push).toHaveBeenCalledTimes(1));
  fireEvent.click(screen.getByRole('button', { name: 'Return to purchase form' }));
  expect(screen.getByRole('alert')).toBeVisible();
  expect(screen.getByLabelText('Retailer')).toBeDisabled();
  submit();
  expect(mutateAsync).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole('button', { name: 'Return to purchase form' }));
  expect(screen.getByLabelText('Retailer')).toBeEnabled();
  expect(replace).toHaveBeenCalledTimes(2);
});

it('blocks click and Enter submissions after API success while navigation is delayed', async () => {
  const { unmount } = render(<PurchaseInputForm />);
  fill();
  submit();
  await waitFor(() => expect(push).toHaveBeenCalledTimes(1));
  const button = screen.getByRole('button', { name: 'Checking…' });
  expect(button).toBeDisabled();
  fireEvent.click(button);
  fireEvent.keyDown(screen.getByLabelText('Retailer'), { key: 'Enter' });
  submit();
  expect(mutateAsync).toHaveBeenCalledTimes(1);
  expect(push).toHaveBeenCalledTimes(1);
  labels.forEach((label) => expect(screen.getByLabelText(label)).toBeDisabled());
  unmount();
  render(<PurchaseInputForm />);
  expect(screen.getByRole('button', { name: 'Find My Benefits' })).toBeEnabled();
});
it('recovers from a synchronous navigation failure and allows unchanged manual retry', async () => {
  push.mockImplementationOnce(() => {
    throw new Error('Navigation unavailable');
  });
  render(<PurchaseInputForm />);
  fill();
  submit();
  await screen.findByRole('alert');
  expect(screen.getByRole('button', { name: 'Find My Benefits' })).toBeEnabled();
  expect(screen.getByLabelText('Product model or SKU')).toHaveValue(draft.model);
  submit();
  await waitFor(() => expect(push).toHaveBeenCalledTimes(2));
  expect(mutateAsync).toHaveBeenCalledTimes(2);
});
it('invalidates an earlier snapshot on unchanged validated submission and retains the draft on failure', async () => {
  function Probe() {
    const session = usePurchaseCheckSession();
    return (
      <>
        <button onClick={() => session.publish(draft, checkPurchaseResponseSchema.parse(resolved))}>
          Seed earlier result
        </button>
        <output data-testid="snapshot">{JSON.stringify(session.snapshot)}</output>
      </>
    );
  }
  render(
    <>
      <PurchaseInputForm />
      <Probe />
    </>,
  );
  fill();
  fireEvent.click(screen.getByRole('button', { name: 'Seed earlier result' }));
  expect(screen.getByTestId('snapshot')).not.toHaveTextContent('null');
  let fail!: (error: Error) => void;
  mutateAsync.mockReturnValueOnce(
    new Promise((_, reject) => {
      fail = reject;
    }),
  );
  submit();
  expect(screen.getByTestId('snapshot')).toHaveTextContent('null');
  await act(async () => fail(new ApiError('unavailable')));
  expect(screen.getByTestId('snapshot')).toHaveTextContent('null');
  expect(push).not.toHaveBeenCalled();
  labels.forEach((label, index) =>
    expect(screen.getByLabelText(label)).toHaveValue(Object.values(draft)[index]),
  );
  submit();
  await waitFor(() => expect(push).toHaveBeenCalledTimes(1));
  expect(screen.getByTestId('snapshot')).not.toHaveTextContent('null');
  expect(mutateAsync).toHaveBeenCalledTimes(2);
});

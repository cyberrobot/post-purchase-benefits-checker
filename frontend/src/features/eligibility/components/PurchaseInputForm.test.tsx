import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { PurchaseInputForm, validatePurchase } from './PurchaseInputForm';
import { useCheckPurchaseMutation } from '../api/useCheckPurchaseMutation';
import { ApiError, type ApiErrorKind } from '@/lib/api/errors';
import { resolved, unresolved } from '@/lib/api/fixtures';
import { populatedClaim } from '@/lib/api/promotion.fixture';
jest.mock('../api/useCheckPurchaseMutation');
const mutateAsync = jest.fn();
const reset = jest.fn();
const draft = {
  brand: 'Example',
  model: ' SKU /-1 ',
  retailer: 'Shop',
  purchase_date: '2024-02-29',
};
const labels = ['Manufacturer', 'Model number', 'Retailer', 'Purchase date'];
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
    .mocked(useCheckPurchaseMutation)
    .mockReturnValue({ mutateAsync, reset } as unknown as ReturnType<
      typeof useCheckPurchaseMutation
    >);
  mutateAsync.mockResolvedValue(resolved);
});
it('starts empty with four labelled required controls in order and no automatic requests', () => {
  const { container, rerender } = render(<PurchaseInputForm />);
  expect(Array.from(container.querySelectorAll('input')).map((input) => input.name)).toEqual(
    Object.keys(draft),
  );
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
  const input = screen.getByLabelText('Manufacturer');
  expect(input).toHaveFocus();
  expect(input).toHaveAttribute('aria-invalid', 'true');
  expect(input).toHaveAccessibleDescription(/Enter the manufacturer/);
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
  expectInvalidFocus('Manufacturer', 'Enter the manufacturer');
  expectInvalidFocus('Manufacturer', 'Enter the manufacturer');
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
    'Manufacturer',
    'Manufacturer',
    'Model number',
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
  fireEvent.change(screen.getByLabelText('Manufacturer'), { target: { value: brand } });
  submit();
  expect(mutateAsync).not.toHaveBeenCalled();
  expect(screen.getByLabelText('Manufacturer')).toHaveAttribute('aria-invalid', 'true');
});
it.each(['2026-02-29', '2024-04-31', 'not-a-date', '2024-2-29', ''])(
  'rejects invalid date %p',
  (purchase_date) => {
    expect(validatePurchase({ ...draft, purchase_date })).toEqual({
      purchase_date: 'Enter a valid purchase date',
    });
  },
);
it.each(['2024-02-29', '1900-01-01', '9999-12-31'])(
  'accepts calendar date without new date policy %p',
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
  expect(screen.getByLabelText('Model number')).toHaveValue(draft.model);
  fireEvent.change(screen.getByLabelText('Model number'), { target: { value: 'corrected' } });
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
          ? 'More than one model number matched'
          : 'model number could not be found',
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
    eligibility: { ...populatedClaim.promotions[0].eligibility, classification: 'NOT_ELIGIBLE' },
  };
  mutateAsync.mockResolvedValue({ ...populatedClaim, promotions: [promotion, promotion] });
  render(<PurchaseInputForm />);
  fill();
  submit();
  await waitFor(() =>
    expect(screen.getByRole('status')).toHaveTextContent(
      '2 promotion records requiring eligibility review. Detailed results are not yet shown.',
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
  expect(screen.getByLabelText('Model number')).toHaveValue(draft.model);
  expect(mutateAsync).toHaveBeenCalledTimes(1);
  fireEvent.change(screen.getByLabelText('Model number'), { target: { value: 'corrected' } });
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

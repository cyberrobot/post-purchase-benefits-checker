import { fireEvent, render, screen } from '@testing-library/react';
import { id } from '@/lib/api/promotion-details.fixture';
import { ClaimChecklist } from './ClaimChecklist';

const labels = [
  ['receipt', 'Receipt'],
  ['serial_number', 'Serial number'],
  ['registration', 'Registration'],
  ['invoice', 'Invoice'],
  ['barcode', 'Barcode'],
  ['imei', 'IMEI'],
  ['installation_evidence', 'Installation evidence'],
] as const;

it('renders every recorded requirement in source order with optional plain text descriptions', () => {
  const description = '<b>Keep the original.</b>';
  const { container } = render(
    <ClaimChecklist
      requirements={labels.map(([requirement_type], index) => ({
        requirement_type,
        requirement_id: id(index),
        description: index === 0 ? description : null,
      }))}
    />,
  );
  const inputs = screen.getAllByRole('checkbox');
  labels.forEach(([, label], index) => {
    expect(inputs[index]).toHaveAccessibleName(label);
    expect(inputs[index]).not.toBeChecked();
  });
  expect(inputs[0]).toHaveAccessibleDescription(description);
  expect(container.querySelector('b')).toBeNull();
  expect(screen.getByRole('status')).toHaveTextContent('0 of 7 items marked ready.');
});

it('tracks duplicate types independently, reverses progress and resets when the variant changes', () => {
  const requirements = [
    { requirement_id: id(1), requirement_type: 'receipt', description: null },
    { requirement_id: id(2), requirement_type: 'receipt', description: null },
  ] as const;
  const storage = jest.spyOn(Storage.prototype, 'setItem');
  const cookieBefore = document.cookie;
  try {
    const { rerender } = render(<ClaimChecklist key="first" requirements={[...requirements]} />);
    const [first, second] = screen.getAllByRole('checkbox', { name: 'Receipt' });
    expect(first.id).not.toBe(second.id);
    fireEvent.click(first);
    expect(first).toBeChecked();
    expect(second).not.toBeChecked();
    expect(screen.getByRole('status')).toHaveTextContent('1 of 2 items marked ready.');
    fireEvent.click(second);
    expect(screen.getByRole('status')).toHaveTextContent('All recorded items marked ready.');
    fireEvent.click(first);
    expect(screen.getByRole('status')).toHaveTextContent('1 of 2 items marked ready.');
    expect(screen.queryByText('All recorded items marked ready.')).not.toBeInTheDocument();
    rerender(<ClaimChecklist key="second" requirements={[...requirements]} />);
    expect(screen.getByRole('status')).toHaveTextContent('0 of 2 items marked ready.');
    expect(storage).not.toHaveBeenCalled();
    expect(document.cookie).toBe(cookieBefore);
  } finally {
    storage.mockRestore();
  }
});

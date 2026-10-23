import { fireEvent, render, screen } from '@testing-library/react';
import { populatedClaim } from '@/lib/api/promotion.fixture';
import { resolved as rawResolved } from '@/lib/api/fixtures';
import { PurchaseCheckSessionProvider, usePurchaseCheckSession } from './PurchaseCheckSession';
import { checkPurchaseResponseSchema } from '@/lib/api/eligibility.contract';
const resolved = checkPurchaseResponseSchema.parse(rawResolved);
const purchase = { brand: 'Brand', model: 'Model', retailer: 'Shop', purchase_date: '2024-01-01' };
it('copies and freezes snapshots, replaces results, invalidates on edits and loses state on remount', () => {
  function Probe() {
    const session = usePurchaseCheckSession();
    return (
      <>
        <button onClick={() => session.publish(purchase, populatedClaim)}>Publish</button>
        <button onClick={() => session.publish(purchase, resolved)}>Replace</button>
        <button onClick={() => session.edit({ ...purchase, model: 'Edited' })}>Edit</button>
        <output>
          {session.snapshot
            ? session.snapshot.response.outcome === 'resolved'
              ? session.snapshot.response.promotions.length
              : 'unresolved'
            : 'empty'}
        </output>
        <span>{session.draft.model}</span>
        <span>{String(session.snapshot ? Object.isFrozen(session.snapshot.response) : false)}</span>
      </>
    );
  }
  const { unmount } = render(
    <PurchaseCheckSessionProvider>
      <Probe />
    </PurchaseCheckSessionProvider>,
  );
  fireEvent.click(screen.getByText('Publish'));
  expect(screen.getByRole('status')).toHaveTextContent('1');
  expect(screen.getByText('true')).toBeVisible();
  fireEvent.click(screen.getByText('Replace'));
  expect(screen.getByRole('status')).toHaveTextContent('0');
  fireEvent.click(screen.getByText('Edit'));
  expect(screen.getByRole('status')).toHaveTextContent('empty');
  expect(screen.getByText('Edited')).toBeVisible();
  unmount();
  render(
    <PurchaseCheckSessionProvider>
      <Probe />
    </PurchaseCheckSessionProvider>,
  );
  expect(screen.getByRole('status')).toHaveTextContent('empty');
  expect(screen.queryByText('Edited')).not.toBeInTheDocument();
});

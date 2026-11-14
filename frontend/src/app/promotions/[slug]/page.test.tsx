import { fireEvent, render, screen } from '@testing-library/react';
import PromotionPage from './page';
import PromotionError from './error';
import { getPromotionDetails } from '@/lib/api/promotion-details.server';
import { recordedTerms } from '@/lib/api/promotion-details.fixture';
import { ApiError } from '@/lib/api/errors';

jest.mock('@/lib/api/promotion-details.server', () => ({ getPromotionDetails: jest.fn() }));
const refresh = jest.fn();
jest.mock('next/navigation', () => ({
  useRouter: () => ({ refresh }),
  notFound: () => {
    throw new Error('not found');
  },
}));
const read = jest.mocked(getPromotionDetails);
const params = Promise.resolve({ slug: recordedTerms.public_slug });

it('renders public details without a purchase session or extra fetch', async () => {
  read.mockResolvedValueOnce(recordedTerms);
  render(await PromotionPage({ params }));
  expect(read).toHaveBeenLastCalledWith(recordedTerms.public_slug);
  expect(read).toHaveBeenCalledTimes(1);
  expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(recordedTerms.name);
});

it('uses the route 404 for unknown and hidden records', async () => {
  read.mockResolvedValueOnce(null);
  await expect(PromotionPage({ params })).rejects.toThrow('not found');
});

it.each(['unavailable', 'contract'] as const)(
  'uses the recoverable error boundary for %s failures',
  async (kind) => {
    const log = jest.spyOn(console, 'warn').mockImplementation(() => {});
    try {
      read.mockRejectedValueOnce(new ApiError(kind));
      await expect(PromotionPage({ params })).rejects.toThrow(
        'Unable to load published promotion details',
      );
      expect(log).toHaveBeenCalledWith('promotion_details_read_failed', {
        category: kind,
        requestId: undefined,
      });
      const reset = jest.fn();
      render(<PromotionError reset={reset} />);
      fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
      expect(reset).toHaveBeenCalledTimes(1);
      expect(refresh).toHaveBeenCalled();
    } finally {
      log.mockRestore();
    }
  },
);

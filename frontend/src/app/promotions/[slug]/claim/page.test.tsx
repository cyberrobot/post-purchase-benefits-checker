import { fireEvent, render, screen } from '@testing-library/react';
import { ApiError } from '@/lib/api/errors';
import { id, recordedTerms } from '@/lib/api/promotion-details.fixture';
import { getPromotionDetails } from '@/lib/api/promotion-details.server';
import PromotionError from '../error';
import ClaimPage from './page';

jest.mock('@/lib/api/promotion-details.server', () => ({ getPromotionDetails: jest.fn() }));
const refresh = jest.fn();
jest.mock('next/navigation', () => ({
  useRouter: () => ({ refresh }),
  notFound: () => {
    throw new Error('not found');
  },
}));
const read = jest.mocked(getPromotionDetails);
const [first, second] = recordedTerms.variants;
function page(variant?: string | string[], slug = recordedTerms.public_slug) {
  return ClaimPage({
    params: Promise.resolve({ slug }),
    searchParams: Promise.resolve({ variant }),
  });
}

beforeEach(() => jest.clearAllMocks());

it('reads the published promotion once and automatically selects its sole variant', async () => {
  read.mockResolvedValueOnce({ ...recordedTerms, variants: [first] });
  render(await page());
  expect(read).toHaveBeenCalledTimes(1);
  expect(read).toHaveBeenCalledWith(recordedTerms.public_slug);
  expect(screen.getByRole('heading', { level: 1, name: 'Prepare your claim' })).toBeVisible();
  expect(screen.getByRole('checkbox', { name: 'Receipt' })).not.toBeChecked();
  expect(screen.getByRole('checkbox', { name: 'Receipt' })).toHaveAccessibleDescription(
    'Keep your receipt.',
  );
  expect(screen.queryByRole('navigation', { name: 'Promotion variants' })).not.toBeInTheDocument();
  expect(screen.getByText(/At least 14 days after purchase/)).toBeVisible();
  expect(screen.getByText(/Last official source verified/)).toBeVisible();
  for (const [name, href] of [
    [/Open official claim site.*opens in a new tab/, recordedTerms.provenance.claim_url],
    [/Read official terms.*opens in a new tab/, recordedTerms.provenance.official_source_url],
  ] as const) {
    const link = screen.getByRole('link', { name });
    expect(link).toHaveAttribute('href', href);
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    expect(link).toHaveAttribute('target', '_blank');
  }
});

it('shows an explicit chooser without an applicable checklist', async () => {
  read.mockResolvedValueOnce(recordedTerms);
  render(await page());
  expect(screen.getByText('Choose a promotion variant to see its requirements.')).toBeVisible();
  expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
  expect(
    screen.getByRole('link', { name: /Base offer.*Example Retailer.*TV-100/ }),
  ).toHaveAttribute(
    'href',
    '/promotions/' + recordedTerms.public_slug + '/claim?variant=' + first.promotion_variant_id,
  );
});

it('disambiguates variants whose rendered names, retailer and model otherwise collide', async () => {
  const collidingVariants = [
    { ...first, name: 'Base', code: 'retail' },
    {
      ...second,
      name: null,
      code: 'Base (variant code: retail)',
      retailer: first.retailer,
    },
  ];
  read.mockResolvedValueOnce({ ...recordedTerms, variants: collidingVariants });
  render(await page());

  const links = screen
    .getAllByRole('link')
    .filter((link) => link.getAttribute('href')?.includes('/claim?variant='));
  expect(links).toHaveLength(2);
  const names = links.map((link) => link.getAttribute('aria-label') ?? link.textContent);
  expect(new Set(names).size).toBe(2);
  expect(names[0]).toContain(first.promotion_variant_id);
  expect(names[1]).toContain(second.promotion_variant_id);
});

it('isolates the selected variant and shows no progress for an empty checklist', async () => {
  read.mockResolvedValueOnce({ ...recordedTerms, status: 'expired', claim_window: null });
  render(await page(second.promotion_variant_id));
  expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
  expect(screen.queryByRole('status')).not.toBeInTheDocument();
  expect(screen.getByText(/No claim requirements are recorded for this variant/)).toBeVisible();
  expect(screen.getByText(/Recorded as expired/)).toBeVisible();
  expect(screen.getByText(/Claim timing not recorded/)).toBeVisible();
  expect(screen.getByRole('link', { name: /special.*selected/ })).toHaveAttribute(
    'aria-current',
    'page',
  );
  expect(screen.getByRole('link', { name: 'Back to promotion details' })).toHaveAttribute(
    'href',
    '/promotions/' + recordedTerms.public_slug + '#variant-' + second.promotion_variant_id,
  );
  expect(screen.getByRole('link', { name: /Open official claim site/ })).toBeVisible();
});

it.each([
  { variant: 'bad' },
  { variant: '' },
  { variant: id(100) },
  { variant: [first.promotion_variant_id, first.promotion_variant_id] },
])('rejects unsupported variant query %j', async ({ variant }) => {
  read.mockResolvedValueOnce(recordedTerms);
  await expect(page(variant)).rejects.toThrow('not found');
  expect(read).toHaveBeenCalledTimes(1);
});

it.each(['example--missing', 'example--hidden', 'WRONG--format'])(
  'uses the public 404 for %s',
  async (slug) => {
    read.mockResolvedValueOnce(null);
    await expect(page(undefined, slug)).rejects.toThrow('not found');
    expect(read).toHaveBeenCalledWith(slug);
  },
);

it.each(['unavailable', 'timeout', 'contract'] as const)(
  'routes %s to the existing retry boundary',
  async (kind) => {
    const log = jest.spyOn(console, 'warn').mockImplementation(() => {});
    try {
      read.mockRejectedValueOnce(new ApiError(kind));
      await expect(page()).rejects.toThrow('Unable to load published promotion details');
      expect(log).toHaveBeenCalledWith('promotion_details_read_failed', {
        category: kind,
        requestId: undefined,
      });
      const reset = jest.fn();
      render(<PromotionError reset={reset} />);
      expect(
        screen.queryByRole('link', { name: /Open official claim site/ }),
      ).not.toBeInTheDocument();
      fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
      expect(reset).toHaveBeenCalledTimes(1);
      expect(refresh).toHaveBeenCalledTimes(1);
    } finally {
      log.mockRestore();
    }
  },
);

import { notFound } from 'next/navigation';
import { ClaimPreparationGuide } from '@/features/promotions/claim/ClaimPreparationGuide';
import { uuid } from '@/lib/api/eligibility.contract';
import { getPromotionDetails } from '@/lib/api/promotion-details.server';
import { ApiError } from '@/lib/api/errors';

export const metadata = { title: 'Prepare your claim' };

export default async function ClaimPage({
  params,
  searchParams,
}: {
  params: Promise<{ slug: string }>;
  searchParams: Promise<{ variant?: string | string[] }>;
}) {
  const [{ slug }, { variant }] = await Promise.all([params, searchParams]);
  let promotion;
  try {
    promotion = await getPromotionDetails(slug);
  } catch (error) {
    console.warn('promotion_details_read_failed', {
      category: error instanceof ApiError ? error.kind : 'unexpected',
      requestId: error instanceof ApiError ? error.requestId : undefined,
    });
    throw new Error('Unable to load published promotion details.');
  }
  if (!promotion) notFound();

  let selected;
  if (variant === undefined) {
    selected = promotion.variants.length === 1 ? promotion.variants[0] : undefined;
  } else {
    const parsed = uuid.safeParse(variant);
    if (!parsed.success) notFound();
    const canonicalId = parsed.data.toLowerCase();
    selected = promotion.variants.find(
      (item) => item.promotion_variant_id.toLowerCase() === canonicalId,
    );
    if (!selected) notFound();
  }
  return <ClaimPreparationGuide promotion={promotion} selected={selected} />;
}

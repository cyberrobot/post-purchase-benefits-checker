import { notFound } from 'next/navigation';
import { PromotionDetailsView } from '@/features/promotions/details/PromotionDetailsView';
import { getPromotionDetails } from '@/lib/api/promotion-details.server';
import { ApiError } from '@/lib/api/errors';

export const metadata = { title: 'Published promotion terms' };

export default async function PromotionPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
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
  return <PromotionDetailsView promotion={promotion} />;
}

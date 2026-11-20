export function claimGuidePath(slug: string, variantId: string) {
  return `/promotions/${slug}/claim?variant=${variantId}`;
}

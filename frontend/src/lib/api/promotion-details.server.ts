import 'server-only';
import { getApiOrigin } from './config';
import { problemSchema } from './eligibility.contract';
import { ApiError, errorKind, safeRequestId } from './errors';
import {
  mediaType,
  MAX_RESPONSE_BYTES,
  readBounded,
  UPSTREAM_TIMEOUT_MS,
  withDeadline,
} from './http';
import { promotionDetailsSchema } from './promotion-details.contract';
import { parsePublicSlug } from './promotion-slug';

export async function getPromotionDetails(publicSlug: string) {
  const parts = parsePublicSlug(publicSlug);
  if (!parts) return null;
  const origin = getApiOrigin();
  if (!origin) throw new ApiError('unavailable');
  return withDeadline(async (signal) => {
    const response = await fetch(new URL('/api/v1/promotions/' + parts.join('/'), origin), {
      cache: 'no-store',
      redirect: 'error',
      credentials: 'omit',
      headers: { Accept: 'application/json, application/problem+json' },
      signal,
    });
    const id = safeRequestId(response.headers.get('x-request-id'));
    const expectedType = response.ok ? 'application/json' : 'application/problem+json';
    if (mediaType(response) !== expectedType) {
      void response.body?.cancel().catch(() => {});
      throw new ApiError('contract', response.status, undefined, id);
    }
    let data: unknown;
    try {
      data = JSON.parse(await readBounded(response.body, MAX_RESPONSE_BYTES, signal));
    } catch {
      throw new ApiError('contract', response.status, undefined, id);
    }
    if (!response.ok) {
      const problem = problemSchema.safeParse(data);
      if (
        !problem.success ||
        problem.data.status !== response.status ||
        (id && id !== problem.data.request_id)
      ) {
        throw new ApiError('contract', response.status, undefined, id);
      }
      if (response.status === 404 && problem.data.code === 'promotion_not_found') return null;
      throw new ApiError(
        errorKind(response.status),
        response.status,
        problem.data.code,
        problem.data.request_id,
      );
    }
    const parsed = promotionDetailsSchema.safeParse(data);
    if (!parsed.success || parsed.data.public_slug !== publicSlug) {
      throw new ApiError('contract', response.status, undefined, id);
    }
    return parsed.data;
  }, UPSTREAM_TIMEOUT_MS);
}

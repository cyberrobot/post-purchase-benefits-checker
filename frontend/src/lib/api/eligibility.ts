import {
  checkPurchaseResponseSchema,
  problemSchema,
  purchaseRequestSchema,
  type PurchaseRequest,
  type CheckPurchaseResponse,
} from './eligibility.contract';
import { ApiError, errorKind, retryAfterSeconds, safeRequestId } from './errors';
import {
  CLIENT_TIMEOUT_MS,
  MAX_RESPONSE_BYTES,
  mediaType,
  readBounded,
  withDeadline,
} from './http';
export type { PurchaseRequest, CheckPurchaseResponse } from './eligibility.contract';
export async function checkPurchase(
  input: PurchaseRequest,
  options?: { signal?: AbortSignal },
): Promise<CheckPurchaseResponse> {
  if (options?.signal?.aborted) throw new ApiError('cancelled');
  const parsed = purchaseRequestSchema.safeParse(input);
  if (!parsed.success) throw new ApiError('validation');
  return withDeadline(
    async (signal) => {
      const response = await fetch('/api/eligibility/check', {
        method: 'POST',
        headers: {
          Accept: 'application/json, application/problem+json',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(parsed.data),
        cache: 'no-store',
        credentials: 'omit',
        signal,
      });
      const requestId = safeRequestId(response.headers.get('x-request-id'));
      let body: unknown;
      try {
        body = JSON.parse(await readBounded(response.body, MAX_RESPONSE_BYTES));
      } catch (error) {
        if (signal.aborted) throw error;
        throw new ApiError('contract', response.status, undefined, requestId);
      }
      if (!response.ok) {
        const problem = problemSchema.safeParse(body);
        if (
          mediaType(response) !== 'application/problem+json' ||
          !problem.success ||
          problem.data.status !== response.status
        )
          throw new ApiError('contract', response.status, undefined, requestId);
        throw new ApiError(
          errorKind(response.status),
          response.status,
          problem.data.code,
          requestId ?? problem.data.request_id,
          retryAfterSeconds(response.headers.get('retry-after')),
        );
      }
      const result = checkPurchaseResponseSchema.safeParse(body);
      if (response.status !== 200 || mediaType(response) !== 'application/json' || !result.success)
        throw new ApiError('contract', response.status, undefined, requestId);
      return result.data;
    },
    CLIENT_TIMEOUT_MS,
    options?.signal,
  );
}

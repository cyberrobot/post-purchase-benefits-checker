import { randomUUID } from 'node:crypto';
import { getApiOrigin } from '@/lib/api/config';
import { checkPurchaseResponseSchema, problemSchema } from '@/lib/api/eligibility.contract';
import { ApiError, retryAfterSeconds, safeRequestId } from '@/lib/api/errors';
import {
  MAX_RESPONSE_BYTES,
  UPSTREAM_TIMEOUT_MS,
  mediaType,
  readBounded,
  withDeadline,
} from '@/lib/api/http';
export const runtime = 'nodejs';
function problem(status: number, code: string, requestId: string) {
  return Response.json(
    {
      type: 'about:blank',
      title: 'Purchase check unavailable',
      status,
      detail:
        status < 500
          ? 'Provide a valid JSON purchase request.'
          : 'Unable to check this purchase. Try again later.',
      code,
      request_id: requestId,
    },
    {
      status,
      headers: {
        'Content-Type': 'application/problem+json',
        'X-Request-ID': requestId,
        'Cache-Control': 'no-store',
      },
    },
  );
}
export async function POST(request: Request): Promise<Response> {
  const requestId = randomUUID();
  if (mediaType(request) !== 'application/json')
    return problem(415, 'unsupported_media_type', requestId);
  let receivingBody = true;
  try {
    return await withDeadline(
      async (signal) => {
        let body: string;
        try {
          body = await readBounded(request.body, 8192, signal);
        } catch (error) {
          if (signal.aborted) throw error;
          return problem(413, 'request_too_large', requestId);
        }
        receivingBody = false;
        try {
          JSON.parse(body);
        } catch {
          return problem(422, 'invalid_purchase_request', requestId);
        }
        const origin = getApiOrigin();
        if (!origin) return problem(503, 'api_not_configured', requestId);
        const upstream = await fetch(`${origin}/api/v1/eligibility/check`, {
          method: 'POST',
          body,
          headers: {
            'Content-Type': 'application/json',
            Accept: 'application/json, application/problem+json',
          },
          cache: 'no-store',
          credentials: 'omit',
          redirect: 'manual',
          signal,
        });
        const id = safeRequestId(upstream.headers.get('x-request-id')) ?? requestId;
        let data: unknown;
        try {
          data = JSON.parse(await readBounded(upstream.body, MAX_RESPONSE_BYTES, signal));
        } catch (error) {
          if (signal.aborted) throw error;
          return problem(502, 'upstream_unavailable', id);
        }
        const headers: Record<string, string> = { 'X-Request-ID': id, 'Cache-Control': 'no-store' };
        if (upstream.status === 200 && mediaType(upstream) === 'application/json') {
          const parsed = checkPurchaseResponseSchema.safeParse(data);
          if (parsed.success) return Response.json(parsed.data, { headers });
        } else if (upstream.status >= 400 && mediaType(upstream) === 'application/problem+json') {
          const parsed = problemSchema.safeParse(data);
          if (parsed.success && parsed.data.status === upstream.status) {
            const retry = retryAfterSeconds(upstream.headers.get('retry-after'));
            if (retry !== undefined) headers['Retry-After'] = String(retry);
            return Response.json(
              {
                type: 'about:blank',
                title: 'Purchase check failed',
                status: upstream.status,
                detail:
                  upstream.status < 500
                    ? 'The purchase request could not be processed.'
                    : 'Unable to check this purchase. Try again later.',
                code: parsed.data.code,
                request_id: id,
              },
              {
                status: upstream.status,
                headers: { ...headers, 'Content-Type': 'application/problem+json' },
              },
            );
          }
        }
        return problem(502, 'upstream_unavailable', id);
      },
      UPSTREAM_TIMEOUT_MS,
      request.signal,
    );
  } catch (error) {
    return error instanceof ApiError && error.kind === 'timeout'
      ? receivingBody
        ? problem(408, 'request_timeout', requestId)
        : problem(504, 'upstream_timeout', requestId)
      : problem(502, 'upstream_unavailable', requestId);
  }
}

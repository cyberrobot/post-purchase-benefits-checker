/** @jest-environment node */
import { getPromotionDetails } from './promotion-details.server';
import { id, recordedTerms } from './promotion-details.fixture';
import { MAX_RESPONSE_BYTES, UPSTREAM_TIMEOUT_MS } from './http';

const slug = recordedTerms.public_slug;
const fetchMock = jest.spyOn(globalThis, 'fetch');
const requestId = id(42);
const origin = process.env.BENEFITSCOUT_API_ORIGIN;

function problem(status: number, code: string) {
  return new Response(
    JSON.stringify({
      type: 'about:blank',
      status,
      code,
      title: 'Unavailable',
      detail: 'Try later.',
      request_id: requestId,
    }),
    { status, headers: { 'Content-Type': 'application/problem+json', 'X-Request-ID': requestId } },
  );
}

beforeEach(() => {
  fetchMock.mockReset();
  process.env.BENEFITSCOUT_API_ORIGIN = 'https://backend.example';
});

afterAll(() => {
  if (origin === undefined) delete process.env.BENEFITSCOUT_API_ORIGIN;
  else process.env.BENEFITSCOUT_API_ORIGIN = origin;
  fetchMock.mockRestore();
});

it('makes exactly one bounded server GET to the configured origin', async () => {
  fetchMock.mockResolvedValue(Response.json(recordedTerms));
  await expect(getPromotionDetails(slug)).resolves.toEqual(recordedTerms);
  expect(fetchMock).toHaveBeenCalledTimes(1);
  expect(fetchMock).toHaveBeenCalledWith(
    new URL('https://backend.example/api/v1/promotions/example/populated-promotion'),
    expect.objectContaining({
      cache: 'no-store',
      redirect: 'error',
      credentials: 'omit',
      signal: expect.any(AbortSignal),
    }),
  );
});

it('handles a validated 404 separately and preserves the unavailable problem identifier', async () => {
  fetchMock
    .mockResolvedValueOnce(problem(404, 'promotion_not_found'))
    .mockResolvedValueOnce(problem(503, 'promotions_unavailable'));
  await expect(getPromotionDetails(slug)).resolves.toBeNull();
  await expect(getPromotionDetails(slug)).rejects.toMatchObject({ kind: 'unavailable', requestId });
});

it('rejects invalid destination configuration without making a request', async () => {
  process.env.BENEFITSCOUT_API_ORIGIN = 'https://user:pass@backend.example';
  await expect(getPromotionDetails(slug)).rejects.toMatchObject({ kind: 'unavailable' });
  await expect(getPromotionDetails('invalid slug')).resolves.toBeNull();
  expect(fetchMock).not.toHaveBeenCalled();
});

it('checks response media type, bounds, JSON and canonical identity', async () => {
  fetchMock
    .mockResolvedValueOnce(new Response('unavailable', { status: 404 }))
    .mockResolvedValueOnce(
      new Response('x'.repeat(MAX_RESPONSE_BYTES + 1), {
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    .mockResolvedValueOnce(
      new Response('{oops', { headers: { 'Content-Type': 'application/json' } }),
    )
    .mockResolvedValueOnce(Response.json(recordedTerms));
  for (let index = 0; index < 4; index++) {
    await expect(getPromotionDetails('example--different')).rejects.toMatchObject({
      kind: 'contract',
    });
  }
});

it('bounds requests even when the underlying fetch does not settle', async () => {
  jest.useFakeTimers();
  try {
    fetchMock.mockImplementation(() => new Promise(() => {}));
    const result = expect(getPromotionDetails(slug)).rejects.toMatchObject({ kind: 'timeout' });
    await jest.advanceTimersByTimeAsync(UPSTREAM_TIMEOUT_MS);
    await result;
    expect(fetchMock.mock.calls[0][1]?.signal?.aborted).toBe(true);
  } finally {
    jest.useRealTimers();
  }
});

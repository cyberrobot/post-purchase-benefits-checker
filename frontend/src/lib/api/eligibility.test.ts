/** @jest-environment node */
import { checkPurchase } from './eligibility';
import { purchase, resolved, unresolved, problem, requestId } from './fixtures';
import { populated, populatedClaim } from './promotion.fixture';
const fetchMock = jest.fn();
beforeEach(() => {
  global.fetch = fetchMock;
  fetchMock.mockReset();
});
it.each([resolved, unresolved, populated, populatedClaim])(
  'returns domain success',
  async (value) => {
    fetchMock.mockResolvedValue(Response.json(value));
    expect(await checkPurchase(purchase)).toEqual(value);
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/eligibility/check',
      expect.objectContaining({
        method: 'POST',
        cache: 'no-store',
        credentials: 'omit',
        body: JSON.stringify(purchase),
      }),
    );
  },
);
it.each([
  [408, 'timeout'],
  [413, 'validation'],
  [415, 'validation'],
  [422, 'validation'],
  [429, 'rate_limited'],
  [502, 'unavailable'],
  [503, 'unavailable'],
  [504, 'timeout'],
  [500, 'server'],
  [401, 'contract'],
])('maps status %s safely', async (status, kind) => {
  fetchMock.mockResolvedValue(
    Response.json(
      { ...problem, status },
      {
        status: Number(status),
        headers: {
          'content-type': 'application/problem+json',
          'x-request-id': requestId,
          'retry-after': '10',
        },
      },
    ),
  );
  await expect(checkPurchase(purchase)).rejects.toMatchObject({
    kind,
    status,
    requestId,
    retryAfterSeconds: 10,
  });
  expect(fetchMock).toHaveBeenCalledTimes(1);
});
it.each([
  new Response('<html>secret</html>'),
  Response.json({ ...resolved, promotions: [{}] }),
  Response.json(resolved, { headers: { 'content-type': 'text/html' } }),
])('rejects invalid reply', async (response) => {
  fetchMock.mockResolvedValue(response);
  await expect(checkPurchase(purchase)).rejects.toMatchObject({ kind: 'contract' });
});
it('rejects invalid input without network', async () => {
  await expect(checkPurchase({ ...purchase, purchase_date: 'invalid' })).rejects.toMatchObject({
    kind: 'validation',
  });
  expect(fetchMock).not.toHaveBeenCalled();
});
it('sanitizes network errors', async () => {
  fetchMock.mockRejectedValue(new Error('private hostname'));
  await expect(checkPurchase(purchase)).rejects.toMatchObject({
    kind: 'unavailable',
    message: 'Purchase check failed: unavailable',
  });
});
it('aborts immediately or during a request', async () => {
  const controller = new AbortController();
  controller.abort();
  await expect(checkPurchase(purchase, { signal: controller.signal })).rejects.toMatchObject({
    kind: 'cancelled',
  });
  expect(fetchMock).not.toHaveBeenCalled();
  const active = new AbortController();
  fetchMock.mockImplementation(
    (_url, { signal }) =>
      new Promise((_resolve, reject) =>
        signal.addEventListener('abort', () => reject(new Error('abort'))),
      ),
  );
  const result = checkPurchase(purchase, { signal: active.signal });
  active.abort();
  await expect(result).rejects.toMatchObject({ kind: 'cancelled' });
});
it('distinguishes deadline and removes timers', async () => {
  jest.useFakeTimers();
  fetchMock.mockImplementation(
    (_url, { signal }) =>
      new Promise((_resolve, reject) =>
        signal.addEventListener('abort', () => reject(new Error('abort'))),
      ),
  );
  const result = checkPurchase(purchase);
  const assertion = expect(result).rejects.toMatchObject({ kind: 'timeout' });
  await jest.advanceTimersByTimeAsync(10000);
  await assertion;
  expect(jest.getTimerCount()).toBe(0);
  jest.useRealTimers();
});

it('rejects a shaped success with unsafe source evidence', async () => {
  const value = structuredClone(populated);
  value.promotions[0].provenance.claim_url = 'javascript:alert(1)';
  fetchMock.mockResolvedValue(Response.json(value));
  await expect(checkPurchase(purchase)).rejects.toMatchObject({ kind: 'contract' });
});

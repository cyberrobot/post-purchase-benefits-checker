/** @jest-environment node */
jest.mock('server-only', () => ({}), { virtual: true });
import { POST } from './route';
import { purchase, resolved, unresolved, problem, requestId } from '@/lib/api/fixtures';
const fetchMock = jest.fn();
const request = (body = JSON.stringify(purchase), headers: Record<string, string> = {}) =>
  new Request('http://localhost/api/eligibility/check?url=https://evil.test', {
    method: 'POST',
    body,
    headers: { 'Content-Type': 'application/json', ...headers },
  });
beforeEach(() => {
  process.env.BENEFITSCOUT_API_ORIGIN = 'http://127.0.0.1:8000';
  global.fetch = fetchMock;
  fetchMock.mockReset();
});
afterEach(() => delete process.env.BENEFITSCOUT_API_ORIGIN);
it.each([resolved, unresolved])(
  'forwards only the fixed operation and controlled headers',
  async (value) => {
    fetchMock.mockResolvedValue(Response.json(value, { headers: { 'x-request-id': requestId } }));
    const response = await POST(
      request(undefined, { cookie: 'secret', authorization: 'secret', host: 'evil.test' }),
    );
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual(value);
    expect(response.headers.get('x-request-id')).toBe(requestId);
    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/v1/eligibility/check',
      expect.objectContaining({
        method: 'POST',
        redirect: 'manual',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json, application/problem+json',
        },
        body: JSON.stringify(purchase),
      }),
    );
  },
);
it.each([413, 415, 422, 429, 500, 503])('preserves problem %s', async (status) => {
  fetchMock.mockResolvedValue(
    Response.json(
      { ...problem, status },
      {
        status,
        headers: {
          'Content-Type': 'application/problem+json',
          'x-request-id': requestId,
          'retry-after': '30',
        },
      },
    ),
  );
  const response = await POST(request());
  expect(response.status).toBe(status);
  expect(await response.json()).toEqual({
    type: 'about:blank',
    title: 'Purchase check failed',
    status,
    detail:
      status < 500
        ? 'The purchase request could not be processed.'
        : 'Unable to check this purchase. Try again later.',
    code: problem.code,
    request_id: requestId,
  });
  expect(response.headers.get('retry-after')).toBe('30');
});
it('does not reflect hostile upstream problem text', async () => {
  fetchMock.mockResolvedValue(
    Response.json(
      {
        ...problem,
        type: 'https://attacker.test/trace?token=private',
        title: 'trace at /srv/private/app.py with password=hunter2',
        detail: 'backend http://db.internal:5432 failed; Authorization: Bearer secret',
        request_id: requestId,
      },
      {
        status: 422,
        headers: { 'Content-Type': 'application/problem+json', 'x-request-id': requestId },
      },
    ),
  );

  const response = await POST(request());
  const body = await response.text();
  expect(response.status).toBe(422);
  expect(body).not.toMatch(/attacker|trace|srv|password|hunter2|db\.internal|Bearer|secret/i);
  expect(JSON.parse(body)).toMatchObject({
    type: 'about:blank',
    title: 'Purchase check failed',
    status: 422,
    code: problem.code,
    request_id: requestId,
  });
});
it.each([
  '',
  'bad',
  'https://user:pass@example.com',
  'https://example.com/path',
  'https://example.com?x=1',
  'https://example.com#fragment',
  'ftp://example.com',
  'http://example.com',
])('rejects unsafe config %s lazily', async (value) => {
  process.env.BENEFITSCOUT_API_ORIGIN = value;
  expect((await POST(request())).status).toBe(503);
  expect(fetchMock).not.toHaveBeenCalled();
});
it('bounds request streaming and rejects media/malformed JSON', async () => {
  expect((await POST(request('x'.repeat(8193)))).status).toBe(413);
  expect((await POST(request('{}', { 'Content-Type': 'text/plain' }))).status).toBe(415);
  expect((await POST(request('{'))).status).toBe(422);
  expect(fetchMock).not.toHaveBeenCalled();
});
it.each([
  new Response('<html>private</html>'),
  Response.json({}),
  new Response('', { status: 302, headers: { location: 'https://evil.test' } }),
])('fails closed for malformed upstream', async (reply) => {
  fetchMock.mockResolvedValue(reply);
  const response = await POST(request());
  expect(response.status).toBe(502);
  expect(await response.text()).not.toContain('private');
});
it('sanitizes connection errors and unsafe headers', async () => {
  fetchMock.mockRejectedValue(new Error('http://private:secret'));
  const response = await POST(request());
  expect(response.status).toBe(502);
  expect(await response.text()).not.toContain('private');
  expect(response.headers.get('x-request-id')).toMatch(/^[0-9a-f-]{36}$/);
});
it('bounds upstream response size', async () => {
  fetchMock.mockResolvedValue(new Response('x'.repeat(1048577)));
  expect((await POST(request())).status).toBe(502);
});
it('times out upstream', async () => {
  jest.useFakeTimers();
  fetchMock.mockImplementation(
    (_url, { signal }) =>
      new Promise((_resolve, reject) =>
        signal.addEventListener('abort', () => reject(new Error('abort'))),
      ),
  );
  const result = POST(request());
  await jest.advanceTimersByTimeAsync(8000);
  expect((await result).status).toBe(504);
  jest.useRealTimers();
});

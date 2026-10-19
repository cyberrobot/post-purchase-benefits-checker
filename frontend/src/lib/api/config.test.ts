/** @jest-environment node */
jest.mock('server-only', () => ({}), { virtual: true });
import { getApiOrigin } from './config';

const originalNodeEnv = process.env.NODE_ENV;
afterEach(() => {
  if (originalNodeEnv === undefined) Reflect.deleteProperty(process.env, 'NODE_ENV');
  else Reflect.set(process.env, 'NODE_ENV', originalNodeEnv);
  delete process.env.BENEFITSCOUT_API_ORIGIN;
});

it('accepts HTTPS origins in production', () => {
  Reflect.set(process.env, 'NODE_ENV', 'production');
  process.env.BENEFITSCOUT_API_ORIGIN = 'https://api.example.com';
  expect(getApiOrigin()).toBe('https://api.example.com');
});

it.each(['http://127.0.0.1:8000', 'http://localhost:8000'])(
  'rejects local HTTP origins in production: %s',
  (origin) => {
    Reflect.set(process.env, 'NODE_ENV', 'production');
    process.env.BENEFITSCOUT_API_ORIGIN = origin;
    expect(getApiOrigin()).toBeUndefined();
  },
);

it('keeps local HTTP origins available outside production', () => {
  Reflect.set(process.env, 'NODE_ENV', 'test');
  process.env.BENEFITSCOUT_API_ORIGIN = 'http://127.0.0.1:8000';
  expect(getApiOrigin()).toBe('http://127.0.0.1:8000');
});

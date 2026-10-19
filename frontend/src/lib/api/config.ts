import 'server-only';
// Read on each invocation: deployment configuration is a server runtime concern.
export function getApiOrigin(): string | undefined {
  const value = process.env.BENEFITSCOUT_API_ORIGIN;
  if (!value || value !== value.trim()) return;
  try {
    const url = new URL(value);
    if (url.username || url.password || url.pathname !== '/' || url.search || url.hash) return;
    const localHttp =
      process.env.NODE_ENV !== 'production' &&
      url.protocol === 'http:' &&
      ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname);
    if (url.protocol !== 'https:' && !localHttp) return;
    return url.origin;
  } catch {
    return;
  }
}

export type ApiErrorKind =
  'validation' | 'rate_limited' | 'unavailable' | 'timeout' | 'cancelled' | 'server' | 'contract';
export class ApiError extends Error {
  constructor(
    public readonly kind: ApiErrorKind,
    public readonly status?: number,
    public readonly code?: string,
    public readonly requestId?: string,
    public readonly retryAfterSeconds?: number,
  ) {
    super(`Purchase check failed: ${kind}`);
    this.name = 'ApiError';
  }
}
export function errorKind(status: number): ApiErrorKind {
  if ([413, 415, 422].includes(status)) return 'validation';
  if (status === 429) return 'rate_limited';
  if ([502, 503].includes(status)) return 'unavailable';
  if (status === 504) return 'timeout';
  return status >= 500 ? 'server' : 'contract';
}
export function safeRequestId(value: string | null): string | undefined {
  return value && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value)
    ? value
    : undefined;
}
export function retryAfterSeconds(value: string | null): number | undefined {
  if (!value || value.length > 64) return;
  const seconds = /^\d+$/.test(value) ? Number(value) : (Date.parse(value) - Date.now()) / 1000;
  return Number.isFinite(seconds) && seconds >= 0 && seconds <= 86400
    ? Math.ceil(seconds)
    : undefined;
}

import { ApiError } from './errors';
export const CLIENT_TIMEOUT_MS = 10_000;
export const UPSTREAM_TIMEOUT_MS = 8_000;
export const MAX_RESPONSE_BYTES = 1_048_576;
export async function readBounded(
  body: ReadableStream<Uint8Array> | null,
  limit: number,
): Promise<string> {
  if (!body) return '';
  const reader = body.getReader();
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > limit) {
        await reader.cancel();
        throw new ApiError('contract');
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return new TextDecoder('utf-8', { fatal: true }).decode(bytes);
}
export async function withDeadline<T>(
  operation: (signal: AbortSignal) => Promise<T>,
  timeout: number,
  caller?: AbortSignal,
): Promise<T> {
  if (caller?.aborted) throw new ApiError('cancelled');
  const controller = new AbortController();
  let timedOut = false;
  const cancel = () => controller.abort();
  caller?.addEventListener('abort', cancel, { once: true });
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeout);
  try {
    return await operation(controller.signal);
  } catch (error) {
    if (caller?.aborted) throw new ApiError('cancelled');
    if (timedOut) throw new ApiError('timeout');
    if (error instanceof ApiError) throw error;
    throw new ApiError('unavailable');
  } finally {
    clearTimeout(timer);
    caller?.removeEventListener('abort', cancel);
  }
}
export function mediaType(response: Response | Request): string {
  return response.headers.get('content-type')?.split(';')[0].trim().toLowerCase() ?? '';
}

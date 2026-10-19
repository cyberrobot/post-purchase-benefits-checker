import { renderHook, act, waitFor } from '@testing-library/react';
import { QueryProvider } from '@/components/providers/QueryProvider';
import { useCheckPurchaseMutation } from './useCheckPurchaseMutation';
import { checkPurchase } from '@/lib/api/eligibility';
import { purchase, unresolved } from '@/lib/api/fixtures';
import { ApiError } from '@/lib/api/errors';
import { onlineManager } from '@tanstack/react-query';
jest.mock('@/lib/api/eligibility', () => ({ checkPurchase: jest.fn() }));
const mocked = jest.mocked(checkPurchase);
beforeEach(() => {
  mocked.mockReset();
  onlineManager.setOnline(true);
});
afterEach(() => onlineManager.setOnline(true));
it('does nothing on render, focus, reconnect and submits only explicitly', async () => {
  mocked.mockResolvedValue(unresolved as Awaited<ReturnType<typeof checkPurchase>>);
  const { result, rerender } = renderHook(useCheckPurchaseMutation, { wrapper: QueryProvider });
  rerender();
  window.dispatchEvent(new Event('focus'));
  window.dispatchEvent(new Event('online'));
  expect(mocked).not.toHaveBeenCalled();
  await act(async () => {
    await result.current.mutateAsync(purchase);
  });
  await waitFor(() => expect(result.current.isSuccess).toBe(true));
  expect(result.current.data).toEqual(unresolved);
  expect(mocked).toHaveBeenCalledTimes(1);
});
it('does not replay an offline submission when connectivity returns', async () => {
  mocked.mockResolvedValue(unresolved as Awaited<ReturnType<typeof checkPurchase>>);
  const { result } = renderHook(useCheckPurchaseMutation, { wrapper: QueryProvider });
  onlineManager.setOnline(false);

  await act(async () => {
    await result.current.mutateAsync(purchase);
  });
  expect(mocked).toHaveBeenCalledTimes(1);

  onlineManager.setOnline(true);
  await waitFor(() => expect(result.current.isSuccess).toBe(true));
  expect(mocked).toHaveBeenCalledTimes(1);

  await act(async () => {
    await result.current.mutateAsync(purchase);
  });
  expect(mocked).toHaveBeenCalledTimes(2);
});
it('does not retry errors', async () => {
  mocked.mockRejectedValue(new ApiError('unavailable'));
  const { result } = renderHook(useCheckPurchaseMutation, { wrapper: QueryProvider });
  await act(async () => {
    await expect(result.current.mutateAsync(purchase)).rejects.toMatchObject({
      kind: 'unavailable',
    });
  });
  await waitFor(() => expect(result.current.isError).toBe(true));
  expect(mocked).toHaveBeenCalledTimes(1);
});

it.each(['success', 'error'])('reset clears a previous %s to idle', async (outcome) => {
  if (outcome === 'success')
    mocked.mockResolvedValue(unresolved as Awaited<ReturnType<typeof checkPurchase>>);
  else mocked.mockRejectedValue(new ApiError('unavailable'));
  const { result } = renderHook(useCheckPurchaseMutation, { wrapper: QueryProvider });
  await act(async () => {
    await result.current.mutateAsync(purchase).catch(() => {});
  });
  await waitFor(() => expect(result.current.status).toBe(outcome));
  if (outcome === 'success') expect(result.current.data).toEqual(unresolved);
  else expect(result.current.error).toMatchObject({ kind: 'unavailable' });
  act(() => result.current.reset());
  await waitFor(() => expect(result.current.status).toBe('idle'));
  expect(result.current.data).toBeUndefined();
  expect(result.current.error).toBeNull();
  window.dispatchEvent(new Event('focus'));
  window.dispatchEvent(new Event('online'));
  expect(mocked).toHaveBeenCalledTimes(1);
});

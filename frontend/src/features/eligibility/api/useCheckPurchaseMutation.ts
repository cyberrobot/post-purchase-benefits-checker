'use client';
import { useMutation } from '@tanstack/react-query';
import {
  checkPurchase,
  type PurchaseRequest,
  type CheckPurchaseResponse,
} from '@/lib/api/eligibility';
import type { ApiError } from '@/lib/api/errors';
// Mutations are explicit. TanStack Query does not automatically cancel them.
export function useCheckPurchaseMutation() {
  return useMutation<CheckPurchaseResponse, ApiError, PurchaseRequest>({
    mutationFn: (input) => checkPurchase(input),
    retry: false,
    // An offline submission should fail immediately; reconnecting must not replay it.
    networkMode: 'always',
    gcTime: 0,
  });
}

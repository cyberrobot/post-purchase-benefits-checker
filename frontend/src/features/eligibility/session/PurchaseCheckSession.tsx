'use client';
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';
import type { CheckPurchaseResponse, PurchaseRequest } from '@/lib/api/eligibility.contract';
import type { Draft } from '../components/purchaseForm';
export type Snapshot = { submittedPurchase: PurchaseRequest; response: CheckPurchaseResponse };
const empty: Draft = { brand: '', model: '', retailer: '', purchase_date: '' };
function immutableCopy<T>(value: T): T {
  const copy = JSON.parse(JSON.stringify(value)) as T;
  function freeze(item: unknown) {
    if (item && typeof item === 'object') {
      Object.values(item).forEach(freeze);
      Object.freeze(item);
    }
  }
  freeze(copy);
  return copy;
}
type Session = {
  snapshot: Snapshot | null;
  draft: Draft;
  publish: (purchase: PurchaseRequest, response: CheckPurchaseResponse) => void;
  edit: (draft: Draft) => void;
};
const Context = createContext<Session | null>(null);
export function PurchaseCheckSessionProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<{ snapshot: Snapshot | null; draft: Draft }>({
    snapshot: null,
    draft: empty,
  });
  const publish = useCallback((purchase: PurchaseRequest, response: CheckPurchaseResponse) => {
    const snapshot = immutableCopy({ submittedPurchase: purchase, response });
    setState({
      snapshot,
      draft: { ...purchase, purchase_price: purchase.purchase_price ?? undefined },
    });
  }, []);
  const edit = useCallback((draft: Draft) => setState({ snapshot: null, draft: { ...draft } }), []);
  const value = useMemo(() => ({ ...state, publish, edit }), [state, publish, edit]);
  return <Context.Provider value={value}>{children}</Context.Provider>;
}
export function usePurchaseCheckSession() {
  const context = useContext(Context);
  if (!context) throw new Error('Purchase check session provider is required.');
  return context;
}

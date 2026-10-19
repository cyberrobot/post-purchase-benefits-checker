import type { CheckPurchaseResponse, PurchaseRequest } from './eligibility.contract';
// Compile-time wire assertions: dates and money never become JavaScript numbers/Date.
type Assert<T extends true> = T;
type Equal<A, B> =
  (<T>() => T extends A ? 1 : 2) extends <T>() => T extends B ? 1 : 2 ? true : false;
export type DateIsString = Assert<Equal<PurchaseRequest['purchase_date'], string>>;
export type MoneyIsWireString = Assert<
  Equal<PurchaseRequest['purchase_price'], string | null | undefined>
>;
export type OutcomeDiscriminant = Assert<
  Equal<CheckPurchaseResponse['outcome'], 'resolved' | 'unresolved_identity'>
>;

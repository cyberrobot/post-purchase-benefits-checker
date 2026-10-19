import type { ComponentPropsWithoutRef } from 'react';
const variants = {
  neutral: 'bg-surface-muted text-ink-muted',
  accent: 'bg-surface-muted text-brand',
  success: 'bg-success-subtle text-success',
};
type BadgeProps = ComponentPropsWithoutRef<'span'> & { variant?: 'neutral' | 'accent' | 'success' };
export function Badge({ variant = 'neutral', className = '', ...props }: BadgeProps) {
  return (
    <span
      className={`inline-block max-w-full rounded-full px-3 py-1 text-small leading-normal font-semibold wrap-anywhere ${variants[variant]} ${className}`}
      {...props}
    />
  );
}

import type { ComponentPropsWithoutRef } from 'react';
type BadgeProps = ComponentPropsWithoutRef<'span'> & { variant?: 'neutral' | 'accent' | 'success' };
export function Badge({ variant = 'neutral', className = '', ...props }: BadgeProps) {
  return <span className={`badge badge--${variant} ${className}`} {...props} />;
}

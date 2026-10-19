import type { ComponentPropsWithoutRef } from 'react';
const variants = {
  default: 'border-border bg-surface shadow-card',
  subtle: 'border-border bg-surface-muted',
  dark: 'border-navy-panel bg-navy-panel text-on-dark',
};
type CardProps = ComponentPropsWithoutRef<'div'> & { variant?: 'default' | 'subtle' | 'dark' };
export function Card({ variant = 'default', className = '', ...props }: CardProps) {
  return (
    <div
      data-surface={variant}
      className={`group/card min-w-0 rounded-card border p-6 wrap-anywhere ${variants[variant]} ${className}`}
      {...props}
    />
  );
}

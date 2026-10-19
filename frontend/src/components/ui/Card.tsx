import type { ComponentPropsWithoutRef } from 'react';
type CardProps = ComponentPropsWithoutRef<'div'> & { variant?: 'default' | 'subtle' | 'dark' };
export function Card({ variant = 'default', className = '', ...props }: CardProps) {
  return <div className={`card card--${variant} ${className}`} {...props} />;
}

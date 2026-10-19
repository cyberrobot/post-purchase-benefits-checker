import type { ComponentPropsWithoutRef } from 'react';
type ContainerProps = ComponentPropsWithoutRef<'div'> & { width?: 'wide' | 'narrow' };
export function Container({ width = 'wide', className = '', ...props }: ContainerProps) {
  return <div className={`container container--${width} ${className}`} {...props} />;
}

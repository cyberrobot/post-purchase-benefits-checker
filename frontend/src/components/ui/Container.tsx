import type { ComponentPropsWithoutRef } from 'react';
type ContainerProps = ComponentPropsWithoutRef<'div'> & { width?: 'wide' | 'narrow' };
export function Container({ width = 'wide', className = '', ...props }: ContainerProps) {
  return (
    <div
      className={`mx-auto w-full min-w-0 px-4 md:px-8 lg:px-10 ${width === 'narrow' ? 'max-w-3xl' : 'max-w-7xl'} ${className}`}
      {...props}
    />
  );
}

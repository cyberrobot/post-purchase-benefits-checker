import type { ComponentPropsWithoutRef } from 'react';
import { buttonStyles, type ButtonVariant } from './buttonStyles';
type ButtonProps = ComponentPropsWithoutRef<'button'> & { variant?: ButtonVariant };
export function Button({ variant = 'primary', type = 'button', className, ...props }: ButtonProps) {
  return <button type={type} className={buttonStyles(variant, className)} {...props} />;
}

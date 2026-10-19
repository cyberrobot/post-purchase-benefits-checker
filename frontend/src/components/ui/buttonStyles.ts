export type ButtonVariant = 'primary' | 'secondary' | 'ghost';
export function buttonStyles(variant: ButtonVariant, className = '') {
  return `control control--${variant} ${className}`;
}

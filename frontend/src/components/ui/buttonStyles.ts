export type ButtonVariant = 'primary' | 'secondary' | 'ghost';
const variants: Record<ButtonVariant, string> = {
  primary: 'border-transparent bg-ink text-on-dark',
  secondary: 'border-transparent bg-brand text-on-dark',
  ghost: 'border-brand bg-surface text-brand',
};
export function buttonStyles(variant: ButtonVariant, className = '') {
  return `inline-flex min-h-11 cursor-pointer items-center justify-center gap-2 rounded-control border px-6 py-3 text-center leading-[1.4] font-semibold no-underline wrap-anywhere hover:underline disabled:hover:no-underline hover:underline-offset-4 disabled:cursor-not-allowed disabled:border-border disabled:bg-surface-muted disabled:text-ink-muted ${variants[variant]} ${className}`;
}

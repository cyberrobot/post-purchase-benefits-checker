import Link from 'next/link';
import type { ComponentPropsWithoutRef } from 'react';
import { buttonStyles, type ButtonVariant } from './buttonStyles';
type ButtonLinkProps = Omit<ComponentPropsWithoutRef<'a'>, 'href'> & {
  href: string;
  variant?: ButtonVariant;
  prefetch?: boolean;
};
export function ButtonLink({
  href,
  variant = 'primary',
  className,
  target,
  rel,
  prefetch,
  ...props
}: ButtonLinkProps) {
  const styles = buttonStyles(variant, className);
  const safeRel = target === '_blank' ? `${rel ?? ''} noopener noreferrer`.trim() : rel;
  if ((href.startsWith('/') && !href.startsWith('//')) || href.startsWith('#')) {
    return (
      <Link
        prefetch={prefetch}
        href={href}
        className={styles}
        target={target}
        rel={safeRel}
        {...props}
      />
    );
  }
  if (!/^https?:\/\//i.test(href))
    throw new Error('ButtonLink requires an internal path, anchor or HTTP(S) URL.');
  return <a href={href} className={styles} target={target} rel={safeRel} {...props} />;
}

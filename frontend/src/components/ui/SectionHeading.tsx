import type { ReactNode } from 'react';
type SectionHeadingProps = {
  level: 'h2' | 'h3';
  children: ReactNode;
  eyebrow?: string;
  description?: string;
  align?: 'normal' | 'center';
  id?: string;
};
export function SectionHeading({
  level: Heading,
  children,
  eyebrow,
  description,
  align = 'normal',
  id,
}: SectionHeadingProps) {
  return (
    <div className={`section-heading section-heading--${align}`}>
      {eyebrow && <p className="eyebrow">{eyebrow}</p>}
      <Heading id={id} className="type-section">
        {children}
      </Heading>
      {description && <p className="body-copy">{description}</p>}
    </div>
  );
}

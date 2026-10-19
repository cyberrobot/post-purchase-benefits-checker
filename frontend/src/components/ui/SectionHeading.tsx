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
    <div className={`grid gap-3 ${align === 'center' ? 'justify-items-center text-center' : ''}`}>
      {eyebrow && (
        <p className="text-small font-bold tracking-widest text-brand uppercase group-data-[surface=dark]/card:text-highlight">
          {eyebrow}
        </p>
      )}
      <Heading id={id} className="text-section leading-[1.15] font-bold tracking-tight">
        {children}
      </Heading>
      {description && (
        <p className="max-w-[70ch] text-body text-ink-muted group-data-[surface=dark]/card:text-on-dark">
          {description}
        </p>
      )}
    </div>
  );
}
